from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
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
    (
        valor,
        {
            "MOTOR": "Motor",
            "ENDEREZADO_PINTURA": "Enderezada y pintura",
        }.get(valor, etiqueta),
    )
    for valor, etiqueta in SolicitudCotizacion.TIPOS_TRABAJO
    if valor != "SIN_CLASIFICAR"
]

AVANCES = [
    ("todos", "Todos"),
    ("sin_repuestos", "Sin repuestos"),
    ("pendientes", "Costos pendientes"),
    ("con_costos", "Con costos registrados"),
]

ORDENES = [
    ("recientes", "Más recientes primero"),
    ("antiguos", "Más antiguos primero"),
]


@login_required
@permission_required(
    "cotizaciones.view_solicitudcotizacion",
    raise_exception=True,
)
@require_GET
@never_cache
def lista(request):
    try:
        sucursal = _sucursal(request)
    except PermissionDenied:
        return lista_anterior(request)

    clave_area = f"torre_area_activa_{sucursal.pk}"

    area = (
        request.GET.get("area")
        or request.session.get(clave_area, "MECANICA")
    )

    if area not in dict(AREAS):
        area = AREAS[0][0]

    if request.session.get(clave_area) != area:
        request.session[clave_area] = area

    q = request.GET.get("q", "").strip()[:100]
    avance = request.GET.get("avance", "todos")
    orden = request.GET.get("orden", "recientes")

    if avance not in dict(AVANCES):
        avance = "todos"

    if orden not in dict(ORDENES):
        orden = "recientes"

    # El acceso y los contadores corresponden al mismo
    # control activo del área seleccionada.
    ultimo_control = (
        SolicitudCotizacion.objects
        .filter(
            orden_id=OuterRef("pk"),
            sucursal_id=sucursal.pk,
            tipo_trabajo=area,
        )
        .exclude(estado="CANCELADA")
        .order_by("-pk")
    )

    filtro_control = Q(
        solicitudes_cotizacion__pk=F("control_torre_id")
    )

    ordenes = (
        OrdenTrabajo.objects
        .filter(
            sucursal_id=sucursal.pk,
            estado="ABIERTA",
            es_migrada=False,
        )
        .select_related("cliente")
        .annotate(
            control_torre_id=Subquery(
                ultimo_control.values("pk")[:1]
            )
        )
        .annotate(
            repuestos_torre=Count(
                "solicitudes_cotizacion__items",
                filter=filtro_control,
                distinct=True,
            ),
            repuestos_con_costo=Count(
                "solicitudes_cotizacion__items",
                filter=(
                    filtro_control
                    & Q(
                        solicitudes_cotizacion__items__cotizaciones_proveedor__precio__isnull=False
                    )
                ),
                distinct=True,
            ),
        )
        .annotate(
            costos_pendientes=(
                F("repuestos_torre")
                - F("repuestos_con_costo")
            )
        )
    )

    if q:
        ordenes = ordenes.filter(
            Q(numero_orden__icontains=q)
            | Q(placa__icontains=q)
            | Q(vehiculo__icontains=q)
        )

    if avance == "sin_repuestos":
        ordenes = ordenes.filter(
            repuestos_torre=0,
        )

    elif avance == "pendientes":
        ordenes = ordenes.filter(
            costos_pendientes__gt=0,
        )

    elif avance == "con_costos":
        ordenes = ordenes.filter(
            repuestos_torre__gt=0,
            costos_pendientes=0,
        )

    campos_orden = (
        ("fecha_ingreso", "pk")
        if orden == "antiguos"
        else ("-fecha_ingreso", "-pk")
    )

    ordenes = ordenes.order_by(
        *campos_orden
    )

    pagina = Paginator(
        ordenes,
        25,
    ).get_page(request.GET.get("page"))

    parametros = {
        "q": q,
        "area": area,
        "avance": avance,
        "orden": orden,
    }

    pestanas = [
        {
            "valor": valor,
            "etiqueta": etiqueta,
            "activa": valor == area,
            "url": "?" + urlencode({
                **parametros,
                "area": valor,
            }),
        }
        for valor, etiqueta in AREAS
    ]

    return render(
        request,
        "cotizaciones/torre/lista.html",
        _contexto(
            request,
            pagina=pagina,
            q=q,
            area=area,
            area_etiqueta=dict(AREAS)[area],
            avance=avance,
            orden_seleccionado=orden,
            pestanas=pestanas,
            avances=AVANCES,
            opciones_orden=ORDENES,
            query_filtros=urlencode(parametros),
            puede_ver_detalle=request.user.has_perms(
                LECTURA
            ),
            puede_crear_control=request.user.has_perm(
                "cotizaciones.add_solicitudcotizacion"
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
        return redirect(
            "cotizaciones:lista"
        )

    sucursal = _sucursal(request)

    tipo = request.POST.get(
        "tipo_trabajo",
        "",
    )

    if tipo not in dict(AREAS):
        messages.error(
            request,
            "Selecciona un área de trabajo válida.",
        )
        return redirect(
            "cotizaciones:lista"
        )

    try:
        orden_id = int(
            request.POST.get("orden", "")
        )
    except (TypeError, ValueError):
        messages.error(
            request,
            "Selecciona una OT válida.",
        )
        return redirect(
            "cotizaciones:lista"
        )

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
        return redirect(
            "cotizaciones:lista"
        )

    return redirect(
        "cotizaciones:detalle",
        pk=solicitud.pk,
    )