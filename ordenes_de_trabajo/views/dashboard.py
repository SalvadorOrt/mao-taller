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

                "total_vehiculos":
                    0,

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
    # VEHÍCULOS ACTUALMENTE EN EL TALLER
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
            "servicios_detalles__servicio",
            "insumos_detalles",
            "tecnicos",
        )
        .filter(
            sucursal=sucursal_activa,
            es_migrada=False,
            estado="ABIERTA",
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
        # DETALLES DE LA ORDEN
        # =================================================

        repuestos = list(
            orden.insumos_detalles.all()
        )

        servicios = list(
            orden.servicios_detalles.all()
        )

        tecnicos = list(
            orden.tecnicos.all()
        )

        # =================================================
        # NOMBRES DE TÉCNICOS
        # =================================================

        tecnicos_nombres = [
            tecnico.nombre
            for tecnico in tecnicos
        ]

        # =================================================
        # REPUESTOS
        # =================================================

        repuestos_count = len(
            repuestos
        )

        # =================================================
        # MANO DE OBRA INTERNA
        # =================================================

        moi_count = sum(
            1
            for servicio in servicios
            if (
                servicio.tipo_servicio != "EXT"
                and getattr(
                    servicio.servicio,
                    "categoria",
                    None,
                ) != "EXT"
            )
        )

        # =================================================
        # MANO DE OBRA EXTERNA
        # =================================================

        moe_count = sum(
            1
            for servicio in servicios
            if (
                servicio.tipo_servicio == "EXT"
                or getattr(
                    servicio.servicio,
                    "categoria",
                    None,
                ) == "EXT"
            )
        )

        # =================================================
        # TIEMPO QUE LLEVA EL VEHÍCULO EN EL TALLER
        # =================================================

        dias_en_taller = 0
        horas_en_taller = 0
        minutos_en_taller = 0

        tiempo_en_taller = (
            "Recién ingresado"
        )

        if orden.fecha_ingreso:

            diferencia = (
                ahora
                -
                orden.fecha_ingreso
            )

            total_segundos = max(
                int(
                    diferencia.total_seconds()
                ),
                0,
            )

            # =============================================
            # DÍAS
            # =============================================

            dias_en_taller = (
                total_segundos
                // 86400
            )

            # =============================================
            # HORAS RESTANTES
            # =============================================

            horas_en_taller = (
                (
                    total_segundos
                    % 86400
                )
                // 3600
            )

            # =============================================
            # MINUTOS RESTANTES
            # =============================================

            minutos_en_taller = (
                (
                    total_segundos
                    % 3600
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
        # AGREGAR VEHÍCULO AL DASHBOARD
        # =================================================

        ordenes_activas.append(
            {
                # =========================================
                # DATOS PRINCIPALES
                # =========================================

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

                # =========================================
                # TÉCNICOS
                # =========================================

                "tecnicos":
                    tecnicos_nombres,

                # =========================================
                # REP / MOI / MOE
                # =========================================

                "repuestos_count":
                    repuestos_count,

                "moi_count":
                    moi_count,

                "moe_count":
                    moe_count,

                # =========================================
                # COLOR DEL VEHÍCULO
                # =========================================

                "color":
                    (
                        orden.color_hex
                        or "#1d1d1f"
                    ),

                # =========================================
                # SUCURSAL
                # =========================================

                "sucursal":
                    (
                        orden.sucursal.nombre
                        if orden.sucursal
                        else ""
                    ),

                # =========================================
                # TOTAL
                # =========================================

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

                # =========================================
                # EXPEDIENTE
                # =========================================

                "expediente_id":
                    orden.expediente_id,
            }
        )

    # =====================================================
    # TOTAL DE VEHÍCULOS EN EL TALLER
    # =====================================================

    total_vehiculos = len(
        ordenes_activas
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

            "total_vehiculos":
                total_vehiculos,

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