from django.shortcuts import  redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages

from ...models import (
    OrdenTrabajo
)
from ..utils import (
    puede_operar_orden_desde_sucursal_activa
)

# =========================================================
# ACCIONES DE ESTADO (Cerrar / Anular / Reabrir)
# =========================================================
@login_required
def cerrar_orden(request, pk):
    if request.method != "POST":
        messages.error(request, "Método no permitido. Debe usar el botón oficial del sistema.")
        return redirect("detalle_orden", pk=pk)

    orden = get_object_or_404(OrdenTrabajo, pk=pk)

    if not puede_operar_orden_desde_sucursal_activa(request, orden):
        messages.error(request, "No tienes permiso para operar esta orden desde tu sucursal activa.")
        return redirect("detalle_orden", pk=pk)

    if orden.estado != "ABIERTA":
        messages.error(request, f"No se puede cerrar la orden porque actualmente está {orden.estado}.")
        return redirect("detalle_orden", pk=pk)

    puede, mensaje = orden.puede_cerrarse()

    if not puede:
        messages.error(request, mensaje)
        return redirect("detalle_orden", pk=pk)

    orden.estado = "CERRADA"
    orden.save()

    messages.success(request, f"La orden {orden.numero_orden} ha sido cerrada.")
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