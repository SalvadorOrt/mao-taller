from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from ...models import ExpedienteVehiculo


@login_required
def historial_vehiculos(request):
    q = request.GET.get("q", "").strip().upper()

    expedientes = ExpedienteVehiculo.objects.none()

    if q:
        expedientes = (
            ExpedienteVehiculo.objects
            .select_related("cliente")
            .filter(
                Q(placa__icontains=q)
                | Q(vehiculo__icontains=q)
                | Q(cliente__nombre_completo__icontains=q)
                | Q(cliente_respaldo__icontains=q),
                activo=True,
            )
            .order_by(
                "placa",
                "vehiculo",
                "id",
            )
        )

    return render(
        request,
        "historial/historial_vehiculos.html",
        {
            "q": q,
            "expedientes": expedientes,
        },
    )


@login_required
def detalle_expediente(request, pk):
    expediente = get_object_or_404(
        ExpedienteVehiculo.objects.select_related("cliente"),
        pk=pk,
        activo=True,
    )

    ordenes = list(
        expediente.ordenes
        .select_related(
            "sucursal",
            "cliente",
            "usuario_receptor",
        )
        .prefetch_related(
            "servicios_detalles",
            "servicios_historicos",
            "insumos_detalles",
            "insumos_historicos",
            "sintomas_items",
            "trabajos_solicitados_items",
        )
        .order_by(
            "fecha_ingreso",
            "id",
        )
    )

    kilometraje_anterior = None

    for posicion, orden in enumerate(ordenes, start=1):
        orden.posicion_historial = posicion
        orden.diferencia_km = None
        orden.kilometraje_inconsistente = False

        if orden.kilometraje is None:
            continue

        if kilometraje_anterior is not None:
            diferencia = orden.kilometraje - kilometraje_anterior

            if diferencia >= 0:
                orden.diferencia_km = diferencia
            else:
                orden.kilometraje_inconsistente = True

        kilometraje_anterior = orden.kilometraje

    return render(
        request,
        "historial/detalle_expediente.html",
        {
            "expediente": expediente,
            "ordenes": ordenes,
            "total_ordenes": len(ordenes),
        },
    )