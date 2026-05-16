# ordenes_de_trabajo/views/dashboard.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Q

from ..models import OrdenTrabajo, Sucursal, ExpedienteVehiculo
from .utils import obtener_sucursal_activa, usuario_puede_cambiar_sucursal

@login_required
def cambiar_sucursal_activa(request):
    if request.method != "POST": return redirect("dashboard")
    if not usuario_puede_cambiar_sucursal(request):
        return HttpResponseForbidden("No tienes permisos.")
    
    sucursal = Sucursal.objects.filter(id=request.POST.get("sucursal_id"), activa=True).first()
    if sucursal: request.session["sucursal_activa_id"] = sucursal.id
    return redirect("dashboard")

@login_required
def dashboard_taller(request):
    sucursal_activa = obtener_sucursal_activa(request)
    sucursales = Sucursal.objects.filter(activa=True).order_by("nombre") if usuario_puede_cambiar_sucursal(request) else []

    if not sucursal_activa:
        return render(request, "dashboard.html", {
            "ordenes_activas": [], "sucursal_activa": None, "sucursales": sucursales,
            "puede_cambiar_sucursal": usuario_puede_cambiar_sucursal(request), "sin_sucursal_activa": True,
        })

    ordenes = OrdenTrabajo.objects.select_related("sucursal", "cliente", "expediente").prefetch_related("servicios_detalles", "insumos_detalles").filter(
        sucursal=sucursal_activa, es_migrada=False, estado__in=["ABIERTA", "ESPERA_REP", "TRABAJO_EXT"],
    ).order_by("-fecha_ingreso")

    ordenes_activas = [{
        "id": o.id, "numero_orden": o.numero_orden, "placa": o.placa, "vehiculo": o.vehiculo,
        "cliente": o.nombre_cliente_final, "items_count": o.servicios_detalles.count() + o.insumos_detalles.count(),
        "color": o.color_hex or "#1d1d1f", "estado": o.get_estado_display(),
        "sucursal": o.sucursal.nombre if o.sucursal else "", "total_general": o.total_general,
        "fecha_ingreso": o.fecha_ingreso, "expediente_id": o.expediente_id,
    } for o in ordenes]

    return render(request, "dashboard.html", {
        "ordenes_activas": ordenes_activas, "sucursal_activa": sucursal_activa,
        "sucursales": sucursales, "puede_cambiar_sucursal": usuario_puede_cambiar_sucursal(request),
        "sin_sucursal_activa": False,
    })
