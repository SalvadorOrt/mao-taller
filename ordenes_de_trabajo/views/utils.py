# ordenes_de_trabajo/views/utils.py
import json
import base64
from decimal import Decimal, InvalidOperation
from django.core.files.base import ContentFile
from ..models import OrdenTrabajo, Sucursal, ExpedienteVehiculo

def parse_int(valor, default=None):
    try:
        if valor is None:
            return default

        texto = str(valor).strip().replace(",", ".")

        if not texto:
            return default

        return int(float(texto))

    except (ValueError, TypeError):
        return default

def parse_decimal(valor, default=Decimal("0.00")):
    try:
        if valor is None:
            return default

        texto = str(valor).strip()

        if not texto:
            return default

        # Acepta 10,50 y 10.50 como decimales
        texto = texto.replace(",", ".")

        # Evita valores ambiguos como 1.000.50
        if texto.count(".") > 1:
            return default

        return Decimal(texto)

    except (InvalidOperation, ValueError, TypeError):
        return default

def cargar_json_lista(texto):
    if not texto: return []
    try:
        data = json.loads(texto)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def procesar_imagen_base64(base64_data):
    if base64_data and 'data:image' in base64_data and ';base64,' in base64_data:
        try:
            format, imgstr = base64_data.split(';base64,')
            return ContentFile(base64.b64decode(imgstr))
        except Exception:
            return None
    return None

def usuario_puede_cambiar_sucursal(request):
    usuario = request.user
    return bool(usuario.is_authenticated and getattr(usuario, "puede_cambiar_sucursal", False))

def obtener_sucursal_activa(request):
    usuario = request.user
    if usuario_puede_cambiar_sucursal(request):
        sucursal_id = request.session.get("sucursal_activa_id")
        if sucursal_id:
            sucursal = Sucursal.objects.filter(id=sucursal_id, activa=True).first()
            if sucursal: return sucursal
    if getattr(usuario, "sucursal_id", None):
        return Sucursal.objects.filter(id=usuario.sucursal_id, activa=True).first()
    return None

def generar_numero_orden():
    ultima = OrdenTrabajo.objects.order_by("-id").first()
    siguiente = (ultima.id + 1) if ultima else 1
    return f"OT-{siguiente:05d}"

def obtener_o_crear_expediente(cliente_obj, nombre_cliente, placa, vehiculo, anio):
    placa_normalizada = placa.strip().upper() if placa else None
    vehiculo_normalizado = vehiculo.strip().upper() if vehiculo else None
    nombre_cliente_normalizado = nombre_cliente.strip().upper() if nombre_cliente else None

    expediente = None
    if placa_normalizada:
        expediente = ExpedienteVehiculo.objects.filter(placa=placa_normalizada).first()

    if expediente:
        if cliente_obj: expediente.cliente = cliente_obj
        if nombre_cliente_normalizado: expediente.cliente_respaldo = nombre_cliente_normalizado
        if vehiculo_normalizado: expediente.vehiculo = vehiculo_normalizado
        if anio: expediente.anio_vehiculo = anio
        expediente.activo = True
        expediente.save()
        return expediente

    return ExpedienteVehiculo.objects.create(
        cliente=cliente_obj,
        cliente_respaldo=nombre_cliente_normalizado if nombre_cliente_normalizado else None,
        placa=placa_normalizada,
        vehiculo=vehiculo_normalizado,
        anio_vehiculo=anio,
        activo=True,
    )

def puede_operar_orden_desde_sucursal_activa(request, orden):
    sucursal_activa = obtener_sucursal_activa(request)
    if not sucursal_activa: return False
    return orden.sucursal_id == sucursal_activa.id


def parse_cantidad(valor, default=Decimal("1.00")):

    try:
        if valor is None:
            return default

        texto = str(valor).strip()

        if not texto:
            return default

        texto = texto.replace(",", ".")

        if texto.count(".") > 1:
            return default

        return Decimal(texto)

    except (InvalidOperation, ValueError, TypeError):
        return default