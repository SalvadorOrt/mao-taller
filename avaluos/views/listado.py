from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from ordenes_de_trabajo.models import (
    OrdenTrabajo,
    Sucursal,
    Tecnico,
)


@login_required
def ordenes_pendientes(request):
    puede_ver_todas_sucursales = (
        request.user.rol == "ADMIN"
        or request.user.puede_cambiar_sucursal
    )

    ordenes = (
        OrdenTrabajo.objects
        .filter(
            estado="ABIERTA",
        )
        .select_related(
            "sucursal",
            "cliente",
            "expediente",
            "avaluo_mecanico",
            "avaluo_mecanico__evaluador",
        )
        .prefetch_related(
            "tecnicos",
        )
        .order_by(
            "-fecha_ingreso",
            "-id",
        )
    )

    # =====================================================
    # RESTRICCIÓN DE SUCURSAL
    # =====================================================

    if not puede_ver_todas_sucursales:
        if not request.user.sucursal_id:
            ordenes = ordenes.none()
        else:
            ordenes = ordenes.filter(
                sucursal_id=request.user.sucursal_id,
            )

    # =====================================================
    # FILTROS RECIBIDOS
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

    estado_avaluo = request.GET.get(
        "estado_avaluo",
        "",
    ).strip().upper()

    tecnico_id = request.GET.get(
        "tecnico",
        "",
    ).strip()

    sucursal_id = request.GET.get(
        "sucursal",
        "",
    ).strip()

    # =====================================================
    # BÚSQUEDA GENERAL
    # =====================================================

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
            | Q(
                avaluo_mecanico__numero_avaluo__icontains=q,
            )
            | Q(
                avaluo_mecanico__evaluador__first_name__icontains=q,
            )
            | Q(
                avaluo_mecanico__evaluador__last_name__icontains=q,
            )
            | Q(
                avaluo_mecanico__evaluador__username__icontains=q,
            )
        )

    # =====================================================
    # FILTRO POR FECHAS
    # =====================================================

    if fecha_inicio:
        ordenes = ordenes.filter(
            fecha_ingreso__date__gte=fecha_inicio,
        )

    if fecha_fin:
        ordenes = ordenes.filter(
            fecha_ingreso__date__lte=fecha_fin,
        )

    # =====================================================
    # FILTRO POR ESTADO DEL AVALÚO
    # =====================================================

    if estado_avaluo == "PENDIENTE":
        ordenes = ordenes.filter(
            avaluo_mecanico__isnull=True,
        )

    elif estado_avaluo == "BORRADOR":
        ordenes = ordenes.filter(
            avaluo_mecanico__estado="BORRADOR",
        )

    elif estado_avaluo == "FINALIZADO":
        ordenes = ordenes.filter(
            avaluo_mecanico__estado="FINALIZADO",
        )

    elif estado_avaluo == "ANULADO":
        ordenes = ordenes.filter(
            avaluo_mecanico__estado="ANULADO",
        )

    # =====================================================
    # FILTRO POR TÉCNICO
    # =====================================================

    if tecnico_id.isdigit():
        ordenes = ordenes.filter(
            tecnicos__id=int(tecnico_id),
        )

    # =====================================================
    # FILTRO POR SUCURSAL
    # =====================================================

    if sucursal_id.isdigit():
        sucursal_seleccionada = int(
            sucursal_id
        )

        if puede_ver_todas_sucursales:
            ordenes = ordenes.filter(
                sucursal_id=sucursal_seleccionada,
            )

        elif (
            request.user.sucursal_id
            == sucursal_seleccionada
        ):
            ordenes = ordenes.filter(
                sucursal_id=sucursal_seleccionada,
            )

    ordenes = ordenes.distinct()

    # =====================================================
    # TÉCNICOS DISPONIBLES PARA EL FILTRO
    # =====================================================

    tecnicos = Tecnico.objects.filter(
        activo=True,
    )

    if puede_ver_todas_sucursales:
        if sucursal_id.isdigit():
            tecnicos = tecnicos.filter(
                sucursal_id=int(sucursal_id),
            )
    else:
        tecnicos = tecnicos.filter(
            sucursal_id=request.user.sucursal_id,
        )

    tecnicos = tecnicos.order_by(
        "nombre",
    )

    # =====================================================
    # SUCURSALES DISPONIBLES PARA EL FILTRO
    # =====================================================

    if puede_ver_todas_sucursales:
        sucursales = (
            Sucursal.objects
            .filter(
                activo=True,
            )
            .order_by(
                "nombre",
            )
        )
    else:
        sucursales = (
            Sucursal.objects
            .filter(
                pk=request.user.sucursal_id,
                activo=True,
            )
            .order_by(
                "nombre",
            )
        )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "avaluos/ordenes_pendientes.html",
        {
            "ordenes": ordenes,

            "q": q,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "estado_avaluo": estado_avaluo,
            "tecnico_id": tecnico_id,
            "sucursal_id": sucursal_id,

            "tecnicos": tecnicos,
            "sucursales": sucursales,

            "puede_ver_todas_sucursales": (
                puede_ver_todas_sucursales
            ),
        },
    )