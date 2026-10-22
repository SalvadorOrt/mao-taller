"""Pantallas de la torre de control de repuestos."""

import mimetypes
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max, Prefetch, Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from inventario.models import CodigoProducto
from ordenes_de_trabajo.models import OrdenTrabajo, Sucursal

from ..forms import (
    CotizacionProveedorForm,
    FiltroTorreControlForm,
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


# =====================================================
# SUCURSAL Y CONTEXTO
# =====================================================

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
    puede_cambiar = (
        request.user.is_superuser
        or request.user.has_perm(
            "inventario.cambiar_sucursal_operativa"
        )
    )

    contexto = {
        "sucursal_operativa": _sucursal(request),
        "puede_cambiar_sucursal": puede_cambiar,
        "sucursales_disponibles": (
            Sucursal.objects.filter(
                activa=True
            ).order_by("nombre")
            if puede_cambiar
            else []
        ),
    }

    contexto.update(datos)
    return contexto


# =====================================================
# CONSULTAS LIMITADAS A LA SUCURSAL OPERATIVA
# =====================================================

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
            "proveedor",
        )
    )


# =====================================================
# VALIDACIONES Y FORMULARIOS
# =====================================================

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
    """
    Presenta también los errores ocurridos al guardar,
    si los datos cambiaron después de validar.
    """
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


# =====================================================
# LISTADO DE SOLICITUDES
# =====================================================

@login_required
@permission_required(
    "cotizaciones.view_solicitudcotizacion",
    raise_exception=True,
)
@require_GET
def lista(request):
    try:
        _sucursal(request)

    except PermissionDenied as error:
        puede_cambiar = (
            request.user.is_superuser
            or request.user.has_perm(
                "inventario.cambiar_sucursal_operativa"
            )
        )

        if not request.user.is_active or not puede_cambiar:
            raise

        return render(
            request,
            "cotizaciones/torre/elegir_sucursal.html",
            {
                "sucursales_disponibles": (
                    Sucursal.objects
                    .filter(activa=True)
                    .order_by("nombre")
                ),
                "motivo_sucursal": str(error),
            },
        )

    formulario = FiltroTorreControlForm(request.GET)

    for campo in formulario.fields.values():
        campo.widget.attrs["class"] = (
            "form-select"
            if isinstance(campo.widget, forms.Select)
            else "form-control"
        )

    formulario.fields["q"].widget.attrs["placeholder"] = (
        "OT, placa, vehículo o repuesto"
    )

    solicitudes = _solicitudes(request).annotate(
        numero_items=Count(
            "items",
            distinct=True,
        )
    )

    if formulario.is_valid():
        datos = formulario.cleaned_data

        if datos["q"]:
            texto = datos["q"]

            solicitudes = solicitudes.filter(
                Q(titulo__icontains=texto)
                | Q(orden__numero_orden__icontains=texto)
                | Q(orden__placa__icontains=texto)
                | Q(orden__vehiculo__icontains=texto)
                | Q(items__descripcion_solicitada__icontains=texto)
            )

        if datos["tipo_trabajo"]:
            solicitudes = solicitudes.filter(
                tipo_trabajo=datos["tipo_trabajo"]
            )

        if datos["estado"]:
            solicitudes = solicitudes.filter(
                estado=datos["estado"]
            )

    else:
        solicitudes = solicitudes.none()

    solicitudes = solicitudes.distinct().order_by(
        "-creada_en",
        "-pk",
    )

    pagina = Paginator(
        solicitudes,
        25,
    ).get_page(request.GET.get("page"))

    parametros = request.GET.copy()
    parametros.pop("page", None)

    pestanas = []

    for valor, etiqueta in (
        [("", "Todas")]
        + SolicitudCotizacion.TIPOS_TRABAJO
    ):
        enlace = parametros.copy()
        enlace["tipo_trabajo"] = valor

        pestanas.append({
            "etiqueta": etiqueta,
            "query": enlace.urlencode(),
            "activa": (
                request.GET.get("tipo_trabajo", "")
                == valor
            ),
        })

    return render(
        request,
        "cotizaciones/torre/lista.html",
        _contexto(
            request,
            formulario=formulario,
            pagina=pagina,
            parametros_pagina=parametros.urlencode(),
            pestanas=pestanas,
            puede_ver_detalle=request.user.has_perms(
                LECTURA
            ),
        ),
    )


# =====================================================
# CREAR SOLICITUD
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_solicitudcotizacion",
    ),
    raise_exception=True,
)
@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_solicitudcotizacion",
    ),
    raise_exception=True,
)
def solicitud_nueva(request):
    sucursal = _sucursal(request)

    # Mismo criterio que utiliza el dashboard del taller.
    ordenes = (
        OrdenTrabajo.objects
        .filter(
            sucursal_id=sucursal.pk,
            estado="ABIERTA",
            es_migrada=False,
        )
        .order_by(
            "-fecha_ingreso",
            "-pk",
        )
    )

    orden_id = (
        request.GET.get("orden")
        or request.POST.get("orden")
    )

    orden = None

    if orden_id:
        try:
            identificador = int(orden_id)
        except (TypeError, ValueError):
            raise Http404(
                "Orden de trabajo no válida."
            ) from None

        orden = get_object_or_404(
            ordenes,
            pk=identificador,
        )

    if request.method == "POST" and orden is None:
        raise Http404(
            "Selecciona una orden abierta del taller."
        )

    formulario = None

    if orden:
        formulario = SolicitudCotizacionForm(
            request.POST
            if request.method == "POST"
            else None,
            initial={
                "orden": orden,
            },
            **_argumentos_formulario(request),
        )

        formulario.fields["orden"].queryset = (
            ordenes.filter(pk=orden.pk)
        )

        formulario.fields["orden"].widget = (
            forms.HiddenInput()
        )

        formulario.fields["orden"].disabled = True

        if request.method == "POST":
            solicitud = _guardar_formulario(
                formulario
            )

            if solicitud:
                messages.success(
                    request,
                    "Solicitud creada. Ahora agrega los repuestos.",
                )

                return redirect(
                    "cotizaciones:detalle",
                    pk=solicitud.pk,
                )

    busqueda = (
        request.GET.get("q_ot", "")
        .strip()[:100]
    )

    pagina_ordenes = None

    if orden is None:
        resultados = ordenes

        # Siempre mostramos las órdenes.
        # El filtro se aplica solamente cuando escribes algo.
        if busqueda:
            resultados = resultados.filter(
                Q(numero_orden__icontains=busqueda)
                | Q(placa__icontains=busqueda)
                | Q(vehiculo__icontains=busqueda)
            )

        pagina_ordenes = Paginator(
            resultados,
            20,
        ).get_page(
            request.GET.get("page")
        )

    parametros = request.GET.copy()
    parametros.pop("page", None)
    parametros.pop("orden", None)

    return render(
        request,
        "cotizaciones/torre/nueva_solicitud.html",
        _contexto(
            request,
            titulo="Seleccionar OT del taller",
            orden_elegida=orden,
            formulario=formulario,
            busqueda=busqueda,
            pagina_ordenes=pagina_ordenes,
            parametros_pagina=parametros.urlencode(),
            volver_url=reverse(
                "cotizaciones:lista"
            ),
        ),
    )


# =====================================================
# EDITAR SOLICITUD
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_solicitudcotizacion",
    ),
    raise_exception=True,
)
def solicitud_editar(request, pk):
    solicitud = get_object_or_404(
        _solicitudes(request),
        pk=pk,
    )

    _exigir_abierta(solicitud)

    formulario = SolicitudCotizacionForm(
        request.POST
        if request.method == "POST"
        else None,
        instance=solicitud,
        **_argumentos_formulario(request),
    )

    formulario.fields["orden"].widget = (
        forms.HiddenInput()
    )

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


# =====================================================
# COMPARACIÓN DE OFERTAS
# =====================================================

def _motivos_no_comparable(oferta):
    motivos = []

    if oferta.disponible is False:
        motivos.append(
            "No disponible"
        )

    elif oferta.disponible is None:
        motivos.append(
            "Disponibilidad por confirmar"
        )

    if oferta.precio is None:
        motivos.append(
            "Falta costo"
        )

    if oferta.item.unidad == "POR_DEFINIR":
        motivos.append(
            "Falta unidad solicitada"
        )

    if oferta.presentacion == "POR_DEFINIR":
        motivos.append(
            "Falta presentación"
        )

    if not oferta.unidades_por_presentacion:
        motivos.append(
            "Falta equivalencia"
        )

    if oferta.tratamiento_iva == "POR_DEFINIR":
        motivos.append(
            "IVA por confirmar"
        )

    elif (
        oferta.tratamiento_iva == "ADICIONAL"
        and oferta.porcentaje_iva is None
    ):
        motivos.append(
            "Falta porcentaje de IVA"
        )

    if not oferta.medida_compatible:
        motivos.append(
            "Medida pendiente o diferente"
        )

    if oferta.estado not in {
        "RESPONDIO",
        "GANADORA",
    }:
        motivos.append(
            oferta.get_estado_display()
        )

    return motivos or [
        "Revisa los datos de la oferta"
    ]


# =====================================================
# DETALLE Y TABLA EDITABLE
# =====================================================

@login_required
@permission_required(
    LECTURA,
    raise_exception=True,
)
@require_GET
def detalle(request, pk):
    solicitud = get_object_or_404(
        _solicitudes(request),
        pk=pk,
    )

    ver_fotos = request.user.has_perm(
        "cotizaciones.view_fotoitemcotizacion"
    )

    ofertas_qs = (
        CotizacionProveedor.objects
        .select_related("proveedor")
        .order_by(
            "proveedor_id",
            "numero_opcion",
            "pk",
        )
    )

    items_qs = (
        solicitud.items
        .prefetch_related(
            Prefetch(
                "cotizaciones_proveedor",
                queryset=ofertas_qs,
            )
        )
        .order_by(
            "orden_item",
            "pk",
        )
    )

    if ver_fotos:
        items_qs = items_qs.prefetch_related(
            "fotos"
        )

    items = list(items_qs)

    proveedores = {}
    preparados = []

    seleccionados = 0
    comprados = 0
    suma = Decimal("0.00")
    elegidos_sin_total = 0

    for item in items:
        grupos = {}
        tarjetas = []

        for oferta in item.cotizaciones_proveedor.all():
            oferta.item = item

            proveedores[
                oferta.proveedor_id
            ] = oferta.proveedor

            total = oferta.costo_requerimiento

            tarjeta = {
                "oferta": oferta,
                "total": total,
                "comparable": total is not None,
                "seleccionada": (
                    oferta.estado == "GANADORA"
                ),
                "presentaciones": (
                    oferta.presentaciones_necesarias
                ),
                "motivos": (
                    _motivos_no_comparable(oferta)
                    if total is None
                    else []
                ),
            }

            tarjetas.append(tarjeta)

            grupos.setdefault(
                oferta.proveedor_id,
                [],
            ).append(tarjeta)

        comparables = [
            tarjeta
            for tarjeta in tarjetas
            if tarjeta["comparable"]
        ]

        menor = min(
            (
                tarjeta["total"]
                for tarjeta in comparables
            ),
            default=None,
        )

        for tarjeta in tarjetas:
            tarjeta["menor_costo"] = (
                menor is not None
                and tarjeta["total"] == menor
            )

        elegida = next(
            (
                tarjeta
                for tarjeta in tarjetas
                if tarjeta["seleccionada"]
            ),
            None,
        )

        if elegida:
            seleccionados += 1

            if elegida["total"] is not None:
                suma += elegida["total"]
            else:
                elegidos_sin_total += 1

        if item.estado_abastecimiento == "COMPRADO":
            comprados += 1

        preparados.append({
            "item": item,
            "grupos": grupos,
            "seleccionada": elegida,
            "fotos": (
                list(item.fotos.all())
                if ver_fotos
                else []
            ),
            "editable": _abierta(solicitud),
            "puede_cotizar": (
                _abierta(solicitud)
                and item.estado_abastecimiento != "COMPRADO"
            ),
            "puede_comprar": bool(
                _abierta(solicitud)
                and elegida
                and elegida["comparable"]
                and item.estado_abastecimiento != "COMPRADO"
            ),
        })

    columnas = sorted(
        proveedores.values(),
        key=lambda prov: (
            (
                prov.empresa
                or prov.nombre_contacto
                or ""
            ).casefold(),
            prov.pk,
        ),
    )

    for fila in preparados:
        fila["celdas"] = [
            {
                "proveedor": prov,
                "tarjetas": fila["grupos"].get(
                    prov.pk,
                    [],
                ),
            }
            for prov in columnas
        ]

    return render(
        request,
        "cotizaciones/torre/detalle.html",
        _contexto(
            request,
            solicitud=solicitud,
            columnas=columnas,
            filas=preparados,
            abierta=_abierta(solicitud),
            total_items=len(items),
            seleccionados=seleccionados,
            comprados=comprados,
            total_seleccionado=suma,
            total_incompleto=(
                seleccionados != len(items)
                or elegidos_sin_total > 0
            ),
            elegidos_sin_total=elegidos_sin_total,
            
        ),
    )


# =====================================================
# AGREGAR REPUESTO MEDIANTE FORMULARIO COMPLETO
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_itemsolicitudcotizacion",
    ),
    raise_exception=True,
)
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
        request.POST
        if request.method == "POST"
        else None,
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
        es_formulario_item=True,
    )


# =====================================================
# EDITAR REPUESTO MEDIANTE FORMULARIO COMPLETO
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_itemsolicitudcotizacion",
    ),
    raise_exception=True,
)
def item_editar(request, pk):
    item = get_object_or_404(
        _items(request),
        pk=pk,
    )

    _exigir_abierta(item.solicitud)

    formulario = ItemSolicitudCotizacionForm(
        request.POST
        if request.method == "POST"
        else None,
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
        es_formulario_item=True,
    )


# =====================================================
# REGISTRAR OFERTA DE PROVEEDOR
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_cotizacionproveedor",
    ),
    raise_exception=True,
)
def oferta_nueva(request, item_pk):
    item = get_object_or_404(
        _items(request),
        pk=item_pk,
    )

    _exigir_abierta(item.solicitud)

    if item.estado_abastecimiento == "COMPRADO":
        raise PermissionDenied(
            "Este repuesto ya está comprado."
        )

    formulario = CotizacionProveedorForm(
        request.POST
        if request.method == "POST"
        else None,
        item=item,
        **_argumentos_formulario(request),
    )

    if (
        request.method == "POST"
        and _guardar_formulario(formulario)
    ):
        messages.success(
            request,
            "Oferta guardada.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=item.solicitud_id,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Registrar oferta",
        item.solicitud,
        item=item,
        es_oferta=True,
    )


# =====================================================
# EDITAR OFERTA DE PROVEEDOR
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_cotizacionproveedor",
    ),
    raise_exception=True,
)
def oferta_editar(request, pk):
    oferta = get_object_or_404(
        _ofertas(request),
        pk=pk,
    )

    item = oferta.item

    _exigir_abierta(item.solicitud)

    if item.estado_abastecimiento == "COMPRADO":
        raise PermissionDenied(
            "Las ofertas de un repuesto comprado están bloqueadas."
        )

    formulario = CotizacionProveedorForm(
        request.POST
        if request.method == "POST"
        else None,
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
            "Oferta actualizada.",
        )

        return redirect(
            "cotizaciones:detalle",
            pk=item.solicitud_id,
        )

    return _pantalla_formulario(
        request,
        formulario,
        "Editar oferta",
        item.solicitud,
        item=item,
        es_oferta=True,
    )


# =====================================================
# SELECCIONAR OFERTA GANADORA
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_cotizacionproveedor",
    ),
    raise_exception=True,
)
@require_POST
def oferta_seleccionar(request, pk):
    oferta = get_object_or_404(
        _ofertas(request),
        pk=pk,
    )

    try:
        oferta.seleccionar()

    except ValidationError as error:
        messages.error(
            request,
            " ".join(error.messages),
        )

    else:
        messages.success(
            request,
            "Oferta seleccionada para este repuesto.",
        )

    return redirect(
        "cotizaciones:detalle",
        pk=oferta.item.solicitud_id,
    )


# =====================================================
# MARCAR REPUESTO COMO COMPRADO
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.change_itemsolicitudcotizacion",
    ),
    raise_exception=True,
)
@require_POST
def item_comprado(request, pk):
    item = get_object_or_404(
        _items(request),
        pk=pk,
    )

    try:
        item.marcar_comprado()

    except ValidationError as error:
        messages.error(
            request,
            " ".join(error.messages),
        )

    else:
        messages.success(
            request,
            "Repuesto marcado como comprado.",
        )

    return redirect(
        "cotizaciones:detalle",
        pk=item.solicitud_id,
    )


# =====================================================
# AGREGAR FOTOGRAFÍA
# =====================================================

@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_fotoitemcotizacion",
    ),
    raise_exception=True,
)
def foto_nueva(request, item_pk):
    item = get_object_or_404(
        _items(request),
        pk=item_pk,
    )

    _exigir_abierta(item.solicitud)

    formulario = FotoItemCotizacionForm(
        request.POST
        if request.method == "POST"
        else None,
        request.FILES
        if request.method == "POST"
        else None,
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


# =====================================================
# MOSTRAR FOTOGRAFÍA
# =====================================================

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


# =====================================================
# CAMBIAR SUCURSAL OPERATIVA
# =====================================================

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

    identificador = request.POST.get(
        "sucursal_id"
    )

    if not identificador:
        raise PermissionDenied(
            "Selecciona una sucursal válida."
        )

    sucursal = obtener_sucursal_operativa(
        request.user,
        identificador,
    )

    # Misma clave que utiliza el dashboard.
    request.session["sucursal_activa_id"] = sucursal.pk

    messages.success(
        request,
        f"Sucursal operativa: {sucursal.nombre}.",
    )

    return redirect(
        "cotizaciones:lista"
    )


# =====================================================
# CÓDIGOS DEL PRODUCTO
# =====================================================

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