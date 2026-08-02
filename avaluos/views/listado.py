from django.contrib.auth.decorators import login_required
from django.db.models import Q
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
        .order_by(
            "-fecha_ingreso",
            "-id",
        )
    )

    # ADMIN puede ver todas las sucursales.
    # Los demás usuarios solo ven su sucursal.
    if request.user.rol != "ADMIN":
        if not request.user.sucursal_id:
            ordenes = ordenes.none()
        else:
            ordenes = ordenes.filter(
                sucursal_id=request.user.sucursal_id,
            )

    # =====================================================
    # FILTROS
    # =====================================================

    q = request.GET.get(
        "q",
        "",
    ).strip()

    fecha_inicio = request.GET.get(
        "fecha_inicio",
        "",
    ).strip()

    fecha_fin = request.GET.get(
        "fecha_fin",
        "",
    ).strip()

    if q:
        ordenes = ordenes.filter(
            Q(
                numero_orden__icontains=q,
            )
            | Q(
                placa__icontains=q,
            )
            | Q(
                vehiculo__icontains=q,
            )
            | Q(
                cliente__nombre_completo__icontains=q,
            )
            | Q(
                cliente_respaldo__icontains=q,
            )
        )

    if fecha_inicio:
        ordenes = ordenes.filter(
            fecha_ingreso__date__gte=fecha_inicio,
        )

    if fecha_fin:
        ordenes = ordenes.filter(
            fecha_ingreso__date__lte=fecha_fin,
        )

    return render(
        request,
        "avaluos/ordenes_pendientes.html",
        {
            "ordenes": ordenes,
            "q": q,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
        },
    )