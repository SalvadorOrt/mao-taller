# ordenes_de_trabajo/views/dashboard.py

from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.utils import timezone

from accesos.permissions import permiso_requerido

from ..models import OrdenTrabajo, Sucursal
from .utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)


# =========================================================
# CAMBIAR SUCURSAL ACTIVA
# =========================================================

@permiso_requerido(
    "ordenes_de_trabajo.view_ordentrabajo"
)
def cambiar_sucursal_activa(request):

    if request.method != "POST":
        return redirect(
            "dashboard"
        )

    # =====================================================
    # VALIDAR SI EL USUARIO PUEDE CAMBIAR DE SUCURSAL
    # =====================================================

    if not usuario_puede_cambiar_sucursal(
        request
    ):
        return HttpResponseForbidden(
            "No tienes permisos."
        )

    # =====================================================
    # OBTENER SUCURSAL
    # =====================================================

    sucursal = (
        Sucursal.objects
        .filter(
            id=request.POST.get(
                "sucursal_id"
            ),
            activa=True,
        )
        .first()
    )

    # =====================================================
    # GUARDAR EN SESIÓN
    # =====================================================

    if sucursal:

        request.session[
            "sucursal_activa_id"
        ] = sucursal.id

    return redirect(
        "dashboard"
    )


# =========================================================
# DASHBOARD TALLER
# =========================================================

@permiso_requerido(
    "ordenes_de_trabajo.view_ordentrabajo"
)
def dashboard_taller(request):

    # =====================================================
    # SUCURSAL ACTIVA
    # =====================================================

    sucursal_activa = (
        obtener_sucursal_activa(
            request
        )
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    # =====================================================
    # SUCURSALES DISPONIBLES
    # =====================================================

    if puede_cambiar_sucursal:

        sucursales = (
            Sucursal.objects
            .filter(
                activa=True
            )
            .order_by(
                "nombre"
            )
        )

    else:

        sucursales = []

    # =====================================================
    # SIN SUCURSAL ACTIVA
    # =====================================================

    if not sucursal_activa:

        return render(
            request,
            "dashboard.html",
            {
                "ordenes_activas":
                    [],

                "sucursal_activa":
                    None,

                "sucursales":
                    sucursales,

                "puede_cambiar_sucursal":
                    puede_cambiar_sucursal,

                "sin_sucursal_activa":
                    True,
            },
        )

    # =====================================================
    # ÓRDENES ACTIVAS
    # =====================================================

    ordenes = (
        OrdenTrabajo.objects
        .select_related(
            "sucursal",
            "cliente",
            "expediente",
        )
        .prefetch_related(
            "servicios_detalles",
            "insumos_detalles",
        )
        .filter(
            sucursal=sucursal_activa,
            es_migrada=False,
            estado__in=[
                "ABIERTA",
                "ESPERA_REP",
                "TRABAJO_EXT",
            ],
        )
        .order_by(
            "-fecha_ingreso"
        )
    )

    # =====================================================
    # PREPARAR DATOS DEL DASHBOARD
    # =====================================================

    ahora = timezone.now()

    ordenes_activas = []

    for orden in ordenes:

        # =================================================
        # TIEMPO QUE LLEVA EL VEHÍCULO EN EL TALLER
        # =================================================

        dias_en_taller = 0
        horas_en_taller = 0
        minutos_en_taller = 0

        tiempo_en_taller = "Recién ingresado"

        if orden.fecha_ingreso:

            diferencia = (
                ahora - orden.fecha_ingreso
            )

            total_segundos = max(
                int(
                    diferencia.total_seconds()
                ),
                0,
            )

            dias_en_taller = (
                total_segundos // 86400
            )

            horas_en_taller = (
                (
                    total_segundos % 86400
                )
                // 3600
            )

            minutos_en_taller = (
                (
                    total_segundos % 3600
                )
                // 60
            )

            # =============================================
            # TEXTO AMIGABLE
            # =============================================

            if dias_en_taller > 0:

                texto_dias = (
                    f"{dias_en_taller} "
                    f"{'día' if dias_en_taller == 1 else 'días'}"
                )

                if horas_en_taller > 0:
                    tiempo_en_taller = (
                        f"{texto_dias} "
                        f"{horas_en_taller} h"
                    )
                else:
                    tiempo_en_taller = (
                        texto_dias
                    )

            elif horas_en_taller > 0:

                tiempo_en_taller = (
                    f"{horas_en_taller} "
                    f"{'hora' if horas_en_taller == 1 else 'horas'}"
                )

            elif minutos_en_taller > 0:

                tiempo_en_taller = (
                    f"{minutos_en_taller} min"
                )

        # =================================================
        # AGREGAR AL DASHBOARD
        # =================================================

        ordenes_activas.append(
            {
                "id":
                    orden.id,

                "numero_orden":
                    orden.numero_orden,

                "placa":
                    orden.placa,

                "vehiculo":
                    orden.vehiculo,

                "cliente":
                    orden.nombre_cliente_final,

                "items_count":
                    (
                        orden.servicios_detalles.count()
                        +
                        orden.insumos_detalles.count()
                    ),

                "color":
                    (
                        orden.color_hex
                        or "#1d1d1f"
                    ),

                "estado":
                    orden.get_estado_display(),

                "sucursal":
                    (
                        orden.sucursal.nombre
                        if orden.sucursal
                        else ""
                    ),

                "total_general":
                    orden.total_general,

                # =========================================
                # INGRESO AL TALLER
                # =========================================

                "fecha_ingreso":
                    orden.fecha_ingreso,

                "dias_en_taller":
                    dias_en_taller,

                "horas_en_taller":
                    horas_en_taller,

                "tiempo_en_taller":
                    tiempo_en_taller,

                "expediente_id":
                    orden.expediente_id,
            }
        )

    # =====================================================
    # RENDER
    # =====================================================

    return render(
        request,
        "dashboard.html",
        {
            "ordenes_activas":
                ordenes_activas,

            "sucursal_activa":
                sucursal_activa,

            "sucursales":
                sucursales,

            "puede_cambiar_sucursal":
                puede_cambiar_sucursal,

            "sin_sucursal_activa":
                False,
        },
    )