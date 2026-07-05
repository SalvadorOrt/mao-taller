# ordenes_de_trabajo/views/api.py

from django.conf import settings

PLACA_API_USERNAME = settings.PLACA_API_USERNAME
CEDULA_API_TOKEN = settings.CEDULA_API_TOKEN
GEMINI_API_KEY = settings.GEMINI_API_KEY

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
from ..models import Cliente, ExpedienteVehiculo, PlantillaRecomendacion
from datetime import timedelta
from django.utils import timezone

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
        return JsonResponse({
            "exito": False,
            "error": "Placa vacía."
        })

    expediente = ExpedienteVehiculo.objects.filter(
        placa=placa
    ).first()

    if expediente:
        ultima_ot = expediente.ordenes.order_by("-fecha_ingreso").first()
        cliente = expediente.cliente
        
        # ====================================================
        # FILTRO DE CALIDAD PARA CÉDULAS MIGRADAS
        # ====================================================
        cedula_valida = ""
        if cliente and cliente.identificacion:
            ced_temp = str(cliente.identificacion).strip()
            # Si es solo números y tiene 10 o 13 dígitos, la pasamos
            if ced_temp.isdigit() and len(ced_temp) in [10, 13]:
                cedula_valida = ced_temp

        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "placa": expediente.placa,
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

            "identificacion": cedula_valida, # <--- AHORA PASA POR EL FILTRO
            "nombre_completo": cliente.nombre_completo if cliente else "",
            "telefono": cliente.telefono if cliente else "",
            "email": cliente.email if cliente else "",
            "direccion": cliente.direccion if cliente else "",

            "tipo_tarifa_vehiculo": (
                ultima_ot.tipo_tarifa_vehiculo
                if ultima_ot else "NO_APLICA"
            ),
            "gama_vehiculo": (
                ultima_ot.gama_vehiculo
                if ultima_ot else "NO_APLICA"
            ),
        })

    url = (
        "https://www.placaapi.ec/API/reg.asmx/CheckEcuador"
        f"?RegistrationNumber={placa}"
        f"&username={PLACA_API_USERNAME}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/xml,text/xml,*/*",
    }

    try:
        respuesta = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        if respuesta.status_code != 200:
            return JsonResponse({
                "exito": False,
                "error": f"Error API placa: {respuesta.status_code}"
            })

        root = ET.fromstring(respuesta.content)

        json_text = None

        for elem in root.iter():
            if elem.tag.endswith("vehicleJson"):
                json_text = elem.text
                break

        if not json_text:
            return JsonResponse({
                "exito": False,
                "error": "Vehículo no encontrado."
            })

        datos_auto = json.loads(json_text)

        def valor_api(campo):
            valor = datos_auto.get(campo)

            if isinstance(valor, dict):
                return valor.get("CurrentTextValue", "")

            return str(valor or "")

        marca = (
            valor_api("MakeDescription")
            or valor_api("CarMake")
        ).strip().upper()

        if marca == "VW":
            marca = "VOLKSWAGEN"

        modelo = (
            valor_api("ModelDescription")
            or valor_api("CarModel")
        ).strip().upper()

        descripcion = (
            datos_auto.get("Description")
            or f"{marca} {modelo}"
        ).strip().upper()

        anio = datos_auto.get("Year")
        tipo = datos_auto.get("Type", "")
        subtipo = datos_auto.get("Subtype", "")
        numero_chasis = datos_auto.get("VehicleIdentificationNumber", "")
        imagen_url = datos_auto.get("ImageUrl", "")

        clasificacion = clasificar_vehiculo_con_ia(
            marca=marca,
            modelo=modelo,
            anio=anio,
            descripcion=descripcion,
        )

        expediente = ExpedienteVehiculo(
            placa=placa
        )

        expediente.cargar_desde_api_placa(datos_auto)
        expediente.fecha_ultima_consulta_placa = timezone.now()
        expediente.save()

        return JsonResponse({
            "exito": True,
            "origen": "api_guardada",
            "placa": expediente.placa,
            "vehiculo": expediente.vehiculo or descripcion,
            "marca": expediente.marca_api or marca,
            "modelo": expediente.modelo_api or modelo,
            "descripcion": expediente.descripcion_api or descripcion,
            "anio": expediente.anio_vehiculo or "",
            "tipo": expediente.tipo_vehiculo_api or tipo,
            "subtipo": expediente.subtipo_vehiculo_api or subtipo,
            "numero_chasis": expediente.numero_chasis or numero_chasis or "",
            "imagen_url": expediente.imagen_url_api or imagen_url or "",

            "tipo_tarifa_vehiculo": clasificacion["tipo_tarifa_vehiculo"],
            "gama_vehiculo": clasificacion["gama_vehiculo"],
            "confianza": clasificacion["confianza"],
            "motivo": clasificacion["motivo"],
        })

    except Exception as e:
        return JsonResponse({
            "exito": False,
            "error": f"Error al consultar placa: {str(e)}"
        })
# =========================================================
# SERIALIZADOR
# =========================================================
def serializar_cliente(cliente):
    """Convierte el objeto Cliente a un diccionario compatible con JSON."""
    return {
        "identificacion": cliente.identificacion,
        "tipo_documento": cliente.tipo_documento,
        "nombre_completo": cliente.nombre_completo or "",
        
        # CONTACTO
        "telefono": cliente.telefono or "",
        "telefono_secundario": cliente.telefono_secundario or "",
        "telefono_trabajo": cliente.telefono_trabajo or "",
        "email": cliente.email or "",
        "direccion": cliente.direccion or "",

        # PERSONALES
        "genero": cliente.genero or "",
        "sexo": cliente.sexo or "",
        "fecha_nacimiento": cliente.fecha_nacimiento.isoformat() if cliente.fecha_nacimiento else "",
        "fecha_cedulacion": cliente.fecha_cedulacion.isoformat() if cliente.fecha_cedulacion else "",
        "estado_civil": cliente.estado_civil or "",
        "conyuge": cliente.conyuge or "",
        "nacionalidad": cliente.nacionalidad or "",
        "nombre_madre": cliente.nombre_madre or "",
        "nombre_padre": cliente.nombre_padre or "",
        "lugar_nacimiento": cliente.lugar_nacimiento or "",

        # DOMICILIO
        "lugar_domicilio": cliente.lugar_domicilio or "",
        "calle_domicilio": cliente.calle_domicilio or "",
        "numeracion_domicilio": cliente.numeracion_domicilio or "",
        "provincia": cliente.provincia or "",
        "canton": cliente.canton or "",
        "parroquia": cliente.parroquia or "",

        # EDUCACIÓN
        "instruccion": cliente.instruccion or "",
        "profesion": cliente.profesion or "",
        "tipo_sangre": cliente.tipo_sangre or "",

        # LICENCIA
        "licencia_tipo": cliente.licencia_tipo or "",
        "licencia_fecha_desde": cliente.licencia_fecha_desde.isoformat() if cliente.licencia_fecha_desde else "",
        "licencia_fecha_hasta": cliente.licencia_fecha_hasta.isoformat() if cliente.licencia_fecha_hasta else "",
        "licencia_puntos": cliente.licencia_puntos or "",
        "licencia_restricciones": cliente.licencia_restricciones or "",

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

        # CONTROL
        "datos_full_consultados": cliente.datos_full_consultados,
        "fecha_ultima_consulta_api": cliente.fecha_ultima_consulta_api.isoformat() if cliente.fecha_ultima_consulta_api else "",
    }
# =========================================================
# VISTA API: CONSULTA DE CLIENTES (CÉDULA Y RUC)
# =========================================================
@login_required
def consultar_cedula_api(request):
    identificacion = request.GET.get("cedula", "").strip()
    solicita_full = request.GET.get("full", "false").strip().lower() == "true"
    
    if not identificacion or not identificacion.isdigit() or len(identificacion) not in [10, 13]:
        return JsonResponse({"exito": False, "error": "Identificación inválida."})

    es_ruc = len(identificacion) == 13
    cliente = Cliente.objects.filter(identificacion=identificacion).first()

    # --- LÓGICA DE CACHÉ (Sin tocar tu modelo) ---
    if cliente:
        if not es_ruc and (not solicita_full or cliente.datos_full_consultados):
            return JsonResponse({"exito": True, "origen": "bd", "cliente": serializar_cliente(cliente)})
        if es_ruc and cliente.fecha_ultima_consulta_api and (timezone.now() - cliente.fecha_ultima_consulta_api) < timedelta(days=30):
            return JsonResponse({"exito": True, "origen": "bd_fresca", "cliente": serializar_cliente(cliente)})

    # --- CONSULTA EXTERNA ---
    url = f"https://apiconsult.zampisoft.com/api/consultar?identificacion={identificacion}&token={CEDULA_API_TOKEN}"
    if not es_ruc and solicita_full:
        url += "&full=true"

    try:
        respuesta = requests.get(url, timeout=20)
        if respuesta.status_code != 200:
            return JsonResponse({"exito": False, "error": "Error externo"})

        data = respuesta.json()
        
        # --- UTILIZANDO TUS MÉTODOS EXISTENTES ---
        if not cliente:
            cliente = Cliente(identificacion=identificacion)
        
        # Aquí aprovechas tus métodos ya construidos
        if es_ruc:
            cliente.cargar_desde_api_ruc(data)
        else:
            cliente.cargar_desde_api_persona(data, full=solicita_full)
            
        cliente.fecha_ultima_consulta_api = timezone.now()
        cliente.save() # Esto dispara tu normalizar_datos() y full_clean()

        return JsonResponse({"exito": True, "origen": "api", "cliente": serializar_cliente(cliente)})
        
    except Exception as e:
        return JsonResponse({"exito": False, "error": str(e)}) 
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

## =================================================================================
# API: AUTOCOMPLETADO DE PLACA PARA RECEPCIÓN
# =================================================================================
@login_required
def buscar_vehiculo_por_placa(request):
    placa = request.GET.get('placa', '').strip().upper()
    
    if placa:
        # Buscamos el último expediente de esta placa
        expediente = ExpedienteVehiculo.objects.filter(placa=placa).order_by('-id').first()
        
        if expediente and expediente.cliente:
            # FILTRO DE CALIDAD
            cedula_valida = ""
            ced_temp = str(expediente.cliente.identificacion or "").strip()
            if ced_temp.isdigit() and len(ced_temp) in [10, 13]:
                cedula_valida = ced_temp
                
            return JsonResponse({
                'encontrado': True,
                'vehiculo': expediente.vehiculo or '',
                'anio': expediente.anio_vehiculo or '',
                'cliente': {
                    'identificacion': cedula_valida, # <--- AHORA PASA POR EL FILTRO
                    'nombre': expediente.cliente.nombre_completo
                }
            })
            
    # Si no existe la placa o no tiene cliente
    return JsonResponse({'encontrado': False})


# =========================================================
# API: BÚSQUEDA RECOMENDACIONES TÉCNICAS
# =========================================================
@login_required
def api_buscar_recomendaciones_ot(request):
    query = request.GET.get("q", "").strip()

    recomendaciones = PlantillaRecomendacion.objects.filter(
        activo=True
    ).order_by("orden_visual", "titulo")

    if query:
        terminos = query.split()

        for t in terminos:
            recomendaciones = recomendaciones.filter(
                Q(titulo__icontains=t) |
                Q(texto__icontains=t)
            )

    data = []

    for item in recomendaciones.distinct()[:20]:
        data.append({
            "id": item.id,
            "titulo": item.titulo,
            "texto": item.texto,
        })

    return JsonResponse({
        "resultados": data
    })