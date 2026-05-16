# ordenes_de_trabajo/views/api.py

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

PLACA_API_USERNAME = "SalvadorOrtega"
CEDULA_API_TOKEN = "yKGE-7wqa-kwNp-3AvU"

# 🔥 TU API KEY GEMINI
GEMINI_API_KEY = "AIzaSyAA5PGQW2XAGoYGzjFjeo8T97fxgy44678"



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
# API: CONSULTAR PLACA CON CACHE
# =========================================================
@login_required
def consultar_regcheck(request):
    placa = request.GET.get("placa", "").strip().upper()

    if not placa:
        return JsonResponse({
            "exito": False,
            "error": "Placa vacía"
        })

    vehiculo_local = ExpedienteVehiculo.objects.filter(placa=placa).first()

    if vehiculo_local:
        cliente = vehiculo_local.cliente_actual

        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "placa": placa,
            "vehiculo": vehiculo_local.vehiculo or "",
            "anio": vehiculo_local.anio or "",
            "color": vehiculo_local.color or "",
            "kilometraje": vehiculo_local.kilometraje_actual or "",
            "identificacion": cliente.identificacion if cliente else "",
            "nombre_completo": cliente.nombre_completo if cliente else "",
            "telefono": cliente.telefono if cliente else "",
            "email": cliente.email if cliente else "",
            "direccion": cliente.direccion if cliente else "",
            "tipo_tarifa_vehiculo": getattr(vehiculo_local, "tipo_tarifa_vehiculo", "NO_APLICA"),
            "gama_vehiculo": getattr(vehiculo_local, "gama_vehiculo", "NO_APLICA"),
        })

    url = (
        "https://www.placaapi.ec/API/reg.asmx/"
        f"CheckEcuador?RegistrationNumber={placa}"
        f"&username={PLACA_API_USERNAME}"
    )

    try:
        respuesta = requests.get(url, timeout=15)

        if respuesta.status_code != 200:
            return JsonResponse({
                "exito": False,
                "error": f"Error API: {respuesta.status_code}"
            })

        root = ET.fromstring(respuesta.content)

        json_node = root.find(
            ".//ns:vehicleJson",
            {"ns": "http://regcheck.org.uk"}
        )

        if json_node is None or not json_node.text:
            return JsonResponse({
                "exito": False,
                "error": "No se encontró información del vehículo."
            })

        datos_auto = json.loads(json_node.text)

        marca = (
            datos_auto.get("MakeDescription", {}).get("CurrentTextValue", "")
            or datos_auto.get("CarMake", {}).get("CurrentTextValue", "")
        )

        if marca.upper() == "VW":
            marca = "VOLKSWAGEN"

        modelo = (
            datos_auto.get("ModelDescription", {}).get("CurrentTextValue", "")
            or datos_auto.get("CarModel", {}).get("CurrentTextValue", "")
        )

        anio = datos_auto.get("Year", "")
        descripcion = datos_auto.get("Description", "")
        vehiculo_completo = f"{marca} {modelo}".strip()

        clasificacion = clasificar_vehiculo_con_ia(
            marca=marca,
            modelo=modelo,
            anio=anio,
            descripcion=descripcion,
        )

        expediente, creado = ExpedienteVehiculo.objects.update_or_create(
            placa=placa,
            defaults={
                "vehiculo": vehiculo_completo.upper(),
                "anio": int(anio) if str(anio).isdigit() else None,
                "color": "",
                "kilometraje_actual": None,
            }
        )

        return JsonResponse({
            "exito": True,
            "origen": "api_guardada",
            "placa": placa,
            "vehiculo": expediente.vehiculo or "",
            "marca": marca,
            "modelo": modelo,
            "anio": expediente.anio or "",
            "descripcion": descripcion,
            "tipo_tarifa_vehiculo": clasificacion["tipo_tarifa_vehiculo"],
            "gama_vehiculo": clasificacion["gama_vehiculo"],
            "confianza": clasificacion["confianza"],
            "motivo": clasificacion["motivo"],
        })

    except Exception as e:
        return JsonResponse({
            "exito": False,
            "error": str(e)
        })
# =========================================================
# API: CONSULTAR CÉDULA Y RUC
# =========================================================
# =========================================================
# API: CONSULTAR CÉDULA / RUC CON CACHE
# =========================================================
@login_required
def consultar_cedula_api(request):
    identificacion = request.GET.get("cedula", "").strip()

    if not identificacion or not identificacion.isdigit() or len(identificacion) not in [10, 13]:
        return JsonResponse({
            "exito": False,
            "error": "Identificación inválida. Debe tener 10 o 13 dígitos."
        })

    cliente = Cliente.objects.filter(identificacion=identificacion).first()

    if cliente:
        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "identificacion": cliente.identificacion,
            "nombre_completo": cliente.nombre_completo,
            "telefono": cliente.telefono or "",
            "telefono_secundario": getattr(cliente, "telefono_secundario", "") or "",
            "telefono_trabajo": getattr(cliente, "telefono_trabajo", "") or "",
            "email": cliente.email or "",
            "direccion": cliente.direccion or "",
        })

    url = (
        "https://apiconsult.zampisoft.com/api/"
        f"consultar?identificacion={identificacion}"
        f"&token={CEDULA_API_TOKEN}"
    )

    try:
        respuesta = requests.get(url, timeout=15)

        if respuesta.status_code != 200:
            return JsonResponse({
                "exito": False,
                "error": "El SRI/Registro Civil no encontró resultados."
            })

        data = respuesta.json()

        nombre_api = data.get("razonSocial") or data.get("nombre", "")
        identificacion_api = data.get("numeroRuc") or data.get("cedula") or identificacion

        direccion_api = data.get("lugarDomicilio", "")
        if not direccion_api and data.get("establecimientos"):
            direccion_api = data.get("establecimientos")[0].get("direccionCompleta", "")

        tipo_documento = "R" if len(identificacion_api) == 13 else "C"

        cliente = Cliente.objects.create(
            tipo_documento=tipo_documento,
            identificacion=identificacion_api,
            nombre_completo=(nombre_api or "CONSUMIDOR FINAL").upper(),
            telefono="",
            email="",
            direccion=direccion_api or "",
        )

        return JsonResponse({
            "exito": True,
            "origen": "api_guardada",
            "identificacion": cliente.identificacion,
            "nombre_completo": cliente.nombre_completo,
            "telefono": cliente.telefono or "",
            "telefono_secundario": getattr(cliente, "telefono_secundario", "") or "",
            "telefono_trabajo": getattr(cliente, "telefono_trabajo", "") or "",
            "email": cliente.email or "",
            "direccion": cliente.direccion or "",
        })

    except Exception as e:
        return JsonResponse({
            "exito": False,
            "error": f"Error de conexión: {str(e)}"
        })
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