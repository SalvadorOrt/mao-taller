from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..forms import obtener_sucursal_operativa
from ..forms_filas import FilasRepuestos
from ..models import ItemSolicitudCotizacion, SolicitudCotizacion


LECTURA = (
    "cotizaciones.view_solicitudcotizacion",
    "cotizaciones.view_itemsolicitudcotizacion",
    "cotizaciones.view_cotizacionproveedor",
)


def contexto_filas(request, solicitud, datos=None):
    puede_editar = (
        request.user.has_perm(
            "cotizaciones.change_itemsolicitudcotizacion"
        )
        and solicitud.estado != "CANCELADA"
        and solicitud.orden.estado != "ANULADA"
    )

    if not puede_editar:
        return {"editor_filas": None}

    items = solicitud.items.order_by(
        "orden_item",
        "pk",
    )

    numero = (
        datos.get("pagina_filas")
        if datos is not None
        else request.GET.get("filas")
    )

    pagina = Paginator(items, 20).get_page(numero)

    ids = list(
        pagina.object_list.values_list(
            "pk",
            flat=True,
        )
    )

    siguiente = (
        items.aggregate(
            ultimo=Max("orden_item")
        )["ultimo"]
        or 0
    ) + 1

    formset = FilasRepuestos(
        datos,
        queryset=items.filter(pk__in=ids),
        prefix="repuestos",
        form_kwargs={
            "solicitud": solicitud,
            "usuario": request.user,
            "sucursal_activa_id": request.session.get(
                "sucursal_activa_id"
            ),
        },
    )

    puede_agregar = request.user.has_perm(
        "cotizaciones.add_itemsolicitudcotizacion"
    )

    vacio = (
        formset.empty_form
        if puede_agregar
        else None
    )

    if vacio is not None:
        vacio.initial["orden_item"] = siguiente

    return {
        "editor_filas": formset,
        "pagina_filas": pagina,
        "fila_vacia": vacio,
        "siguiente_orden": siguiente,
        "puede_eliminar_fila": request.user.has_perm(
            "cotizaciones.delete_itemsolicitudcotizacion"
        ),
    }


@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_itemsolicitudcotizacion",
    ),
    raise_exception=True,
)
@require_POST
def repuestos_guardar(request, solicitud_pk):
    sucursal = obtener_sucursal_operativa(
        request.user,
        request.session.get("sucursal_activa_id"),
    )

    contexto = {}

    try:
        with transaction.atomic():
            solicitud = get_object_or_404(
                SolicitudCotizacion.objects
                .select_for_update()
                .filter(
                    sucursal_id=sucursal.pk,
                    orden__sucursal_id=sucursal.pk,
                ),
                pk=solicitud_pk,
            )

            if (
                solicitud.estado == "CANCELADA"
                or solicitud.orden.estado == "ANULADA"
            ):
                raise PermissionDenied(
                    "La solicitud o su orden está cancelada."
                )

            list(
                ItemSolicitudCotizacion.objects
                .select_for_update()
                .filter(solicitud=solicitud)
            )

            contexto = contexto_filas(
                request,
                solicitud,
                request.POST,
            )

            formulario = contexto["editor_filas"]

            if formulario.is_valid():
                formulario.save()
                solicitud.actualizar_estado()

                messages.success(
                    request,
                    "Repuestos guardados.",
                )

                url = reverse(
                    "cotizaciones:detalle",
                    args=[solicitud.pk],
                )

                pagina = contexto["pagina_filas"].number

                return redirect(
                    f"{url}?filas={pagina}#editor-repuestos"
                )

    except ValidationError as error:
        contexto["error_guardado"] = " ".join(
            error.messages
        )

    return render(
        request,
        "cotizaciones/torre/repuestos_editar.html",
        {
            **contexto,
            "solicitud": solicitud,
            "sucursal_operativa": sucursal,
        },
    )