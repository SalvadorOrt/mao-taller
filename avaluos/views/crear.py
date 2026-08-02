from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect

from avaluos.models import (
    AvaluoMecanico,
    CompresionCilindro,
    EstadoRevision,
    ItemInspeccionAvaluo,
    ItemPruebaRuta,
    ItemRevisionSiNo,
    RespuestaSiNo,
    ResultadoInspeccionAvaluo,
    ResultadoPruebaRuta,
    ResultadoRevisionSiNo,
)
from ordenes_de_trabajo.models import OrdenTrabajo


# =========================================================
# CREAR RESULTADOS INICIALES
# =========================================================

def crear_resultados_iniciales(avaluo):
    """
    Crea únicamente los resultados que todavía no existen.

    Esta función puede ejecutarse varias veces sin duplicar datos,
    gracias a las restricciones únicas de los modelos y al uso de
    ignore_conflicts=True.
    """

    # =====================================================
    # INSPECCIÓN NRR / RRM / RRT
    # =====================================================

    items_inspeccion = list(
        ItemInspeccionAvaluo.objects.filter(
            activo=True,
        )
    )

    ResultadoInspeccionAvaluo.objects.bulk_create(
        [
            ResultadoInspeccionAvaluo(
                avaluo=avaluo,
                item=item,
                estado=EstadoRevision.NO_REVISADO,
            )
            for item in items_inspeccion
        ],
        ignore_conflicts=True,
    )

    # =====================================================
    # REVISIONES SÍ / NO
    # =====================================================

    items_revision = list(
        ItemRevisionSiNo.objects.filter(
            activo=True,
        )
    )

    ResultadoRevisionSiNo.objects.bulk_create(
        [
            ResultadoRevisionSiNo(
                avaluo=avaluo,
                item=item,
                respuesta=RespuestaSiNo.NO_REVISADO,
            )
            for item in items_revision
        ],
        ignore_conflicts=True,
    )

    # =====================================================
    # PRUEBA DE RUTA
    # =====================================================

    items_ruta = list(
        ItemPruebaRuta.objects.filter(
            activo=True,
        )
    )

    ResultadoPruebaRuta.objects.bulk_create(
        [
            ResultadoPruebaRuta(
                avaluo=avaluo,
                item=item,
                respuesta=RespuestaSiNo.NO_REVISADO,
            )
            for item in items_ruta
        ],
        ignore_conflicts=True,
    )

    # =====================================================
    # COMPRESIÓN DEL MOTOR
    # =====================================================

    CompresionCilindro.objects.bulk_create(
        [
            CompresionCilindro(
                avaluo=avaluo,
                numero_cilindro=numero,
                unidad="PSI",
            )
            for numero in range(1, 9)
        ],
        ignore_conflicts=True,
    )


# =========================================================
# INICIAR AVALÚO DESDE ORDEN DE TRABAJO
# =========================================================

@login_required
@transaction.atomic
def iniciar_avaluo(request, orden_id):
    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_for_update()
        .select_related(
            "sucursal",
            "cliente",
            "expediente",
        ),
        pk=orden_id,
    )

    # =====================================================
    # VALIDAR ESTADO DE LA OT
    # =====================================================

    if orden.estado != "ABIERTA":
        messages.error(
            request,
            "Solo se puede iniciar un avalúo desde una orden abierta.",
        )

        return redirect(
            "avaluos:ordenes_pendientes",
        )

    # =====================================================
    # VALIDAR SUCURSAL
    # =====================================================

    if request.user.rol != "ADMIN":
        if not request.user.sucursal_id:
            messages.error(
                request,
                "Tu usuario no tiene una sucursal asignada.",
            )

            return redirect(
                "avaluos:ordenes_pendientes",
            )

        if (
            orden.sucursal_id
            != request.user.sucursal_id
        ):
            messages.error(
                request,
                "No tienes permiso para evaluar una orden de otra sucursal.",
            )

            return redirect(
                "avaluos:ordenes_pendientes",
            )

    # =====================================================
    # CREAR O RECUPERAR AVALÚO
    # =====================================================

    avaluo, creado = (
        AvaluoMecanico.objects.get_or_create(
            orden=orden,
            defaults={
                "creado_por": request.user,
                "actualizado_por": request.user,
                "solicitado_por": (
                    orden.nombre_cliente_final
                ),
                "evaluador": (
                    request.user
                    if request.user.rol == "TECNICO"
                    else None
                ),
            },
        )
    )

    # =====================================================
    # COMPLETAR DATOS DEL AVALÚO EXISTENTE
    # =====================================================

    campos_actualizados = []

    if not avaluo.actualizado_por_id:
        avaluo.actualizado_por = request.user
        campos_actualizados.append(
            "actualizado_por",
        )

    if (
        request.user.rol == "TECNICO"
        and not avaluo.evaluador_id
    ):
        avaluo.evaluador = request.user
        campos_actualizados.append(
            "evaluador",
        )

    if campos_actualizados:
        avaluo.save(
            update_fields=(
                campos_actualizados
                + ["actualizado_en"]
            )
        )

    # =====================================================
    # CREAR CATÁLOGOS Y RESULTADOS FALTANTES
    # =====================================================

    crear_resultados_iniciales(
        avaluo,
    )

    # =====================================================
    # MENSAJE
    # =====================================================

    if creado:
        messages.success(
            request,
            "El avalúo fue iniciado correctamente.",
        )
    else:
        messages.info(
            request,
            "Esta orden ya tenía un avalúo. Se abrió el registro existente.",
        )

    # =====================================================
    # IR AL PASO 1
    # =====================================================

    return redirect(
        "avaluos:detalle_avaluo_paso",
        pk=avaluo.pk,
        paso=1,
    )