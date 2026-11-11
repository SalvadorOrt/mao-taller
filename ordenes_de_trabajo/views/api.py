import json

import requests
import xml.etree.ElementTree as ET

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone


from servicios.models import ServicioCatalogo
from inventario.models import CodigoProducto, StockSucursal

from .utils import obtener_sucursal_activa

from ..models import (
    Cliente,
    ExpedienteVehiculo,
    PlantillaRecomendacion,
)


# =========================================================
# CONFIGURACIÓN
# =========================================================

PLACA_API_USERNAME = settings.PLACA_API_USERNAME
CEDULA_API_TOKEN = getattr(settings, "CEDULA_API_TOKEN", "")



# =========================================================
# UTILIDADES GENERALES
# =========================================================

def parametro_booleano(request, nombre, default=False):
    """
    Convierte parámetros GET tipo:
    true / false
    1 / 0
    yes / no
    si / no
    """
    valor = request.GET.get(nombre)

    if valor is None:
        return default

    return str(valor).strip().lower() in {
        "1",
        "true",
        "yes",
        "si",
        "sí",
        "on",
    }


def valor_vacio(valor):
    """
    Determina si un valor proveniente de API está vacío.
    """
    if valor is None:
        return True

    if isinstance(valor, str):
        return not valor.strip()

    if isinstance(valor, (list, dict)):
        return len(valor) == 0

    return False


def texto_limpio(valor):
    """
    Convierte un valor a texto seguro para comparación.
    """
    if valor is None:
        return ""

    return str(valor).strip()


# =========================================================
# HELPERS: CLIENTE / API
# =========================================================

def _iso(valor):
    """Convierte date/datetime a ISO-8601 para JSON."""
    return valor.isoformat() if valor else ""


def _edad_desde_fecha(fecha_nacimiento):
    """Calcula la edad sin almacenarla en BD."""
    if not fecha_nacimiento:
        return None

    hoy = timezone.localdate()
    return (
        hoy.year
        - fecha_nacimiento.year
        - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    )


def _identificacion_valida_cliente(cliente):
    """Devuelve cédula/RUC válida para autocompletado o cadena vacía."""
    if not cliente or not cliente.identificacion:
        return ""

    valor = str(cliente.identificacion).strip()
    return valor if valor.isdigit() and len(valor) in (10, 13) else ""


def _datos_contacto_cliente(cliente):
    """Datos reutilizables del cliente asociado a una placa."""
    if not cliente:
        return {
            "cliente_id": None,
            "identificacion": "",
            "nombre_completo": "",
            "telefono": "",
            "telefono_secundario": "",
            "telefono_trabajo": "",
            "email": "",
            "direccion": "",
        }

    return {
        "cliente_id": cliente.id,
        "identificacion": _identificacion_valida_cliente(cliente),
        "nombre_completo": cliente.nombre_completo or "",
        "telefono": cliente.telefono or "",
        "telefono_secundario": cliente.telefono_secundario or "",
        "telefono_trabajo": cliente.telefono_trabajo or "",
        "email": cliente.email or "",
        "direccion": cliente.direccion or "",
    }


# =========================================================
# API: CONSULTAR PLACA
# =========================================================

@login_required
def consultar_regcheck(request):
    placa = (
        request.GET.get("placa", "")
        .strip()
        .upper()
        .replace("-", "")
        .replace(" ", "")
    )

    if not placa:
        return JsonResponse(
            {"exito": False, "error": "Placa vacía."},
            status=400,
        )

    # 1. Primero MAO: evita volver a consumir la API de placa.
    expediente = (
        ExpedienteVehiculo.objects
        .filter(placa=placa)
        .order_by("-id")
        .first()
    )

    if expediente:
        ultima_ot = (
            expediente.ordenes
            .order_by("-fecha_ingreso")
            .first()
        )

        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "placa": expediente.placa or "",
            "vehiculo": expediente.vehiculo or "",
            "marca": expediente.marca_api or "",
            "modelo": expediente.modelo_api or "",
            "descripcion": expediente.descripcion_api or expediente.vehiculo or "",
            "anio": expediente.anio_vehiculo or "",
            "tipo": expediente.tipo_vehiculo_api or "",
            "subtipo": expediente.subtipo_vehiculo_api or "",
            "numero_chasis": expediente.numero_chasis or "",
            "imagen_url": expediente.imagen_url_api or "",
            "color": ultima_ot.color if ultima_ot else "",
            "kilometraje": ultima_ot.kilometraje if ultima_ot else "",
            **_datos_contacto_cliente(expediente.cliente),
        })

    # 2. No está en MAO: consultar API externa de placa.
    url = "https://www.placaapi.ec/API/reg.asmx/CheckEcuador"

    try:
        respuesta = requests.get(
            url,
            params={
                "RegistrationNumber": placa,
                "username": PLACA_API_USERNAME,
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/xml,text/xml,*/*",
            },
            timeout=20,
        )

        if respuesta.status_code != 200:
            return JsonResponse(
                {
                    "exito": False,
                    "error": f"Error API placa: {respuesta.status_code}",
                },
                status=502,
            )

        root = ET.fromstring(respuesta.content)
        json_text = next(
            (
                elem.text
                for elem in root.iter()
                if elem.tag.endswith("vehicleJson") and elem.text
            ),
            None,
        )

        if not json_text:
            return JsonResponse(
                {"exito": False, "error": "Vehículo no encontrado."},
                status=404,
            )

        datos_auto = json.loads(json_text)

        def valor_api(campo):
            valor = datos_auto.get(campo)
            if isinstance(valor, dict):
                return str(valor.get("CurrentTextValue") or "").strip()
            return str(valor or "").strip()

        marca = (valor_api("MakeDescription") or valor_api("CarMake")).upper()
        if marca == "VW":
            marca = "VOLKSWAGEN"

        modelo = (valor_api("ModelDescription") or valor_api("CarModel")).upper()
        descripcion = str(
            datos_auto.get("Description") or f"{marca} {modelo}"
        ).strip().upper()

        anio = valor_api("Year")
        tipo = valor_api("Type")
        subtipo = valor_api("Subtype")
        numero_chasis = valor_api("VehicleIdentificationNumber")
        imagen_url = valor_api("ImageUrl")


        expediente = ExpedienteVehiculo(placa=placa)
        expediente.cargar_desde_api_placa(datos_auto)
        expediente.fecha_ultima_consulta_placa = timezone.now()
        expediente.save()

        return JsonResponse({
            "exito": True,
            "origen": "api_guardada",
            "placa": expediente.placa or placa,
            "vehiculo": expediente.vehiculo or descripcion,
            "marca": expediente.marca_api or marca,
            "modelo": expediente.modelo_api or modelo,
            "descripcion": expediente.descripcion_api or descripcion,
            "anio": expediente.anio_vehiculo or "",
            "tipo": expediente.tipo_vehiculo_api or tipo,
            "subtipo": expediente.subtipo_vehiculo_api or subtipo,
            "numero_chasis": expediente.numero_chasis or numero_chasis or "",
            "imagen_url": expediente.imagen_url_api or imagen_url or "",
            **_datos_contacto_cliente(None),
        })

    except requests.RequestException as e:
        return JsonResponse(
            {
                "exito": False,
                "error": f"No se pudo conectar con la API de placa: {e}",
            },
            status=502,
        )
    except (ET.ParseError, json.JSONDecodeError, ValueError) as e:
        return JsonResponse(
            {
                "exito": False,
                "error": f"Respuesta inválida de la API de placa: {e}",
            },
            status=502,
        )
    except Exception as e:
        return JsonResponse(
            {"exito": False, "error": f"Error al consultar placa: {e}"},
            status=500,
        )


# =========================================================
# CLIENTE: SERIALIZADOR
# =========================================================

def serializar_cliente(cliente):
    """
    Serializa el Cliente para la interfaz de MAO.

    La edad se calcula; no se almacena.
    Los campos FULL que aún no existan como columnas se intentan
    recuperar de datos_api_originales para no perder información.
    """
    raw = cliente.datos_api_originales or {}
    persona_raw = raw.get("persona") or {}
    fechas_raw = persona_raw.get("fechas") or {}
    licencia_raw = raw.get("licencia") or {}

    condicion_cedulado = (
        getattr(cliente, "condicion_cedulado", "")
        or persona_raw.get("condicionCedulado")
        or raw.get("condicionCedulado")
        or ""
    )
    fecha_defuncion = (
        getattr(cliente, "fecha_defuncion", None)
        or fechas_raw.get("defuncion")
    )
    fecha_inscripcion_defuncion = (
        getattr(cliente, "fecha_inscripcion_defuncion", None)
        or fechas_raw.get("inscripcionDefuncion")
        or raw.get("fechaInscripcionDefuncion")
    )
    licencia_infracciones = (
        getattr(cliente, "licencia_infracciones", "")
        or licencia_raw.get("infracciones")
        or ""
    )

    return {
        # Identificación
        "id": cliente.id,
        "identificacion": cliente.identificacion or "",
        "tipo_documento": cliente.tipo_documento or "",
        "nombre_completo": cliente.nombre_completo or "",

        # Contacto
        "telefono": cliente.telefono or "",
        "telefono_secundario": cliente.telefono_secundario or "",
        "telefono_trabajo": cliente.telefono_trabajo or "",
        "email": cliente.email or "",
        "direccion": cliente.direccion or "",

        # Persona
        "edad": _edad_desde_fecha(cliente.fecha_nacimiento),
        "genero": cliente.genero or "",
        "sexo": cliente.sexo or "",
        "fecha_nacimiento": _iso(cliente.fecha_nacimiento),
        "fecha_cedulacion": _iso(cliente.fecha_cedulacion),
        "fecha_defuncion": _iso(fecha_defuncion) if not isinstance(fecha_defuncion, str) else fecha_defuncion,
        "fecha_inscripcion_defuncion": (
            _iso(fecha_inscripcion_defuncion)
            if not isinstance(fecha_inscripcion_defuncion, str)
            else fecha_inscripcion_defuncion
        ),
        "estado_civil": cliente.estado_civil or "",
        "conyuge": cliente.conyuge or "",
        "nacionalidad": cliente.nacionalidad or "",
        "condicion_cedulado": condicion_cedulado,
        "nombre_madre": cliente.nombre_madre or "",
        "nombre_padre": cliente.nombre_padre or "",
        "lugar_nacimiento": cliente.lugar_nacimiento or "",

        # Domicilio
        "lugar_domicilio": cliente.lugar_domicilio or "",
        "calle_domicilio": cliente.calle_domicilio or "",
        "numeracion_domicilio": cliente.numeracion_domicilio or "",
        "provincia": cliente.provincia or "",
        "canton": cliente.canton or "",
        "parroquia": cliente.parroquia or "",
        "otras_direcciones": cliente.otras_direcciones or [],

        # Educación
        "instruccion": cliente.instruccion or "",
        "profesion": cliente.profesion or "",
        "tipo_sangre": cliente.tipo_sangre or "",

        # Licencia
        "licencia_tipo": cliente.licencia_tipo or "",
        "licencia_fecha_desde": _iso(cliente.licencia_fecha_desde),
        "licencia_fecha_hasta": _iso(cliente.licencia_fecha_hasta),
        "licencia_puntos": cliente.licencia_puntos or "",
        "licencia_infracciones": licencia_infracciones,
        "licencia_restricciones": cliente.licencia_restricciones or "",
        "licencia_todos": cliente.licencia_todos or [],

        # Discapacidad
        "carnet_conadis": cliente.carnet_conadis or "",
        "discapacidad": cliente.discapacidad,
        "porcentaje_discapacidad": cliente.porcentaje_discapacidad or "",

        # RUC / SRI
        "razon_social": cliente.razon_social or "",
        "estado_contribuyente_ruc": cliente.estado_contribuyente_ruc or "",
        "actividad_economica_principal": cliente.actividad_economica_principal or "",
        "tipo_contribuyente": cliente.tipo_contribuyente or "",
        "regimen": cliente.regimen or "",
        "obligado_llevar_contabilidad": cliente.obligado_llevar_contabilidad or "",
        "agente_retencion": cliente.agente_retencion or "",
        "contribuyente_especial": cliente.contribuyente_especial or "",
        "representantes_legales": cliente.representantes_legales or [],
        "establecimientos": cliente.establecimientos or [],

        # Control
        "datos_full_consultados": cliente.datos_full_consultados,
        "fecha_ultima_consulta_api": _iso(cliente.fecha_ultima_consulta_api),
        # Datos registrales que pueden no existir como columnas en Cliente.
        "fecha_inscripcion_genero": texto_limpio(raw.get("fechaInscripcionGenero")),
        "lugar_inscripcion_genero": texto_limpio(raw.get("lugarInscripcionGenero")),
    }


# =========================================================
# CLIENTE: EXTRAER DATOS IMPORTANTES DE RESPUESTA API
# =========================================================

def extraer_datos_cliente_api(data, es_ruc=False):
    """Mapea información externa al formato ya utilizado por MAO."""
    if es_ruc:
        establecimientos = data.get("establecimientos") or []
        matriz = next(
            (
                item for item in establecimientos
                if isinstance(item, dict)
                and str(item.get("matriz", "")).strip().upper() in ("SI", "SÍ", "TRUE", "1")
            ),
            None,
        )
        return {
            "nombre_completo": texto_limpio(data.get("razonSocial")),
            "telefono": "",
            "telefono_secundario": "",
            "telefono_trabajo": "",
            "email": "",
            "direccion": texto_limpio(matriz.get("direccionCompleta")) if matriz else "",
        }

    # La respuesta 2026 de cédula es plana. Se tolera el formato histórico
    # para compatibilidad con los registros que ya existen en MAO.
    persona = data.get("persona") or data
    if not isinstance(persona, dict):
        persona = data
    direccion = persona.get("direccion") or {}
    if not isinstance(direccion, dict):
        direccion = {}
    partes = [
        texto_limpio(direccion.get("domicilio") or data.get("lugarDomicilio")),
        texto_limpio(direccion.get("calle") or data.get("calleDomicilio")),
        texto_limpio(direccion.get("numeroCasa") or data.get("numeracionDomicilio")),
    ]
    return {
        "nombre_completo": texto_limpio(persona.get("nombre") or data.get("nombre")),
        # La consulta básica documentada NO devuelve teléfono ni correo.
        "telefono": texto_limpio(persona.get("celular")),
        "telefono_secundario": "",
        "telefono_trabajo": "",
        "email": texto_limpio(persona.get("email")),
        "direccion": " / ".join(parte for parte in partes if parte),
    }


# =========================================================
# CLIENTE: COMPARAR MAO VS API
# =========================================================

def comparar_cliente_con_api(cliente, datos_api):
    """Devuelve diferencias útiles sin aplicar cambios."""
    campos = {
        "nombre_completo": "Nombre",
        "telefono": "Celular",
        "telefono_secundario": "Celular secundario",
        "telefono_trabajo": "Teléfono trabajo",
        "email": "Correo",
        "direccion": "Dirección",
    }

    diferencias = []

    for campo, etiqueta in campos.items():
        valor_api = datos_api.get(campo)
        if valor_vacio(valor_api):
            continue

        valor_actual = getattr(cliente, campo, "")
        actual = texto_limpio(valor_actual)
        api = texto_limpio(valor_api)

        iguales = (
            actual.lower() == api.lower()
            if campo == "email"
            else actual.upper() == api.upper()
        )

        if not iguales:
            diferencias.append({
                "campo": campo,
                "etiqueta": etiqueta,
                "actual": actual,
                "api": api,
                "actual_vacio": valor_vacio(valor_actual),
            })

    return diferencias


# =========================================================
# API: CONSULTAR CLIENTE POR CÉDULA / RUC
# =========================================================

APICONSULT_URL = "https://apiconsult.zampisoft.com/api/consultar"


class ApiConsultError(Exception):
    """Error controlado que nunca incluye el token ni datos personales."""

    def __init__(self, mensaje, http_status=502, codigo_api=None, retry_after=None):
        super().__init__(mensaje)
        self.http_status = http_status
        self.codigo_api = codigo_api
        self.retry_after = retry_after


def validar_identificacion_api(identificacion):
    """Valida formato y, para cédula ecuatoriana, dígito verificador."""
    if not isinstance(identificacion, str):
        return False
    if not identificacion.isascii() or not identificacion.isdigit():
        return False
    if len(identificacion) == 13:
        # Para RUC hay distintos algoritmos según el tipo de contribuyente.
        # La comprobación definitiva la realiza ApiConsult.
        return True
    if len(identificacion) != 10:
        return False
    provincia = int(identificacion[:2])
    if provincia not in range(1, 25) and provincia != 30:
        return False
    if int(identificacion[2]) > 5:
        return False
    total = 0
    for posicion, digito in enumerate(identificacion[:9]):
        valor = int(digito) * (2 if posicion % 2 == 0 else 1)
        total += valor - 9 if valor > 9 else valor
    return (10 - total % 10) % 10 == int(identificacion[9])


def consultar_zampisoft(identificacion):
    """
    Única salida hacia ZampiSoft para las vistas de MAO.
    No hace reintentos: cada nueva consulta puede generar un cobro.
    """
    identificacion = str(identificacion or "").strip()
    if not validar_identificacion_api(identificacion):
        raise ApiConsultError(
            "Identificación inválida. Verifica cédula o RUC.",
            http_status=400,
        )

    token = str(getattr(settings, "CEDULA_API_TOKEN", "") or "").strip()
    if not token:
        raise ApiConsultError("Falta configurar CEDULA_API_TOKEN en Django.", 503)

    try:
        respuesta = requests.post(
            APICONSULT_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"identificacion": identificacion},
            timeout=(5, 20),
        )
    except requests.Timeout as exc:
        raise ApiConsultError(
            "Se agotó el tiempo de espera. Revisa antes de repetir la consulta.", 504
        ) from exc
    except requests.RequestException as exc:
        raise ApiConsultError(
            "No fue posible conectar con ApiConsult. No se efectuará otro intento automático.",
            502,
        ) from exc

    errores = {
        400: "Identificación ausente o inválida.",
        401: "Token de ApiConsult ausente o incorrecto.",
        402: "Saldo insuficiente en ApiConsult.",
        403: "La clave no tiene permiso de Identificaciones o la cuenta está inactiva.",
        404: "No se encontró la identificación en la fuente.",
        408: "La fuente agotó el tiempo de espera.",
        429: "Límite de consultas. Respeta Retry-After antes de volver a consultar.",
        500: "Error temporal de ApiConsult.",
        502: "Error temporal de la fuente de datos.",
        503: "La fuente de identificación no está disponible temporalmente.",
    }
    if respuesta.status_code != 200:
        raise ApiConsultError(
            errores.get(respuesta.status_code, "No se pudo completar la consulta."),
            http_status=(
                respuesta.status_code
                if respuesta.status_code in (400, 402, 403, 404, 429, 503)
                else 502
            ),
            codigo_api=respuesta.status_code,
            retry_after=respuesta.headers.get("Retry-After"),
        )

    try:
        data = respuesta.json()
    except ValueError as exc:
        raise ApiConsultError("La API devolvió una respuesta que no es JSON.") from exc

    if not isinstance(data, dict):
        raise ApiConsultError("La API devolvió un formato de respuesta inesperado.")
    if data.get("success") is False or data.get("error"):
        # No se reintenta: el proveedor ya procesó la solicitud.
        raise ApiConsultError(
            texto_limpio(data.get("error") or data.get("message"))
            or "La API rechazó la identificación.",
            http_status=422,
        )

    # La nueva documentación incluye la respuesta de cédula. La de RUC
    # se mantiene con el contrato ya usado en este proyecto.
    es_ruc = len(identificacion) == 13
    campo_nombre = "razonSocial" if es_ruc else "nombre"
    if not texto_limpio(data.get(campo_nombre)):
        raise ApiConsultError(
            "La API no devolvió los datos mínimos esperados para "
            + ("RUC" if es_ruc else "cédula")
            + ". No se guardó información incompleta.",
            http_status=502,
        )

    identificacion_recibida = data.get("numeroRuc" if es_ruc else "cedula")
    if identificacion_recibida and str(identificacion_recibida) != identificacion:
        raise ApiConsultError("La API devolvió una identificación diferente.")

    return data


def aplicar_datos_zampisoft(cliente, data, es_ruc=False):
    """Usa los métodos del modelo actual: llena vacíos sin pisar datos manuales."""
    if es_ruc:
        cliente.cargar_desde_api_ruc(data, sobrescribir=False)
    else:
        # La respuesta plana 2026 es básica; NO marcar full=True.
        # El modelo Cliente existente acepta directamente los campos planos.
        cliente.cargar_desde_api_persona(data, full=False, sobrescribir=False)
    cliente.fecha_ultima_consulta_api = timezone.now()
    return cliente


def _cache_identificacion_disponible(cliente, es_ruc):
    """Sólo conserva caché de una consulta anterior realmente válida."""
    if not cliente:
        return False
    raw = cliente.datos_api_originales or {}
    if not isinstance(raw, dict):
        return False
    if es_ruc:
        return bool(texto_limpio(raw.get("razonSocial")))
    persona = raw.get("persona") or {}
    if not isinstance(persona, dict):
        persona = {}
    return bool(texto_limpio(raw.get("nombre") or persona.get("nombre")))


@login_required
def consultar_cedula_api(request):
    """Mantiene los mismos parámetros y JSON usados por los formularios MAO."""
    identificacion = request.GET.get("cedula", "").strip()
    forzar_refresh = parametro_booleano(request, "refresh", False)
    es_ruc = len(identificacion) == 13

    if not validar_identificacion_api(identificacion):
        return JsonResponse(
            {"exito": False, "error": "Cédula/RUC inválido. Revisa sus dígitos."},
            status=400,
        )

    cliente = Cliente.objects.filter(identificacion=identificacion).first()

    # Una consulta válida ya guardada se reutiliza sin costo; para forzar una
    # consulta NUEVA el usuario debe solicitar expresamente refresh=true.
    if cliente and not forzar_refresh and _cache_identificacion_disponible(cliente, es_ruc):
        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "cliente": serializar_cliente(cliente),
            "datos_api": {},
            "cambios_sugeridos": [],
        })

    try:
        data = consultar_zampisoft(identificacion)
    except ApiConsultError as exc:
        respuesta_error = {
            "exito": False,
            "error": str(exc),
            "codigo_api": exc.codigo_api,
        }
        if exc.retry_after:
            respuesta_error["retry_after"] = exc.retry_after
        return JsonResponse(respuesta_error, status=exc.http_status)

    datos_detectados = extraer_datos_cliente_api(data, es_ruc=es_ruc)
    cliente_era_nuevo = cliente is None

    try:
        with transaction.atomic():
            if cliente:
                cliente = Cliente.objects.select_for_update().get(pk=cliente.pk)
            else:
                cliente = Cliente(identificacion=identificacion)

            # Respetar cualquier dato que el usuario haya escrito manualmente.
            aplicar_datos_zampisoft(cliente, data, es_ruc=es_ruc)
            cliente.save()

        cambios_sugeridos = comparar_cliente_con_api(cliente, datos_detectados)
        origen = "api_nuevo" if cliente_era_nuevo else (
            "api_refrescada" if forzar_refresh else "api"
        )
        return JsonResponse({
            "exito": True,
            "origen": origen,
            "cliente": serializar_cliente(cliente),
            "datos_api": datos_detectados,
            "cambios_sugeridos": cambios_sugeridos,
        })
    except Exception:
        # No mostrar excepciones con datos internos al navegador.
        return JsonResponse(
            {"exito": False, "error": "No se pudieron guardar los datos recibidos."},
            status=500,
        )


# =========================================================
# API: EDITAR DATOS DEL MISMO CLIENTE
# =========================================================

@login_required
@require_POST
def actualizar_datos_cliente_api(request, cliente_id):
    """
    Actualización manual y explícita de datos de contacto.
    No modifica identificación, nombre ni tipo_documento.
    """
    try:
        content_type = (request.content_type or "").lower()
        payload = (
            json.loads(request.body or b"{}")
            if "application/json" in content_type
            else request.POST
        )
    except Exception:
        return JsonResponse(
            {"exito": False, "error": "Datos enviados inválidos."},
            status=400,
        )

    campos_permitidos = {
        "telefono",
        "telefono_secundario",
        "telefono_trabajo",
        "email",
        "direccion",
    }

    try:
        with transaction.atomic():
            cliente = (
                Cliente.objects
                .select_for_update()
                .filter(pk=cliente_id)
                .first()
            )

            if not cliente:
                return JsonResponse(
                    {"exito": False, "error": "El cliente no existe."},
                    status=404,
                )

            hubo_cambios = False

            for campo in campos_permitidos:
                if campo not in payload:
                    continue

                valor = payload.get(campo)
                valor = "" if valor is None else valor
                if isinstance(valor, str):
                    valor = valor.strip()

                if texto_limpio(getattr(cliente, campo, "")) != texto_limpio(valor):
                    setattr(cliente, campo, valor)
                    hubo_cambios = True

            if hubo_cambios:
                cliente.save()

        return JsonResponse({
            "exito": True,
            "actualizado": hubo_cambios,
            "cliente": serializar_cliente(cliente),
        })

    except Exception as e:
        return JsonResponse(
            {"exito": False, "error": str(e)},
            status=400,
        )


# =========================================================
# API: BÚSQUEDA REPUESTOS
# =========================================================

@login_required
def api_buscar_repuestos_ot(request):

    query = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    sucursal_activa = (
        obtener_sucursal_activa(
            request
        )
    )

    if (
        not query
        or not sucursal_activa
    ):

        return JsonResponse({
            "resultados": []
        })

    terminos = (
        query.split()
    )

    repuestos = (
        CodigoProducto.objects
        .filter(
            activo=True,
            producto__activo=True,
        )
        .select_related(
            "producto__categoria",
            "marca",
        )
    )

    for termino in terminos:

        if (
            len(
                termino
            ) <= 2
            and len(
                terminos
            ) > 1
        ):

            continue

        repuestos = repuestos.filter(

            Q(
                producto__nombre_base__icontains=termino
            )
            |
            Q(
                nombre_comercial__icontains=termino
            )
            |
            Q(
                marca__nombre__icontains=termino
            )
            |
            Q(
                producto__categoria__nombre__icontains=termino
            )
            |
            Q(
                codigo__icontains=termino
            )
            |
            Q(
                codigo_barras__icontains=termino
            )
            |
            Q(
                producto__valores_atributos__valor__icontains=termino
            )
        )

    data = []

    for item in (
        repuestos
        .distinct()[:20]
    ):

        stock_obj = (
            StockSucursal.objects
            .filter(
                codigo_producto=item,
                sucursal=sucursal_activa,
            )
            .first()
        )

        cat = (
            f"[{item.producto.categoria.nombre}] "
            if item.producto.categoria
            else ""
        )

        desc_final = (
            f"{cat}"
            f"{item.producto.nombre_base} "
            f"{item.nombre_comercial or ''} "
            f"- {item.marca.nombre}"
        )

        data.append({

            "id": (
                item.id
            ),

            "codigo": (
                item.codigo
            ),

            "descripcion": (
                desc_final.strip()
            ),

            "p_u": str(
                item.precio_venta
                or "0.00"
            ),

            "stock": (
                stock_obj.cantidad
                if stock_obj
                else 0
            ),
        })

    return JsonResponse({
        "resultados": data
    })


# =========================================================
# API: BÚSQUEDA SERVICIOS PARA OT
# =========================================================

@login_required
def api_buscar_servicios_ot(request):

    query = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    categoria = (
        request.GET
        .get(
            "categoria",
            "moi",
        )
        .strip()
        .lower()
    )

    variante_precio = (
        request.GET
        .get(
            "variante_precio",
            "NORMAL",
        )
        .strip()
        .upper()
        or "NORMAL"
    )

    sucursal_activa = (
        obtener_sucursal_activa(
            request
        )
    )

    if (
        not query
        or not sucursal_activa
    ):

        return JsonResponse({
            "resultados": []
        })

    mapa_categorias = {
        "moi": "MEC",
        "moe": "EXT",
        "pin": "PIN",
        "end": "END",
        "ele": "ELE",
    }

    categoria_db = (
        mapa_categorias.get(
            categoria,
            "MEC",
        )
    )

    terminos = (
        query.split()
    )

    servicios = (
        ServicioCatalogo.objects
        .filter(
            activo=True,
            categoria=categoria_db,
        )
        .prefetch_related(
            "procedimientos"
        )
    )

    for termino in terminos:

        if (
            len(
                termino
            ) <= 2
            and len(
                terminos
            ) > 1
        ):

            continue

        servicios = servicios.filter(

            Q(
                codigo__icontains=termino
            )
            |
            Q(
                descripcion__icontains=termino
            )
            |
            Q(
                categoria__icontains=termino
            )
            |
            Q(
                procedimientos__descripcion__icontains=termino
            )
        )

    data = []

    for item in (
        servicios
        .distinct()[:20]
    ):

        precio = (
            item.obtener_precio_inteligente(
                sucursal=sucursal_activa,
                variante=variante_precio,
            )
        )

        procedimientos = [

            {
                "id": proc.id,
                "descripcion": (
                    proc.descripcion
                ),
                "orden": (
                    proc.orden
                ),
            }

            for proc
            in item.procedimientos.all()

            if getattr(
                proc,
                "visible_en_ot",
                True,
            )
        ]

        data.append({

            "id": (
                item.id
            ),

            "codigo": (
                item.codigo
            ),

            "descripcion": (
                item.descripcion
            ),

            "descripcion_display": (
                f"[{item.get_categoria_display()}] "
                f"{item.descripcion}"
            ),

            "p_u": str(
                precio
                or "0.00"
            ),

            "precio_recomendado": str(
                precio
                or "0.00"
            ),

            "requiere_variante": (
                item.requiere_variante
            ),

            "variante_aplicada": (
                variante_precio
            ),

            "procedimientos": (
                procedimientos
            ),

            "stock": 0,
        })

    return JsonResponse({
        "resultados": data
    })


# =========================================================
# API: AUTOCOMPLETADO DE PLACA PARA RECEPCIÓN
# =========================================================

@login_required
def buscar_vehiculo_por_placa(request):
    placa = request.GET.get("placa", "").strip().upper()

    if not placa:
        return JsonResponse({"encontrado": False})

    expediente = (
        ExpedienteVehiculo.objects
        .filter(placa=placa)
        .order_by("-id")
        .first()
    )

    if not expediente or not expediente.cliente:
        return JsonResponse({"encontrado": False})

    cliente = expediente.cliente

    return JsonResponse({
        "encontrado": True,
        "vehiculo": expediente.vehiculo or "",
        "anio": expediente.anio_vehiculo or "",
        "cliente": {
            "id": cliente.id,
            "identificacion": _identificacion_valida_cliente(cliente),
            "nombre": cliente.nombre_completo or "",
            "telefono": cliente.telefono or "",
            "telefono_secundario": cliente.telefono_secundario or "",
            "telefono_trabajo": cliente.telefono_trabajo or "",
            "email": cliente.email or "",
            "direccion": cliente.direccion or "",
        },
    })


# =========================================================
# API: BÚSQUEDA RECOMENDACIONES TÉCNICAS
# =========================================================

@login_required
def api_buscar_recomendaciones_ot(request):

    query = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    recomendaciones = (
        PlantillaRecomendacion.objects
        .filter(
            activo=True
        )
        .order_by(
            "orden_visual",
            "titulo",
        )
    )

    if query:

        terminos = (
            query.split()
        )

        for termino in terminos:

            recomendaciones = (
                recomendaciones
                .filter(
                    Q(
                        titulo__icontains=termino
                    )
                    |
                    Q(
                        texto__icontains=termino
                    )
                )
            )

    data = []

    for item in (
        recomendaciones
        .distinct()[:20]
    ):

        data.append({

            "id": (
                item.id
            ),

            "titulo": (
                item.titulo
            ),

            "texto": (
                item.texto
            ),
        })

    return JsonResponse({
        "resultados": data
    })