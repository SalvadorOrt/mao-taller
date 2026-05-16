
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

# =========================================================
# ACCIONES DE ESTADO (Cerrar / Anular / Reabrir)
# =========================================================
@login_required
def cerrar_orden(request, pk):
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=pk)
        
        if not puede_operar_orden_desde_sucursal_activa(request, orden):
            messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
            return redirect("detalle_orden", pk=pk)
            
        if orden.estado == 'ABIERTA':
            orden.estado = 'CERRADA'
            orden.save()
            messages.success(request, f"La orden {orden.numero_orden} ha sido cerrada.")
        else:
            messages.error(request, f"No se puede cerrar la orden porque actualmente está {orden.estado}.")
    else:
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        
    return redirect("detalle_orden", pk=pk)

@login_required
def anular_orden(request, pk):
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=pk)
        
        if not puede_operar_orden_desde_sucursal_activa(request, orden):
            messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
            return redirect("detalle_orden", pk=pk)
            
        if orden.estado == 'ABIERTA':
            orden.estado = 'ANULADA'
            orden.save()
            messages.success(request, f"La orden {orden.numero_orden} ha sido anulada.")
        else:
            messages.error(request, f"No se puede anular la orden porque actualmente está {orden.estado}.")
    else:
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        
    return redirect("detalle_orden", pk=pk)

@login_required
@permission_required('ordenes_de_trabajo.can_reopen_orden', raise_exception=True)
def reabrir_orden(request, pk):
    if request.method == "POST":
        orden = get_object_or_404(OrdenTrabajo, pk=pk)
        
        if not puede_operar_orden_desde_sucursal_activa(request, orden):
            messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
            return redirect("detalle_orden", pk=pk)
            
        if orden.estado != 'ABIERTA':
            orden.estado = 'ABIERTA'
            orden.save()
            messages.success(request, f"Privilegio concedido: La orden {orden.numero_orden} ha sido reabierta.")
        else:
            messages.error(request, "La orden ya se encuentra ABIERTA.")
    else:
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        
    return redirect("detalle_orden", pk=pk)