from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from ...models import (
    ExpedienteVehiculo,
    OrdenTrabajo,
)


# ==========================================================
# UTILIDADES
# ==========================================================


def _decimal(valor):
    if valor is None:
        return Decimal("0.00")

    return Decimal(str(valor))


def _normalizar_procedimientos(procedimientos):
    resultado = []

    for procedimiento in procedimientos or []:

        if procedimiento is None:
            continue

        if isinstance(procedimiento, str):

            texto = procedimiento.strip()

        elif isinstance(procedimiento, dict):

            texto = (
                procedimiento.get("descripcion")
                or procedimiento.get("texto")
                or procedimiento.get("nombre")
                or ""
            )

            texto = str(texto).strip()

        else:

            texto = str(
                procedimiento
            ).strip()

        if texto:
            resultado.append(
                texto
            )

    return resultado


# ==========================================================
# PREPARAR HISTORIAL
# ==========================================================


def preparar_ordenes_historial(
    expediente,
    excluir_orden_id=None,
    solo_anteriores_a=None,
):
    """
    Prepara todas las órdenes de un expediente para mostrarlas
    en modo consulta.

    Esta función es utilizada por:

    1. El historial individual del vehículo.
    2. El modal de historial dentro de una Orden de Trabajo.

    Unifica:

    - Repuestos actuales.
    - Repuestos históricos / migrados.
    - Mano de obra interna actual.
    - Mano de obra externa actual.
    - Mano de obra histórica / migrada.
    - Procedimientos.
    - Técnicos.
    - Subtotales.
    - Abonos.

    Parámetros:

    excluir_orden_id:
        Permite excluir una OT específica.

    solo_anteriores_a:
        Si recibe una OrdenTrabajo, solo devuelve las órdenes
        cronológicamente anteriores a esa OT.
    """

    # ======================================================
    # QUERY BASE
    # ======================================================

    queryset = (
        expediente.ordenes
        .select_related(
            "sucursal",
            "cliente",
            "usuario_receptor",
        )
        .prefetch_related(

            # Técnicos
            "tecnicos",

            # Servicios actuales
            "servicios_detalles__servicio",
            "servicios_detalles__tecnico_responsable",
            "servicios_detalles__procedimientos_detalle",

            # Servicios históricos
            "servicios_historicos",

            # Repuestos
            "insumos_detalles",
            "insumos_historicos",

            # Recepción
            "sintomas_items",
            "trabajos_solicitados_items",

            # Recomendaciones
            "recomendaciones_items",

            # Abonos
            "abonos",
            "abonos__usuario",
        )
    )

    # ======================================================
    # EXCLUIR UNA OT
    # ======================================================

    if excluir_orden_id is not None:

        queryset = queryset.exclude(
            pk=excluir_orden_id
        )

    # ======================================================
    # SOLO VISITAS ANTERIORES
    # ======================================================

    if solo_anteriores_a is not None:

        queryset = queryset.filter(

            Q(
                fecha_ingreso__lt=
                solo_anteriores_a.fecha_ingreso
            )

            |

            Q(
                fecha_ingreso=
                solo_anteriores_a.fecha_ingreso,
                id__lt=
                solo_anteriores_a.id,
            )

        )

    # ======================================================
    # ORDEN CRONOLÓGICO
    # ======================================================

    ordenes = list(

        queryset.order_by(
            "fecha_ingreso",
            "id",
        )

    )

    # ==========================================================
    # POSICIÓN Y DIFERENCIA DE KILOMETRAJE
    # ==========================================================

    kilometraje_anterior = None

    for posicion, orden in enumerate(
        ordenes,
        start=1,
    ):

        orden.posicion_historial = (
            posicion
        )

        orden.diferencia_km = None

        orden.kilometraje_inconsistente = (
            False
        )

        if orden.kilometraje is None:
            continue

        if kilometraje_anterior is not None:

            diferencia = (
                orden.kilometraje
                - kilometraje_anterior
            )

            if diferencia >= 0:

                orden.diferencia_km = (
                    diferencia
                )

            else:

                orden.kilometraje_inconsistente = (
                    True
                )

        kilometraje_anterior = (
            orden.kilometraje
        )

    # ==========================================================
    # PREPARAR INFORMACIÓN DE CADA ORDEN
    # ==========================================================

    for orden in ordenes:

        repuestos = []

        moi = []

        moe = []

        # ======================================================
        # REPUESTOS ACTUALES
        # ======================================================

        for item in orden.insumos_detalles.all():

            referencia = (

                item.codigo_empaque_referencia

                or item.codigo_barras_referencia

                or "[ TEXTO LIBRE / MANUAL ]"

            )

            repuestos.append({

                "referencia":
                    referencia,

                "descripcion": (
                    item.descripcion_factura
                    or "SIN DESCRIPCIÓN"
                ),

                "precio_unitario":
                    item.precio_unitario,

                "cantidad":
                    item.cantidad,

                "subtotal":
                    item.subtotal,

                "es_historico":
                    False,

            })

        # ======================================================
        # REPUESTOS HISTÓRICOS / MIGRADOS
        # ======================================================

        for item in orden.insumos_historicos.all():

            repuestos.append({

                "referencia": (
                    item.codigo_original
                    or "[ HISTÓRICO ]"
                ),

                "descripcion": (
                    item.descripcion_original
                    or "SIN DESCRIPCIÓN"
                ),

                "precio_unitario":
                    item.precio_unitario,

                "cantidad":
                    item.cantidad,

                "subtotal":
                    item.subtotal,

                "es_historico":
                    True,

            })

        # ======================================================
        # SERVICIOS ACTUALES
        # ======================================================

        for item in orden.servicios_detalles.all():

            codigo_servicio = None

            if item.servicio:

                codigo_servicio = getattr(
                    item.servicio,
                    "codigo",
                    None,
                )

            # --------------------------------------------------
            # PROCEDIMIENTOS / SUBMANOS
            # --------------------------------------------------

            procedimientos = [

                procedimiento.descripcion

                for procedimiento
                in item.procedimientos_detalle.all()

                if procedimiento.descripcion

            ]

            fila = {

                "referencia": (
                    codigo_servicio
                    or "[ MANUAL ]"
                ),

                "descripcion": (
                    item.descripcion_servicio
                    or "SIN DESCRIPCIÓN"
                ),

                "tecnico": (

                    item.tecnico_responsable.nombre

                    if item.tecnico_responsable

                    else None

                ),

                "precio_unitario":
                    item.precio_unitario,

                "cantidad":
                    item.cantidad,

                "subtotal":
                    item.subtotal,

                "procedimientos":
                    procedimientos,

                "es_cortesia":
                    False,

                "es_historico":
                    False,

            }

            # --------------------------------------------------
            # MOI / MOE
            # --------------------------------------------------

            if item.tipo_servicio == "EXT":

                moe.append(
                    fila
                )

            else:

                moi.append(
                    fila
                )

        # ======================================================
        # SERVICIOS HISTÓRICOS / MIGRADOS
        # ======================================================

        for item in orden.servicios_historicos.all():

            fila = {

                "referencia":
                    "[ HISTÓRICO ]",

                "descripcion": (
                    item.descripcion_original
                    or "SIN DESCRIPCIÓN"
                ),

                "tecnico":
                    None,

                "precio_unitario":
                    item.precio_unitario,

                "cantidad":
                    item.cantidad,

                "subtotal":
                    item.subtotal,

                "procedimientos":
                    _normalizar_procedimientos(
                        item.procedimientos
                    ),

                "es_cortesia":
                    item.es_cortesia,

                "es_historico":
                    True,

            }

            if item.tipo == "MOE":

                moe.append(
                    fila
                )

            else:

                moi.append(
                    fila
                )

        # ======================================================
        # DATOS UNIFICADOS
        # ======================================================

        orden.repuestos_consulta = (
            repuestos
        )

        orden.moi_consulta = (
            moi
        )

        orden.moe_consulta = (
            moe
        )

        # ======================================================
        # TÉCNICOS ASIGNADOS A TODA LA OT
        # ======================================================

        orden.tecnicos_consulta = list(

            orden.tecnicos.all()

        )

        # ======================================================
        # SUBTOTAL REPUESTOS
        # ======================================================

        orden.subtotal_repuestos_consulta = sum(

            (

                _decimal(
                    item["subtotal"]
                )

                for item in repuestos

            ),

            Decimal("0.00"),

        )

        # ======================================================
        # SUBTOTAL MANO DE OBRA INTERNA
        # ======================================================

        orden.subtotal_moi_consulta = sum(

            (

                _decimal(
                    item["subtotal"]
                )

                for item in moi

            ),

            Decimal("0.00"),

        )

        # ======================================================
        # SUBTOTAL MANO DE OBRA EXTERNA
        # ======================================================

        orden.subtotal_moe_consulta = sum(

            (

                _decimal(
                    item["subtotal"]
                )

                for item in moe

            ),

            Decimal("0.00"),

        )

        # ======================================================
        # ABONOS
        # ======================================================

        orden.abonos_consulta = list(

            orden.abonos.all()

        )

        orden.total_abonado_consulta = sum(

            (

                _decimal(
                    abono.monto
                )

                for abono
                in orden.abonos_consulta

                if abono.estado != "ANULADO"

            ),

            Decimal("0.00"),

        )

        # ======================================================
        # SALDO PENDIENTE
        # ======================================================

        orden.saldo_pendiente_consulta = max(

            _decimal(
                orden.total_final
            )

            - orden.total_abonado_consulta,

            Decimal("0.00"),

        )

    return ordenes


# ==========================================================
# BUSCADOR DE HISTORIAL DE VEHÍCULOS
# ==========================================================


@login_required
def historial_vehiculos(request):

    q = request.GET.get(
        "q",
        "",
    ).strip().upper()

    expedientes = (
        ExpedienteVehiculo.objects.none()
    )

    if q:

        expedientes = (

            ExpedienteVehiculo.objects

            .select_related(
                "cliente"
            )

            .filter(

                Q(
                    placa__icontains=q
                )

                |

                Q(
                    vehiculo__icontains=q
                )

                |

                Q(
                    cliente__nombre_completo__icontains=q
                )

                |

                Q(
                    cliente_respaldo__icontains=q
                ),

                activo=True,

            )

            .order_by(
                "placa",
                "vehiculo",
                "id",
            )

        )

    return render(

        request,

        "historial/historial_vehiculos.html",

        {

            "q":
                q,

            "expedientes":
                expedientes,

        },

    )


# ==========================================================
# DETALLE COMPLETO DEL EXPEDIENTE
# ==========================================================


@login_required
def detalle_expediente(
    request,
    pk,
):

    expediente = get_object_or_404(

        ExpedienteVehiculo.objects
        .select_related(
            "cliente"
        ),

        pk=pk,

        activo=True,

    )

    # ======================================================
    # HISTORIAL COMPLETO
    # ======================================================

    ordenes = preparar_ordenes_historial(

        expediente=expediente,

    )

    return render(

        request,

        "historial/detalle_expediente.html",

        {

            "expediente":
                expediente,

            "ordenes":
                ordenes,

            "total_ordenes":
                len(ordenes),

        },

    )


# ==========================================================
# HISTORIAL DENTRO DE UNA ORDEN DE TRABAJO
# ==========================================================


@login_required
def historial_modal_orden(
    request,
    pk,
):
    """
    Devuelve únicamente el HTML que será cargado dentro del
    modal de historial de detalle_orden.

    Importante:

    - No muestra nuevamente la OT actual.
    - Solo muestra visitas anteriores.
    - Mantiene repuestos.
    - Mantiene MOI.
    - Mantiene MOE.
    - Mantiene procedimientos.
    - Mantiene técnicos.
    - Mantiene históricos migrados.
    """

    # ======================================================
    # OT ACTUAL
    # ======================================================

    orden_actual = get_object_or_404(

        OrdenTrabajo.objects
        .select_related(
            "expediente"
        ),

        pk=pk,

    )

    # ======================================================
    # EXPEDIENTE
    # ======================================================

    expediente = (
        orden_actual.expediente
    )

    # ======================================================
    # OT SIN EXPEDIENTE
    # ======================================================

    if expediente is None:

        return render(

            request,

            (
                "includes/"
                "detalle_orden/"
                "historial_modal_contenido.html"
            ),

            {

                "orden_actual":
                    orden_actual,

                "expediente":
                    None,

                "ordenes":
                    [],

                "total_ordenes":
                    0,

            },

        )

    # ======================================================
    # VISITAS ANTERIORES
    # ======================================================

    ordenes = preparar_ordenes_historial(

        expediente=expediente,

        excluir_orden_id=(
            orden_actual.pk
        ),

        solo_anteriores_a=(
            orden_actual
        ),

    )

    # ======================================================
    # RENDER PARCIAL PARA EL MODAL
    # ======================================================

    return render(

        request,

        (
            "includes/"
            "detalle_orden/"
            "historial_modal_contenido.html"
        ),

        {

            "orden_actual":
                orden_actual,

            "expediente":
                expediente,

            "ordenes":
                ordenes,

            "total_ordenes":
                len(ordenes),

        },

    )