# ordenes_de_trabajo/views/api.py

import json
import requests
import xml.etree.ElementTree as ET
from google import genai

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from servicios.models import ServicioCatalogo
from ..models import Cliente
from inventario.models import CodigoProducto, StockSucursal
from .utils import obtener_sucursal_activa


PLACA_API_USERNAME = "SalvadorOrtega"
CEDULA_API_TOKEN = "yKGE-7wqa-kwNp-3AvU"

# 🔥 TU API KEY GEMINI
GEMINI_API_KEY = "AIzaSyAA5PGQW2XAGoYGzjFjeo8T97fxgy44678"


# =========================================================
# IA: LIMPIAR JSON
# =========================================================
def limpiar_json_ia(texto):
    texto = (texto or "").strip()

    if texto.startswith("```json"):
        texto = texto[7:].strip()

    elif texto.startswith("```"):
        texto = texto[3:].strip()

    if texto.endswith("```"):
        texto = texto[:-3].strip()

    return texto

# =========================================================
# IA: CLASIFICAR VEHÍCULO
# =========================================================
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

    print("\n========== INICIO CLASIFICACIÓN IA ==========")
    print("MARCA RECIBIDA:", marca)
    print("MODELO RECIBIDO:", modelo)
    print("AÑO RECIBIDO:", anio)
    print("DESCRIPCIÓN RECIBIDA:", descripcion)

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)

        prompt = f"""
Devuelve SOLO JSON válido.

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

Formato obligatorio:

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

        print("\n========== RESPUESTA RAW GEMINI ==========")
        print(response.text)

        texto = limpiar_json_ia(response.text)

        print("\n========== TEXTO LIMPIO ==========")
        print(texto)

        data = json.loads(texto)

        print("\n========== JSON PARSEADO ==========")
        print(data)

        tipo_tarifa = data.get(
            "tipo_tarifa_vehiculo",
            "NO_APLICA"
        )

        gama = data.get(
            "gama_vehiculo",
            "NO_APLICA"
        )

        if tipo_tarifa not in tipos_validos:
            print("ADVERTENCIA: tipo_tarifa inválido:", tipo_tarifa)
            tipo_tarifa = "NO_APLICA"

        if gama not in gamas_validas:
            print("ADVERTENCIA: gama inválida:", gama)
            gama = "NO_APLICA"

        resultado = {
            "tipo_tarifa_vehiculo": tipo_tarifa,
            "gama_vehiculo": gama,
            "confianza": data.get("confianza", 0.0),
            "motivo": data.get("motivo"),
        }

        print("\n========== RESULTADO FINAL IA ==========")
        print("TIPO TARIFA:", resultado["tipo_tarifa_vehiculo"])
        print("GAMA:", resultado["gama_vehiculo"])
        print("CONFIANZA:", resultado["confianza"])
        print("MOTIVO:", resultado["motivo"])
        print("========================================\n")

        return resultado

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
# API: CONSULTAR PLACA
# =========================================================
@login_required
def consultar_regcheck(request):
    print("ENTRÓ A CONSULTAR_REGCHECK NUEVA")
    placa = request.GET.get("placa","").strip().upper()

    if not placa:
        return JsonResponse({
            "exito": False,
            "error": "Placa vacía"
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
                "error": "No vehicleJson"
            })

        datos_auto = json.loads(json_node.text)

        marca = (
            datos_auto.get(
                "MakeDescription",
                {}
            ).get(
                "CurrentTextValue",
                ""
            )
            or
            datos_auto.get(
                "CarMake",
                {}
            ).get(
                "CurrentTextValue",
                ""
            )
        )

        if marca.upper() == "VW":
            marca = "VOLKSWAGEN"

        modelo = (
            datos_auto.get(
                "ModelDescription",
                {}
            ).get(
                "CurrentTextValue",
                ""
            )
            or
            datos_auto.get(
                "CarModel",
                {}
            ).get(
                "CurrentTextValue",
                ""
            )
        )

        anio = datos_auto.get("Year", "")

        descripcion = datos_auto.get(
            "Description",
            ""
        )

        vehiculo_completo = (
            f"{marca} {modelo}"
        ).strip()

        # =====================================================
        # IA
        # =====================================================
        clasificacion = clasificar_vehiculo_con_ia(
            marca=marca,
            modelo=modelo,
            anio=anio,
            descripcion=descripcion,
        )

        return JsonResponse({
            "exito": True,
            "placa": placa,
            "vehiculo": vehiculo_completo,
            "marca": marca,
            "modelo": modelo,
            "anio": anio,
            "descripcion": descripcion,
            "chasis": datos_auto.get("VehicleIdentificationNumber", ""),
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
# API: CONSULTAR CÉDULA
# =========================================================
@login_required
def consultar_cedula_api(request):

    cedula = request.GET.get(
        "cedula",
        ""
    ).strip()

    if not cedula or not cedula.isdigit():

        return JsonResponse({
            "exito": False,
            "error": "Cédula inválida"
        })

    cliente = Cliente.objects.filter(
        identificacion=cedula
    ).first()

    if cliente:

        return JsonResponse({
            "exito": True,
            "origen": "bd",
            "identificacion": cliente.identificacion,
            "nombre_completo": cliente.nombre_completo,
            "telefono": cliente.telefono or "",
            "email": cliente.email or "",
            "direccion": cliente.direccion or "",
        })

    url = (
        "https://apiconsult.zampisoft.com/api/"
        f"consultar?identificacion={cedula}"
        f"&token={CEDULA_API_TOKEN}"
    )

    try:
        respuesta = requests.get(url, timeout=15)

        if respuesta.status_code == 200:

            data = respuesta.json()

            return JsonResponse({
                "exito": True,
                "origen": "api",
                "identificacion": data.get(
                    "cedula",
                    cedula
                ),
                "nombre_completo": data.get(
                    "nombre",
                    ""
                ),
                "telefono": "",
                "email": "",
                "direccion": data.get(
                    "lugarDomicilio",
                    ""
                ),
                "genero": data.get(
                    "genero",
                    ""
                ),
            })

        return JsonResponse({
            "exito": False,
            "error": "Error API Cédula"
        })

    except Exception as e:
        return JsonResponse({
            "exito": False,
            "error": str(e)
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