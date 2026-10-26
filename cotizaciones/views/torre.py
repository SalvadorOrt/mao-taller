"""Vistas auxiliares de la torre de control simplificada."""

import mimetypes

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
    permission_required,
)
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import (
    require_GET,
    require_POST,
    require_http_methods,
)

from inventario.models import CodigoProducto

from ..forms import (
    CotizacionProveedorForm,
    FotoItemCotizacionForm,
    ItemSolicitudCotizacionForm,
    SolicitudCotizacionForm,
    obtener_sucursal_operativa,
)
from ..models import (
    CotizacionProveedor,
    FotoItemCotizacion,
    ItemSolicitudCotizacion,
    SolicitudCotizacion,
)


LECTURA = (
    "cotizaciones.view_solicitudcotizacion",
    "cotizaciones.view_itemsolicitudcotizacion",
    "cotizaciones.view_cotizacionproveedor",
)


# =========================================================
# SUCURSAL Y CONTEXTO
# =========================================================

def _sucursal(request):
    return obtener_sucursal_operativa(
        request.user,
        request.session.get("sucursal_activa_id"),
    )


def _argumentos_formulario(request):
    return {
        "usuario": request.user,
        "sucursal_activa_id": request.session.get(
            "sucursal_activa_id"
        ),
    }


def _contexto(request, **datos):
    contexto = {
        "sucursal_operativa": _sucursal(request),

        # El selector de sucursal pertenece al dashboard.
        "puede_cambiar_sucursal": False,
        "sucursales_disponibles": [],
    }

    contexto.update(datos)
    return contexto


# =========================================================
# CONSULTAS LIMITADAS A LA SUCURSAL
# =========================================================

def _solicitudes(request):
    sucursal = _sucursal(request)

    return (
        SolicitudCotizacion.objects
        .filter(
            sucursal_id=sucursal.pk,
            orden__sucursal_id=sucursal.pk,
        )
        .select_related(
            "orden",
            "sucursal",
        )
    )


def _items(request):
    sucursal = _sucursal(request)

    return (
        ItemSolicitudCotizacion.objects
        .filter(
            solicitud__sucursal_id=sucursal.pk,
            solicitud__orden__sucursal_id=sucursal.pk,
        )
        .select_related(
            "solicitud__orden",
            "solicitud__sucursal",
        )
    )


def _ofertas(request):
    sucursal = _sucursal(request)

    return (
        CotizacionProveedor.objects
        .filter(
            item__solicitud__sucursal_id=sucursal.pk,
            item__solicitud__orden__sucursal_id=sucursal.pk,
        )
        .select_related(
            "item__solicitud__orden",
            "item__solicitud__sucursal",
        )
    )


# =========================================================
# VALIDACIONES Y FORMULARIOS
# =========================================================

def _abierta(solicitud):
    return (
        solicitud.estado != "CANCELADA"
        and solicitud.orden.estado != "ANULADA"
    )


def _exigir_abierta(solicitud):
    if not _abierta(solicitud):
        raise PermissionDenied(
            "La solicitud o su orden de trabajo está cancelada."
        )


def _guardar_formulario(formulario):
    if formulario.is_valid():
        try:
            return formulario.save()

        except ValidationError as error:
            formulario.add_error(None, error)

    return None


def _pantalla_formulario(
    request,
    formulario,
    titulo,
    solicitud,
    **datos,
):
    return render(
        request,
        "cotizaciones/torre/formulario.html",
        _contexto(
            request,
            formulario=formulario,
            titulo=titulo,
            solicitud=solicitud,
            volver_url=reverse(
                "cotizaciones:detalle",
                args=[solicitud.pk],
            ),
            **datos,
        ),
    )


# =========================================================
# COMPATIBILIDAD CON EL PANEL PRINCIPAL
# =========================================================

@login_required
@permission_required(
    "cotizaciones.view_solicitudcotizacion",
    raise_exception=True,
)
@require_GET
def lista(request):
    """
    El listado principal está en panel.py.

    Si falta la sucursal, devuelve al dashboard.
    """

    try:
        _sucursal(request)

    except PermissionDenied as error:
        messages.error(
            request,
            str(error),
        )

        return redirect("dashboard")

    # Importación local para evitar un ciclo con panel.py.
    from .panel import lista as lista_panel

    return lista_panel(request)


# =========================================================
# EDITAR SOLICITUD
# =========================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_solicitudcotizacion",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def solicitud_editar(request, pk):
    solicitud = get_object_or_404(
        _solicitudes(request),
        pk=pk,
    )

    _exigir_abierta(solicitud)

    formulario = SolicitudCotizacionForm(
        request.POST if request.method == "POST" else None,
        instance=solicitud,
        **_argumentos_formulario(request),
    )

    formulario.fields["orden"].widget = forms.HiddenInput()

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Solicitud actualizada.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=solicitud.pk,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Editar solicitud",
        solicitud,
    )


# =========================================================
# FORMULARIO INDIVIDUAL DE REPUESTO
# =========================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_itemsolicitudcotizacion",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def item_nuevo(request, solicitud_pk):
    solicitud = get_object_or_404(
        _solicitudes(request),
        pk=solicitud_pk,
    )

    _exigir_abierta(solicitud)

    siguiente = (
        solicitud.items.aggregate(
            ultimo=Max("orden_item")
        )["ultimo"]
        or 0
    ) + 1

    formulario = ItemSolicitudCotizacionForm(
        request.POST if request.method == "POST" else None,
        solicitud=solicitud,
        initial={
            "orden_item": siguiente,
        },
        **_argumentos_formulario(request),
    )

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Repuesto agregado.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=solicitud.pk,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Agregar repuesto",
        solicitud,
    )


@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_itemsolicitudcotizacion",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def item_editar(request, pk):
    item = get_object_or_404(
        _items(request),
        pk=pk,
    )

    _exigir_abierta(item.solicitud)

    formulario = ItemSolicitudCotizacionForm(
        request.POST if request.method == "POST" else None,
        instance=item,
        solicitud=item.solicitud,
        **_argumentos_formulario(request),
    )

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Repuesto actualizado.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=item.solicitud_id,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Editar repuesto",
        item.solicitud,
        item=item,
    )


# =========================================================
# FORMULARIO INDIVIDUAL DE COSTO
# =========================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_cotizacionproveedor",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def oferta_nueva(request, item_pk):
    item = get_object_or_404(
        _items(request),
        pk=item_pk,
    )

    _exigir_abierta(item.solicitud)

    formulario = CotizacionProveedorForm(
        request.POST if request.method == "POST" else None,
        item=item,
        **_argumentos_formulario(request),
    )

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Costo guardado.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=item.solicitud_id,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Registrar costo",
        item.solicitud,
        item=item,
    )


@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_cotizacionproveedor",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def oferta_editar(request, pk):
    oferta = get_object_or_404(
        _ofertas(request),
        pk=pk,
    )

    item = oferta.item

    _exigir_abierta(item.solicitud)

    formulario = CotizacionProveedorForm(
        request.POST if request.method == "POST" else None,
        instance=oferta,
        item=item,
        **_argumentos_formulario(request),
    )

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Costo actualizado.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=item.solicitud_id,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Editar costo",
        item.solicitud,
        item=item,
        oferta=oferta,
    )


# =========================================================
# AGREGAR FOTOGRAFÍA
# =========================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_fotoitemcotizacion",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def foto_nueva(request, item_pk):
    item = get_object_or_404(
        _items(request),
        pk=item_pk,
    )

    _exigir_abierta(item.solicitud)

    formulario = FotoItemCotizacionForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        item=item,
        **_argumentos_formulario(request),
    )

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Foto agregada.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=item.solicitud_id,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Agregar foto",
        item.solicitud,
        item=item,
    )


# =========================================================
# MOSTRAR FOTOGRAFÍA
# =========================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.view_fotoitemcotizacion",
    ),
    raise_exception=True,
)
@require_GET
def foto(request, pk):
    sucursal = _sucursal(request)

    imagen = get_object_or_404(
        FotoItemCotizacion.objects.filter(
            item__solicitud__sucursal_id=sucursal.pk,
            item__solicitud__orden__sucursal_id=sucursal.pk,
        ),
        pk=pk,
    )

    try:
        archivo = imagen.imagen.open("rb")

    except (OSError, ValueError):
        raise Http404(
            "La imagen no está disponible."
        ) from None

    tipo = mimetypes.guess_type(
        imagen.imagen.name
    )[0]

    permitido = tipo in {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/tiff",
    }

    respuesta = FileResponse(
        archivo,
        content_type=(
            tipo
            if permitido
            else "application/octet-stream"
        ),
        as_attachment=not permitido,
    )

    respuesta["Cache-Control"] = "private, no-store"
    respuesta["X-Content-Type-Options"] = "nosniff"

    return respuesta


# =========================================================
# CAMBIO DE SUCURSAL: COMPATIBILIDAD
# =========================================================

@login_required
@permission_required(
    "cotizaciones.view_solicitudcotizacion",
    raise_exception=True,
)
@require_POST
def cambiar_sucursal(request):
    puede_cambiar = (
        request.user.is_superuser
        or request.user.has_perm(
            "inventario.cambiar_sucursal_operativa"
        )
    )

    if not puede_cambiar:
        raise PermissionDenied(
            "No tienes permiso para cambiar de sucursal."
        )

    identificador = request.POST.get("sucursal_id")

    if not identificador:
        raise PermissionDenied(
            "Selecciona una sucursal válida."
        )

    sucursal = obtener_sucursal_operativa(
        request.user,
        identificador,
    )

    request.session["sucursal_activa_id"] = sucursal.pk

    messages.success(
        request,
        f"Sucursal operativa: {sucursal.nombre}.",
    )

    return redirect("cotizaciones:lista")


# =========================================================
# CONSULTA DEL CATÁLOGO EXISTENTE
# =========================================================

@login_required
@permission_required(
    LECTURA,
    raise_exception=True,
)
@require_GET
def codigos_producto(request):
    _sucursal(request)

    permisos = (
        "cotizaciones.add_itemsolicitudcotizacion",
        "cotizaciones.change_itemsolicitudcotizacion",
    )

    if not any(
        request.user.has_perm(permiso)
        for permiso in permisos
    ):
        raise PermissionDenied(
            "No tienes permiso para consultar estos códigos."
        )

    try:
        producto_id = int(
            request.GET.get(
                "producto_id",
                "",
            )
        )

    except (TypeError, ValueError):
        return JsonResponse({
            "resultados": [],
        })

    codigos = (
        CodigoProducto.objects
        .filter(producto_id=producto_id)
        .order_by("pk")
    )

    return JsonResponse({
        "resultados": [
            {
                "id": codigo.pk,
                "texto": (
                    " · ".join(
                        parte
                        for parte in (
                            codigo.codigo,
                            codigo.nombre_comercial,
                        )
                        if parte
                    )
                    or f"Código {codigo.pk}"
                ),
            }
            for codigo in codigos
        ],
    })