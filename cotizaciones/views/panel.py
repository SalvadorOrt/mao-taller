from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from ordenes_de_trabajo.models import OrdenTrabajo

from ..models import SolicitudCotizacion
from .torre import (
    LECTURA,
    _contexto,
    _sucursal,
    lista as lista_anterior,
)


AREAS = [
    (valor, etiqueta)
    for valor, etiqueta in SolicitudCotizacion.TIPOS_TRABAJO
    if valor != "SIN_CLASIFICAR"
]


@login_required
@permission_required(
    "cotizaciones.view_solicitudcotizacion",
    raise_exception=True,
)
@require_GET
def lista(request):
    try:
        sucursal = _sucursal(request)
    except PermissionDenied:
        return lista_anterior(request)

    controles = (
        SolicitudCotizacion.objects
        .filter(sucursal_id=sucursal.pk)
        .exclude(estado="CANCELADA")
        .annotate(
            numero_items=Count("items", distinct=True)
        )
        .order_by("tipo_trabajo", "-pk")
    )

    ordenes = (
        OrdenTrabajo.objects
        .filter(
            sucursal_id=sucursal.pk,
            estado="ABIERTA",
            es_migrada=False,
        )
        .select_related("cliente")
        .prefetch_related(
            Prefetch(
                "solicitudes_cotizacion",
                queryset=controles,
                to_attr="controles_torre",
            )
        )
        .order_by("-fecha_ingreso", "-pk")
    )

    q = request.GET.get("q", "").strip()[:100]

    if q:
        ordenes = ordenes.filter(
            Q(numero_orden__icontains=q)
            | Q(placa__icontains=q)
            | Q(vehiculo__icontains=q)
        )

    pagina = Paginator(
        ordenes,
        25,
    ).get_page(request.GET.get("page"))

    for orden in pagina:
        usadas = {
            control.tipo_trabajo
            for control in orden.controles_torre
        }

        orden.areas_disponibles = [
            opcion
            for opcion in AREAS
            if opcion[0] not in usadas
        ]

        orden.repuestos_torre = sum(
            control.numero_items
            for control in orden.controles_torre
        )

    return render(
        request,
        "cotizaciones/torre/lista.html",
        _contexto(
            request,
            pagina=pagina,
            q=q,
            puede_ver_detalle=request.user.has_perms(
                LECTURA
            ),
        ),
    )


@login_required
@permission_required(
    LECTURA + (
        "cotizaciones.add_solicitudcotizacion",
    ),
    raise_exception=True,
)
@require_http_methods(["GET", "POST"])
def solicitud_nueva(request):
    if request.method == "GET":
        return redirect("cotizaciones:lista")

    sucursal = _sucursal(request)
    tipo = request.POST.get("tipo_trabajo", "")

    if tipo not in dict(AREAS):
        messages.error(
            request,
            "Selecciona el área de trabajo en la fila del vehículo.",
        )
        return redirect("cotizaciones:lista")

    try:
        orden_id = int(
            request.POST.get("orden", "")
        )
    except (TypeError, ValueError):
        messages.error(
            request,
            "Selecciona una OT válida.",
        )
        return redirect("cotizaciones:lista")

    try:
        with transaction.atomic():
            orden = get_object_or_404(
                OrdenTrabajo.objects
                .select_for_update()
                .filter(
                    sucursal_id=sucursal.pk,
                    estado="ABIERTA",
                    es_migrada=False,
                ),
                pk=orden_id,
            )

            solicitud = (
                SolicitudCotizacion.objects
                .filter(
                    orden=orden,
                    sucursal=sucursal,
                    tipo_trabajo=tipo,
                )
                .exclude(estado="CANCELADA")
                .order_by("-pk")
                .first()
            )

            if solicitud is None:
                solicitud = SolicitudCotizacion.objects.create(
                    orden=orden,
                    sucursal=sucursal,
                    creada_por=request.user,
                    tipo_trabajo=tipo,
                    titulo=(
                        (orden.placa or "").strip().upper()
                        or f"OT {orden.numero_orden}"
                    ),
                )

    except ValidationError as error:
        messages.error(
            request,
            " ".join(error.messages),
        )
        return redirect("cotizaciones:lista")

    return redirect(
        "cotizaciones:detalle",
        pk=solicitud.pk,
    )