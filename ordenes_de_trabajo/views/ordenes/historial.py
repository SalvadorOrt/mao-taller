
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Count
from ..api import clasificar_vehiculo_con_ia
# 🚀 IMPORTAMOS LOS MODELOS DE INVENTARIO NECESARIOS PARA LA "CUARENTENA"
from inventario.models import CodigoProducto, Categoria
from servicios.models import ServicioCatalogo
from ...models import (
    Sucursal,
    Cliente,
    OrdenTrabajo,
    FotoRecepcionVehiculo,
    OrdenChecklistRecepcion,
    OrdenCroquisDanio,
    OrdenInsumoDetalle,
    OrdenObjetoAdicional,
    OrdenServicioDetalle,
    OrdenServicioProcedimientoDetalle, 
    OrdenSintoma,
    OrdenTrabajoSolicitado,
    ExpedienteVehiculo,
    Cotizacion,                   
    CotizacionInsumoDetalle,      
    CotizacionServicioDetalle,
    CotizacionProcedimientoDetalle
)
from ..utils import (
    parse_int, parse_decimal, cargar_json_lista, procesar_imagen_base64,
    obtener_sucursal_activa, obtener_o_crear_expediente, generar_numero_orden,
    puede_operar_orden_desde_sucursal_activa,parse_cantidad
)
from django.urls import reverse

@login_required
def historial_vehiculos(request):
    q = request.GET.get("q", "").strip().upper()
    expedientes = ExpedienteVehiculo.objects.none()
    if q:
        expedientes = ExpedienteVehiculo.objects.select_related("cliente").filter(
            Q(placa__icontains=q) | Q(vehiculo__icontains=q) |
            Q(cliente__nombre_completo__icontains=q) | Q(cliente_respaldo__icontains=q)
        ).order_by("placa", "vehiculo", "id")
    return render(request, "historial_vehiculos.html", {"q": q, "expedientes": expedientes})

@login_required
def detalle_expediente(request, pk):
    expediente = get_object_or_404(ExpedienteVehiculo.select_related("cliente"), pk=pk)
    ordenes = expediente.ordenes.select_related("sucursal", "cliente", "usuario_receptor").prefetch_related(
        "servicios_detalles", "insumos_detalles", "sintomas_items", "trabajos_solicitados_items"
    ).order_by("-fecha_ingreso")
    return render(request, "detalle_expediente.html", {"expediente": expediente, "ordenes": ordenes})