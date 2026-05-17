# ordenes_de_trabajo/views/api.py
PLACA_API_USERNAME = "SalvadorOrtega"
CEDULA_API_TOKEN = "yKGE-7wqa-kwNp-3AvU"

GEMINI_API_KEY = "AIzaSyAA5PGQW2XAGoYGzjFjeo8T97fxgy44678"


import json
import requests
import xml.etree.ElementTree as ET
from google import genai
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from servicios.models import ServicioCatalogo
from inventario.models import CodigoProducto, StockSucursal
from .utils import obtener_sucursal_activa
from ..models import Cliente, ExpedienteVehiculo




# =========================================================
# IA: CLASIFICAR VEHÍCULO
# =========================================================
import json
import re
from google import genai


def limpiar_json_ia(texto):
    if not texto:
        return "{}"

    texto = texto.strip()

    # Quitar bloques tipo ```json ... ```
    texto = texto.replace("```json", "")
    texto = texto.replace("```", "")
    texto = texto.strip()

    # Intentar extraer solo el JSON entre llaves
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        return match.group(0).strip()

    return texto


def clasificar_vehiculo_con_ia(
    marca,
    modelo,
    anio="",
    descripcion=""
):
    tipos_validos = {
        "NO_APLICA",
        "AUTO",
        "AUTO_3P",
        "AUTO_5P",
        "SUV_3P",
        "SUV_5P",
        "CAMIONETA_CS",
        "CAMIONETA_DC",
        "CAMIONETA_GRANDE",
    }

    gamas_validas = {
        "NO_APLICA",
        "ECONOMICA",
        "MEDIA",
        "MEDIA_ALTA",
        "ALTA",
        "PREMIUM",
        "LUJO",
        "COMERCIAL",
        "DEPORTIVA",
    }

    resultado_fallback = {
        "tipo_tarifa_vehiculo": "NO_APLICA",
        "gama_vehiculo": "NO_APLICA",
        "confianza": 0.0,
        "motivo": "No se pudo clasificar con IA.",
    }

    print("\n========== INICIO CLASIFICACIÓN IA ==========")
    print("MARCA RECIBIDA:", marca)
    print("MODELO RECIBIDO:", modelo)
    print("AÑO RECIBIDO:", anio)
    print("DESCRIPCIÓN RECIBIDA:", descripcion)

    try:
        if not GEMINI_API_KEY:
            print("ADVERTENCIA: GEMINI_API_KEY no configurada.")
            resultado_fallback["motivo"] = "GEMINI_API_KEY no configurada."
            return resultado_fallback

        marca = str(marca or "").strip().upper()
        modelo = str(modelo or "").strip().upper()
        anio = str(anio or "").strip()
        descripcion = str(descripcion or "").strip().upper()

        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = f"""
Devuelve SOLO JSON válido. No uses markdown. No expliques nada fuera del JSON.

Clasifica este vehículo automotriz para un taller automotriz en Ecuador.

Datos:
Marca: {marca}
Modelo: {modelo}
Año: {anio}
Descripción: {descripcion}

REGLAS:

tipo_tarifa_vehiculo debe ser SOLO uno de:
- NO_APLICA
- AUTO
- AUTO_3P
- AUTO_5P
- SUV_3P
- SUV_5P
- CAMIONETA_CS
- CAMIONETA_DC
- CAMIONETA_GRANDE

gama_vehiculo debe ser SOLO uno de:
- NO_APLICA
- ECONOMICA
- MEDIA
- MEDIA_ALTA
- ALTA
- PREMIUM
- LUJO
- COMERCIAL
- DEPORTIVA

Criterio general:
- AUTO_3P: autos compactos/hatchback/coupé de 3 puertas.
- AUTO_5P: sedanes, hatchbacks o autos de 5 puertas.
- SUV_3P: SUV todoterreno pequeño de 3 puertas, ejemplo Grand Vitara 3P.
- SUV_5P: SUV/crossover familiar de 5 puertas.
- CAMIONETA_CS: pickup cabina sencilla.
- CAMIONETA_DC: pickup doble cabina.
- CAMIONETA_GRANDE: pickup grande tipo F150, RAM, Silverado, Tundra.
- COMERCIAL: vans, camiones, furgones o vehículos de trabajo.
- NO_APLICA: si no hay información suficiente.

Formato obligatorio exacto:

{{
  "tipo_tarifa_vehiculo": "NO_APLICA",
  "gama_vehiculo": "NO_APLICA",
  "confianza": 0.0,
  "motivo": null
}}
"""

        print("\n========== ENVIANDO A GEMINI ==========")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        texto_respuesta = getattr(response, "text", "") or ""

        print("\n========== RESPUESTA RAW GEMINI ==========")
        print(texto_respuesta)

        texto_limpio = limpiar_json_ia(texto_respuesta)

        print("\n========== TEXTO LIMPIO ==========")
        print(texto_limpio)

        data = json.loads(texto_limpio)

        print("\n========== JSON PARSEADO ==========")
        print(data)

        tipo_tarifa = str(
            data.get("tipo_tarifa_vehiculo") or "NO_APLICA"
        ).strip().upper()

        gama = str(
            data.get("gama_vehiculo") or "NO_APLICA"
        ).strip().upper()

        if tipo_tarifa not in tipos_validos:
            print("ADVERTENCIA: tipo_tarifa inválido:", tipo_tarifa)
            tipo_tarifa = "NO_APLICA"

        if gama not in gamas_validas:
            print("ADVERTENCIA: gama inválida:", gama)
            gama = "NO_APLICA"

        try:
            confianza = float(data.get("confianza", 0.0) or 0.0)
        except Exception:
            confianza = 0.0

        if confianza < 0:
            confianza = 0.0
        if confianza > 1:
            confianza = 1.0

        resultado = {
            "tipo_tarifa_vehiculo": tipo_tarifa,
            "gama_vehiculo": gama,
            "confianza": confianza,
            "motivo": data.get("motivo"),
        }

        print("\n========== RESULTADO FINAL IA ==========")
        print("TIPO TARIFA:", resultado["tipo_tarifa_vehiculo"])
        print("GAMA:", resultado["gama_vehiculo"])
        print("CONFIANZA:", resultado["confianza"])
        print("MOTIVO:", resultado["motivo"])
        print("========================================\n")

        return resultado

    except json.JSONDecodeError as e:
        print("\n========== ERROR JSON IA ==========")
        print("ERROR:", str(e))
        print("===================================\n")

        return {
            "tipo_tarifa_vehiculo": "NO_APLICA",
            "gama_vehiculo": "NO_APLICA",
            "confianza": 0.0,
            "motivo": f"Respuesta IA no era JSON válido: {str(e)}",
        }

    except Exception as e:
        print("\n========== ERROR CLASIFICACIÓN IA ==========")
        print("ERROR:", str(e))
        print("===========================================\n")

        return {
            "tipo_tarifa_vehiculo": "NO_APLICA",
            "gama_vehiculo": "NO_APLICA",
            "confianza": 0.0,
            "motivo": str(e),
        }
# =========================================================
# API: CONSULTAR PLACA CON CACHE (CORREGIDA)
# =========================================================
import json
import requests
import xml.etree.ElementTree as ET
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

# =========================================================
# API: CONSULTAR PLACA CON CACHE (CORREGIDA)
# =========================================================
@login_required
def consultar_regcheck(request):
    placa = request.GET.get("placa", "").strip().upper()

    if not placa:
        return JsonResponse({"exito": False, "error": "Placa vacía"})

    # 1. Buscar primero en la base de datos local
    vehiculo_local = ExpedienteVehiculo.objects.filter(placa=placa).first()

    if vehiculo_local:
        cliente = vehiculo_local.cliente
        # Buscamos la última Orden de Trabajo para sacar tarifa, gama, color y km
        ultima_ot = vehiculo_local.ordenes.order_by('-fecha_ingreso').first()
        
        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "placa": placa,
            "vehiculo": vehiculo_local.vehiculo or "",
            "anio": vehiculo_local.anio_vehiculo or "",
            "color": ultima_ot.color if ultima_ot else "",
            "kilometraje": ultima_ot.kilometraje if ultima_ot else "",
            "identificacion": cliente.identificacion if cliente else "",
            "nombre_completo": cliente.nombre_completo if cliente else "",
            "telefono": cliente.telefono if cliente else "",
            "email": cliente.email if cliente else "",
            "direccion": cliente.direccion if cliente else "",
            "tipo_tarifa_vehiculo": ultima_ot.tipo_tarifa_vehiculo if ultima_ot else "NO_APLICA",
            "gama_vehiculo": ultima_ot.gama_vehiculo if ultima_ot else "NO_APLICA",
        })

    # 2. Consultar a la API de PlacaAPI.ec
    url = (
        "https://www.placaapi.ec/API/reg.asmx/"
        f"CheckEcuador?RegistrationNumber={placa}"
        f"&username={PLACA_API_USERNAME}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        respuesta = requests.get(url, headers=headers, timeout=15)

        if respuesta.status_code != 200:
            return JsonResponse({"exito": False, "error": f"Error API: {respuesta.status_code}"})

        # Parsear el XML ignorando namespaces
        root = ET.fromstring(respuesta.content)
        json_text = None
        for elem in root.iter():
            if elem.tag.endswith('vehicleJson'):
                json_text = elem.text
                break

        if not json_text:
            return JsonResponse({"exito": False, "error": "Vehículo no encontrado en ANT/SRI."})

        datos_auto = json.loads(json_text)

        def obtener_valor(campo_primario, campo_secundario):
            obj = datos_auto.get(campo_primario) or datos_auto.get(campo_secundario)
            if isinstance(obj, dict):
                return obj.get("CurrentTextValue", "")
            return str(obj or "")

        marca = obtener_valor("MakeDescription", "CarMake")
        if marca.upper() == "VW": marca = "VOLKSWAGEN"
        modelo = obtener_valor("ModelDescription", "CarModel")
        
        anio = datos_auto.get("Year", "")
        descripcion = datos_auto.get("Description", "")
        vehiculo_completo = f"{marca} {modelo}".strip()

        # 3. Clasificación con Inteligencia Artificial
        clasificacion = clasificar_vehiculo_con_ia(
            marca=marca, modelo=modelo, anio=anio, descripcion=descripcion
        )

        # 4. Guardamos en caché local (Solo campos válidos)
        expediente, creado = ExpedienteVehiculo.objects.update_or_create(
            placa=placa,
            defaults={
                "vehiculo": vehiculo_completo.upper(),
                "anio_vehiculo": int(anio) if str(anio).isdigit() else None,
            }
        )

        return JsonResponse({
            "exito": True,
            "origen": "api_guardada",
            "placa": placa,
            "vehiculo": expediente.vehiculo or "",
            "marca": marca,
            "modelo": modelo,
            "anio": expediente.anio_vehiculo or "",
            "descripcion": descripcion,
            "tipo_tarifa_vehiculo": clasificacion["tipo_tarifa_vehiculo"],
            "gama_vehiculo": clasificacion["gama_vehiculo"],
            "confianza": clasificacion["confianza"],
            "motivo": clasificacion["motivo"],
        })

    except Exception as e:
        # Volvemos a un mensaje genérico por seguridad
        return JsonResponse({"exito": False, "error": "Ocurrió un error al consultar el vehículo."})
# =========================================================
# API: CONSULTAR CÉDULA / RUC CON CACHE
# =========================================================

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone

import requests


# =========================================================
# SERIALIZADOR
# =========================================================
def serializar_cliente(cliente):

    return {

        "identificacion": cliente.identificacion,
        "tipo_documento": cliente.tipo_documento,
        "nombre_completo": cliente.nombre_completo or "",

        # ======================================
        # CONTACTO
        # ======================================
        "telefono": cliente.telefono or "",
        "telefono_secundario": cliente.telefono_secundario or "",
        "telefono_trabajo": cliente.telefono_trabajo or "",
        "email": cliente.email or "",
        "direccion": cliente.direccion or "",

        # ======================================
        # PERSONALES
        # ======================================
        "genero": cliente.genero or "",
        "sexo": cliente.sexo or "",

        "fecha_nacimiento":
            cliente.fecha_nacimiento.isoformat()
            if cliente.fecha_nacimiento else "",

        "fecha_cedulacion":
            cliente.fecha_cedulacion.isoformat()
            if cliente.fecha_cedulacion else "",

        "estado_civil": cliente.estado_civil or "",
        "conyuge": cliente.conyuge or "",
        "nacionalidad": cliente.nacionalidad or "",

        # ======================================
        # PADRES / NACIMIENTO
        # ======================================
        "nombre_madre": cliente.nombre_madre or "",
        "nombre_padre": cliente.nombre_padre or "",

        "lugar_nacimiento":
            cliente.lugar_nacimiento or "",

        # ======================================
        # DOMICILIO
        # ======================================
        "lugar_domicilio":
            cliente.lugar_domicilio or "",

        "calle_domicilio":
            cliente.calle_domicilio or "",

        "numeracion_domicilio":
            cliente.numeracion_domicilio or "",

        "provincia": cliente.provincia or "",
        "canton": cliente.canton or "",
        "parroquia": cliente.parroquia or "",

        # ======================================
        # EDUCACIÓN
        # ======================================
        "instruccion": cliente.instruccion or "",
        "profesion": cliente.profesion or "",
        "tipo_sangre": cliente.tipo_sangre or "",

        # ======================================
        # LICENCIA
        # ======================================
        "licencia_tipo":
            cliente.licencia_tipo or "",

        "licencia_fecha_desde":
            cliente.licencia_fecha_desde.isoformat()
            if cliente.licencia_fecha_desde else "",

        "licencia_fecha_hasta":
            cliente.licencia_fecha_hasta.isoformat()
            if cliente.licencia_fecha_hasta else "",

        "licencia_puntos":
            cliente.licencia_puntos or "",

        "licencia_restricciones":
            cliente.licencia_restricciones or "",

        # ======================================
        # RUC / SRI
        # ======================================
        "razon_social":
            cliente.razon_social or "",

        "estado_contribuyente_ruc":
            cliente.estado_contribuyente_ruc or "",

        "actividad_economica_principal":
            cliente.actividad_economica_principal or "",

        "tipo_contribuyente":
            cliente.tipo_contribuyente or "",

        "regimen":
            cliente.regimen or "",

        "obligado_llevar_contabilidad":
            cliente.obligado_llevar_contabilidad or "",

        "agente_retencion":
            cliente.agente_retencion or "",

        "contribuyente_especial":
            cliente.contribuyente_especial or "",

        "representantes_legales":
            cliente.representantes_legales or [],

        "establecimientos":
            cliente.establecimientos or [],

        # ======================================
        # CONTROL
        # ======================================
        "datos_full_consultados":
            cliente.datos_full_consultados,

        "fecha_ultima_consulta_api":
            cliente.fecha_ultima_consulta_api.isoformat()
            if cliente.fecha_ultima_consulta_api else "",
    }


# =========================================================
# API CONSULTAR
# =========================================================
@login_required
def consultar_cedula_api(request):

    identificacion = request.GET.get(
        "cedula",
        ""
    ).strip()

    # ======================================
    # VALIDACIÓN
    # ======================================
    if (
        not identificacion
        or not identificacion.isdigit()
        or len(identificacion) not in [10, 13]
    ):

        return JsonResponse({
            "exito": False,
            "error":
                "Identificación inválida. "
                "Debe tener 10 o 13 dígitos."
        })

    es_ruc = len(identificacion) == 13

    solicita_full = (
        request.GET
        .get("full", "false")
        .strip()
        .lower()
        == "true"
    )

    # ======================================
    # BUSCAR EN CACHE LOCAL
    # ======================================
    cliente = Cliente.objects.filter(
        identificacion=identificacion
    ).first()

    # ======================================
    # SI EXISTE Y NO NECESITA FULL
    # ======================================
    if (
        cliente
        and (
            not solicita_full
            or cliente.datos_full_consultados
        )
    ):

        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "cliente": serializar_cliente(cliente),
        })

    # ======================================
    # URL API EXTERNA
    # ======================================
    url = (
        "https://apiconsult.zampisoft.com/api/consultar"
        f"?identificacion={identificacion}"
        f"&token={CEDULA_API_TOKEN}"
    )

    # ======================================
    # FULL SOLO PARA CÉDULA
    # ======================================
    if not es_ruc and solicita_full:
        url += "&full=true"

    try:

        respuesta = requests.get(
            url,
            timeout=20,
            headers={
                "Accept": "application/json"
            }
        )

        if respuesta.status_code != 200:

            return JsonResponse({
                "exito": False,
                "error":
                    "No se encontraron resultados."
            })

        data = respuesta.json()

        if data.get("error"):

            return JsonResponse({
                "exito": False,
                "error": data.get("error")
            })

        # ======================================
        # SI NO EXISTE -> CREAR
        # ======================================
        if not cliente:
            cliente = Cliente()

        # ======================================
        # CARGAR DATOS PERSONA
        # ======================================
        if es_ruc:

            cliente.cargar_desde_api_ruc(data)

        else:

            cliente.cargar_desde_api_persona(
                data,
                full=solicita_full
            )

        # ======================================
        # CONTROL API
        # ======================================
        cliente.fecha_ultima_consulta_api = (
            timezone.now()
        )

        if solicita_full:
            cliente.datos_full_consultados = True

        # ======================================
        # GUARDAR
        # ======================================
        cliente.save()

        return JsonResponse({

            "exito": True,

            "origen":
                "api_actualizada"
                if cliente.id else
                "api_guardada",

            "cliente":
                serializar_cliente(cliente),

        })

    except requests.Timeout:

        return JsonResponse({
            "exito": False,
            "error":
                "La consulta demoró demasiado."
        })

    except requests.RequestException as e:

        return JsonResponse({
            "exito": False,
            "error":
                f"Error de conexión API: {str(e)}"
        })

    except Exception as e:

        return JsonResponse({
            "exito": False,
            "error":
                f"Error interno: {str(e)}"
        })
#fetch(`/api/consultar_cedula/?cedula=${cedula}`) 
#fetch(`/api/consultar_cedula/?cedula=${cedula}&full=true`)   
# =========================================================
# API: BÚSQUEDA REPUESTOS
# =========================================================
@login_required
def api_buscar_repuestos_ot(request):

    query = request.GET.get(
        'q',
        ''
    ).strip()

    sucursal_activa = obtener_sucursal_activa(request)

    if not query or not sucursal_activa:
        return JsonResponse({
            "resultados": []
        })

    terminos = query.split()

    repuestos = (
        CodigoProducto.objects
        .filter(
            activo=True,
            producto__activo=True
        )
        .select_related(
            'producto__categoria',
            'marca'
        )
    )

    for t in terminos:

        if len(t) <= 2 and len(terminos) > 1:
            continue

        repuestos = repuestos.filter(

            Q(producto__nombre_base__icontains=t) |
            Q(nombre_comercial__icontains=t) |
            Q(marca__nombre__icontains=t) |
            Q(producto__categoria__nombre__icontains=t) |
            Q(codigo__icontains=t) |
            Q(codigo_barras__icontains=t) |
            Q(producto__valores_atributos__valor__icontains=t)

        )

    data = []

    for item in repuestos.distinct()[:20]:

        stock_obj = (
            StockSucursal.objects
            .filter(
                codigo_producto=item,
                sucursal=sucursal_activa
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

            "id": item.id,

            "codigo": item.codigo,

            "descripcion": desc_final.strip(),

            "p_u": str(
                item.precio_venta or "0.00"
            ),

            "stock":
                stock_obj.cantidad
                if stock_obj
                else 0,
        })

    return JsonResponse({
        "resultados": data
    })

# =================================================================================
# API: BÚSQUEDA SERVICIOS PARA OT
# =================================================================================
@login_required
def api_buscar_servicios_ot(request):
    query = request.GET.get("q", "").strip()

    categoria = request.GET.get("categoria", "moi").strip().lower()

    tipo_tarifa_vehiculo = request.GET.get(
        "tipo_tarifa_vehiculo",
        "NO_APLICA"
    ).strip().upper() or "NO_APLICA"

    variante_precio = request.GET.get(
        "variante_precio",
        "NORMAL"
    ).strip().upper() or "NORMAL"

    sucursal_activa = obtener_sucursal_activa(request)

    if not query or not sucursal_activa:
        return JsonResponse({"resultados": []})

    mapa_categorias = {
        "moi": "MEC",
        "moe": "EXT",
        "pin": "PIN",
        "end": "END",
        "ele": "ELE",
    }

    categoria_db = mapa_categorias.get(categoria, "MEC")

    terminos = query.split()

    servicios = (
        ServicioCatalogo.objects
        .filter(
            activo=True,
            categoria=categoria_db
        )
        .prefetch_related("procedimientos")
    )

    for t in terminos:
        if len(t) <= 2 and len(terminos) > 1:
            continue

        servicios = servicios.filter(
            Q(codigo__icontains=t) |
            Q(descripcion__icontains=t) |
            Q(categoria__icontains=t) |
            Q(procedimientos__descripcion__icontains=t)
        )

    data = []

    for item in servicios.distinct()[:20]:
        precio = item.obtener_precio_inteligente(
            sucursal=sucursal_activa,
            tipo_tarifa=tipo_tarifa_vehiculo,
            variante=variante_precio,
        )

        procedimientos = [
            {
                "id": proc.id,
                "descripcion": proc.descripcion,
                "orden": proc.orden,
            }
            for proc in item.procedimientos.all()
            if getattr(proc, "visible_en_ot", True)
        ]

        data.append({
            "id": item.id,
            "codigo": item.codigo,
            "descripcion": item.descripcion,
            "descripcion_display": f"[{item.get_categoria_display()}] {item.descripcion}",
            "p_u": str(precio or "0.00"),
            "precio_recomendado": str(precio or "0.00"),
            "requiere_tipo_tarifa": item.requiere_tipo_tarifa,
            "requiere_variante": item.requiere_variante,
            "tipo_tarifa_aplicada": tipo_tarifa_vehiculo,
            "variante_aplicada": variante_precio,
            "procedimientos": procedimientos,
            "stock": 0,
        })

    return JsonResponse({"resultados": data})