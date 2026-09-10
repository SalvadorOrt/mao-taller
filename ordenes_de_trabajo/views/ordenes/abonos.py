from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from ...models import (
    AbonoOrdenTrabajo,
    OrdenTrabajo,
)

from ..utils import (
    parse_decimal,
    puede_operar_orden_desde_sucursal_activa,
)


# =========================================================
# REGISTRAR ABONO EN ORDEN DE TRABAJO
# =========================================================

@login_required
@require_POST
def registrar_abono(request, pk):

    with transaction.atomic():

        # -----------------------------------------------------
        # BLOQUEAR OT MIENTRAS SE REGISTRA EL ABONO
        # -----------------------------------------------------

        orden = get_object_or_404(
            OrdenTrabajo.objects.select_for_update(),
            pk=pk,
        )

        # -----------------------------------------------------
        # VALIDAR SUCURSAL
        # -----------------------------------------------------

        if not puede_operar_orden_desde_sucursal_activa(
            request,
            orden,
        ):
            messages.error(
                request,
                (
                    "No puede registrar abonos en una orden "
                    "que no pertenece a la sucursal activa."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # LA OT DEBE ESTAR ABIERTA PARA RECIBIR NUEVOS ABONOS
        # -----------------------------------------------------

        if orden.estado != "ABIERTA":
            messages.error(
                request,
                (
                    "Solo se pueden registrar abonos "
                    "mientras la orden esté abierta."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # PERMISO DJANGO
        # -----------------------------------------------------

        if not request.user.has_perm(
            "ordenes_de_trabajo.add_abonoordentrabajo"
        ):
            messages.error(
                request,
                "No tiene permiso para registrar abonos.",
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # OBTENER MONTO
        # -----------------------------------------------------

        monto = parse_decimal(
            request.POST.get(
                "monto_abono",
                "0",
            ),
            Decimal("0.00"),
        )

        if monto <= Decimal("0.00"):
            messages.error(
                request,
                (
                    "El monto del abono debe ser "
                    "mayor a $0.00."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # OBSERVACIÓN
        # -----------------------------------------------------

        observacion = (
            request.POST.get(
                "observacion_abono",
                "",
            )
            or ""
        ).strip()

        # -----------------------------------------------------
        # CREAR ABONO
        #
        # IMPORTANTE:
        # El abono NO modifica:
        #
        # - subtotal de la OT
        # - descuento
        # - IVA
        # - total_final
        #
        # Es únicamente un movimiento asociado a la OT.
        # -----------------------------------------------------

        try:

            abono = AbonoOrdenTrabajo.objects.create(
                orden=orden,
                monto=monto,
                usuario=request.user,
                estado="REGISTRADO",
                observacion=observacion,
            )

        except ValidationError as exc:

            mensaje = (
                exc.messages[0]
                if exc.messages
                else "No se pudo registrar el abono."
            )

            messages.error(
                request,
                mensaje,
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

    # ---------------------------------------------------------
    # CONFIRMACIÓN
    # ---------------------------------------------------------

    messages.success(
        request,
        (
            f"Abono de ${abono.monto:.2f} "
            f"registrado correctamente."
        ),
    )

    return redirect(
        "detalle_orden",
        pk=orden.pk,
    )


# =========================================================
# EDITAR OBSERVACIÓN DE ABONO
# =========================================================
#
# REGLA:
#
# REGISTRADO + SIN FACTURA
#     -> SE PUEDE EDITAR ÚNICAMENTE LA OBSERVACIÓN
#
# FACTURA ASOCIADA
#     -> NO SE PUEDE EDITAR
#
# FACTURADO / ANULADO
#     -> NO SE PUEDE EDITAR
#
# IMPORTANTE:
# - NO se modifica el monto.
# - NO se modifica la fecha.
# - NO se modifica el usuario.
# - NO se modifica el estado.
# - NO se modifica ningún total de la OT.
#
# =========================================================

@login_required
@require_POST
def editar_observacion_abono(request, pk, abono_id):

    with transaction.atomic():

        # -----------------------------------------------------
        # BLOQUEAR OT
        # -----------------------------------------------------

        orden = get_object_or_404(
            OrdenTrabajo.objects.select_for_update(),
            pk=pk,
        )

        # -----------------------------------------------------
        # VALIDAR SUCURSAL
        # -----------------------------------------------------

        if not puede_operar_orden_desde_sucursal_activa(
            request,
            orden,
        ):
            messages.error(
                request,
                (
                    "No puede editar abonos de una orden "
                    "que no pertenece a la sucursal activa."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # PERMISO DJANGO
        # -----------------------------------------------------

        if not request.user.has_perm(
            "ordenes_de_trabajo.change_abonoordentrabajo"
        ):
            messages.error(
                request,
                "No tiene permiso para editar abonos.",
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # OBTENER Y BLOQUEAR ABONO
        #
        # Además verificamos que pertenezca a la OT indicada.
        # -----------------------------------------------------

        abono = get_object_or_404(
            AbonoOrdenTrabajo.objects.select_for_update(),
            pk=abono_id,
            orden=orden,
        )

        # -----------------------------------------------------
        # SOLO UN ABONO REGISTRADO PUEDE EDITARSE
        # -----------------------------------------------------

        if abono.estado != "REGISTRADO":

            if abono.estado == "FACTURADO":
                mensaje = (
                    "Este abono ya está facturado y "
                    "no puede editarse desde la orden."
                )
            elif abono.estado == "ANULADO":
                mensaje = (
                    "Este abono está anulado y "
                    "no puede editarse."
                )
            else:
                mensaje = (
                    "El estado actual del abono "
                    "no permite editarlo."
                )

            messages.error(
                request,
                mensaje,
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # SI YA TIENE FACTURA, LA INFORMACIÓN QUEDA CONGELADA
        #
        # Esto incluye facturas BORRADOR.
        # -----------------------------------------------------

        if hasattr(
            abono,
            "factura",
        ):
            messages.error(
                request,
                (
                    "Este abono ya está asociado a una factura "
                    "y su observación no puede modificarse."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # OBTENER NUEVA OBSERVACIÓN
        # -----------------------------------------------------

        observacion = (
            request.POST.get(
                "observacion_abono",
                "",
            )
            or ""
        ).strip()

        if len(observacion) > 500:
            messages.error(
                request,
                (
                    "La observación del abono no puede "
                    "superar los 500 caracteres."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # ACTUALIZAR ÚNICAMENTE LA OBSERVACIÓN
        # -----------------------------------------------------

        abono.observacion = observacion

        try:
            abono.save(
                update_fields=[
                    "observacion",
                ]
            )

        except ValidationError as exc:

            mensaje = (
                exc.messages[0]
                if exc.messages
                else "No se pudo actualizar la observación del abono."
            )

            messages.error(
                request,
                mensaje,
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

    # ---------------------------------------------------------
    # CONFIRMACIÓN
    # ---------------------------------------------------------

    messages.success(
        request,
        "Observación del abono actualizada correctamente.",
    )

    return redirect(
        "detalle_orden",
        pk=orden.pk,
    )


# =========================================================
# ELIMINAR ABONO DE ORDEN DE TRABAJO
# =========================================================
#
# REGLA:
#
# REGISTRADO + SIN FACTURA
#     -> SE PUEDE ELIMINAR
#
# FACTURA ASOCIADA
#     -> NO SE PUEDE ELIMINAR
#
# FACTURADO
#     -> NO SE PUEDE ELIMINAR
#
# ANULADO
#     -> NO SE ELIMINA DESDE AQUÍ
#
# =========================================================

@login_required
@require_POST
def eliminar_abono(request, pk, abono_id):

    with transaction.atomic():

        # -----------------------------------------------------
        # BLOQUEAR OT
        # -----------------------------------------------------

        orden = get_object_or_404(
            OrdenTrabajo.objects.select_for_update(),
            pk=pk,
        )

        # -----------------------------------------------------
        # VALIDAR SUCURSAL
        # -----------------------------------------------------

        if not puede_operar_orden_desde_sucursal_activa(
            request,
            orden,
        ):
            messages.error(
                request,
                (
                    "No puede eliminar abonos de una orden "
                    "que no pertenece a la sucursal activa."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # PERMISO DJANGO
        # -----------------------------------------------------

        if not request.user.has_perm(
            "ordenes_de_trabajo.delete_abonoordentrabajo"
        ):
            messages.error(
                request,
                "No tiene permiso para eliminar abonos.",
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # OBTENER Y BLOQUEAR ABONO
        #
        # Además verificamos que realmente pertenezca
        # a la OT indicada en la URL.
        # -----------------------------------------------------

        abono = get_object_or_404(
            AbonoOrdenTrabajo.objects.select_for_update(),
            pk=abono_id,
            orden=orden,
        )

        # -----------------------------------------------------
        # SOLO LOS REGISTRADOS PUEDEN ELIMINARSE
        # -----------------------------------------------------

        if abono.estado != "REGISTRADO":

            if abono.estado == "FACTURADO":
                mensaje = (
                    "Este abono ya está facturado y "
                    "no puede eliminarse desde la orden."
                )
            elif abono.estado == "ANULADO":
                mensaje = (
                    "Este abono está anulado y "
                    "no puede eliminarse."
                )
            else:
                mensaje = (
                    "El estado actual del abono "
                    "no permite eliminarlo."
                )

            messages.error(
                request,
                mensaje,
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # COMPROBAR SI YA EXISTE UNA FACTURA
        #
        # Esto también bloquea el caso donde la factura
        # todavía sea BORRADOR.
        #
        # No esperamos a que diga FACTURADO, porque desde
        # que existe una FacturaVenta relacionada con este
        # abono ya debemos proteger la relación.
        # -----------------------------------------------------

        if hasattr(
            abono,
            "factura",
        ):
            messages.error(
                request,
                (
                    "Este abono ya está asociado a una factura "
                    "y no puede eliminarse."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

        # -----------------------------------------------------
        # GUARDAR MONTO PARA EL MENSAJE
        # -----------------------------------------------------

        monto_eliminado = Decimal(
            abono.monto
            or 0
        )

        # -----------------------------------------------------
        # ELIMINAR
        #
        # El modelo FacturaVenta utiliza PROTECT sobre el
        # abono. Esta captura es una segunda barrera de
        # seguridad en caso de existir una relación.
        # -----------------------------------------------------

        try:
            abono.delete()

        except ProtectedError:
            messages.error(
                request,
                (
                    "El abono está siendo utilizado por una "
                    "factura y no puede eliminarse."
                ),
            )

            return redirect(
                "detalle_orden",
                pk=orden.pk,
            )

    # ---------------------------------------------------------
    # CONFIRMACIÓN
    # ---------------------------------------------------------

    messages.success(
        request,
        (
            f"Abono de ${monto_eliminado:.2f} "
            f"eliminado correctamente."
        ),
    )

    return redirect(
        "detalle_orden",
        pk=orden.pk,
    )