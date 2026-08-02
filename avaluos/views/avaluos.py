from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ordenes_de_trabajo.models import OrdenTrabajo


@login_required
def ordenes_pendientes(request):
    ordenes = (
        OrdenTrabajo.objects
        .filter(
            estado="ABIERTA",
            avaluo_mecanico__isnull=True,
        )
        .select_related(
            "sucursal",
            "cliente",
            "expediente",
        )
        .prefetch_related(
            "tecnicos",
        )
        .order_by("-fecha_ingreso")
    )

    if request.user.rol != "ADMIN":
        ordenes = ordenes.filter(
            sucursal=request.user.sucursal
        )

    return render(
        request,
        "avaluos/ordenes_pendientes.html",
        {
            "ordenes": ordenes,
        },
    )