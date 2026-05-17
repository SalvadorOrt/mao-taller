

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required


from django.db.models import Q

from ...models import (
    ExpedienteVehiculo,
)



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