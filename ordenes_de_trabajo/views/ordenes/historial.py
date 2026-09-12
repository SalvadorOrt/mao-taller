from decimal import Decimal

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from ...models import ExpedienteVehiculo


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
            texto = str(procedimiento).strip()

        if texto:
            resultado.append(texto)

    return resultado


@login_required
def historial_vehiculos(request):
    q = request.GET.get("q", "").strip().upper()

    expedientes = ExpedienteVehiculo.objects.none()

    if q:
        expedientes = (
            ExpedienteVehiculo.objects
            .select_related("cliente")
            .filter(
                Q(placa__icontains=q)
                | Q(vehiculo__icontains=q)
                | Q(cliente__nombre_completo__icontains=q)
                | Q(cliente_respaldo__icontains=q),
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
            "q": q,
            "expedientes": expedientes,
        },
    )


@login_required
def detalle_expediente(request, pk):
    expediente = get_object_or_404(
        ExpedienteVehiculo.objects.select_related(
            "cliente"
        ),
        pk=pk,
        activo=True,
    )

    ordenes = list(
        expediente.ordenes
        .select_related(
            "sucursal",
            "cliente",
            "usuario_receptor",
        )
        .prefetch_related(
            "tecnicos",
            "servicios_detalles__tecnico_responsable",
            "servicios_detalles__procedimientos_detalle",
            "servicios_historicos",
            "insumos_detalles",
            "insumos_historicos",
            "sintomas_items",
            "trabajos_solicitados_items",
            "recomendaciones_items",
            "abonos",
        )
        .order_by(
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
        orden.posicion_historial = posicion
        orden.diferencia_km = None
        orden.kilometraje_inconsistente = False

        if orden.kilometraje is None:
            continue

        if kilometraje_anterior is not None:
            diferencia = (
                orden.kilometraje
                - kilometraje_anterior
            )

            if diferencia >= 0:
                orden.diferencia_km = diferencia
            else:
                orden.kilometraje_inconsistente = True

        kilometraje_anterior = orden.kilometraje

    # ==========================================================
    # DATOS DE CONSULTA PARA CADA OT
    # Unifica órdenes actuales e históricas/migradas.
    # ==========================================================

    for orden in ordenes:
        repuestos = []
        moi = []
        moe = []

        # ------------------------------------------------------
        # REPUESTOS ACTUALES
        # ------------------------------------------------------

        for item in orden.insumos_detalles.all():
            referencia = (
                item.codigo_empaque_referencia
                or item.codigo_barras_referencia
                or "[ TEXTO LIBRE / MANUAL ]"
            )

            repuestos.append({
                "referencia": referencia,
                "descripcion": (
                    item.descripcion_factura
                    or "SIN DESCRIPCIÓN"
                ),
                "precio_unitario": item.precio_unitario,
                "cantidad": item.cantidad,
                "subtotal": item.subtotal,
                "es_historico": False,
            })

        # ------------------------------------------------------
        # REPUESTOS HISTÓRICOS / MIGRADOS
        # ------------------------------------------------------

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
                "precio_unitario": item.precio_unitario,
                "cantidad": item.cantidad,
                "subtotal": item.subtotal,
                "es_historico": True,
            })

        # ------------------------------------------------------
        # SERVICIOS ACTUALES
        # ------------------------------------------------------

        for item in orden.servicios_detalles.all():
            codigo_servicio = None

            if item.servicio:
                codigo_servicio = getattr(
                    item.servicio,
                    "codigo",
                    None,
                )

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
                "precio_unitario": item.precio_unitario,
                "cantidad": item.cantidad,
                "subtotal": item.subtotal,
                "procedimientos": procedimientos,
                "es_cortesia": False,
                "es_historico": False,
            }

            if item.tipo_servicio == "EXT":
                moe.append(fila)
            else:
                moi.append(fila)

        # ------------------------------------------------------
        # SERVICIOS HISTÓRICOS / MIGRADOS
        # ------------------------------------------------------

        for item in orden.servicios_historicos.all():
            fila = {
                "referencia": "[ HISTÓRICO ]",
                "descripcion": (
                    item.descripcion_original
                    or "SIN DESCRIPCIÓN"
                ),
                "precio_unitario": item.precio_unitario,
                "cantidad": item.cantidad,
                "subtotal": item.subtotal,
                "procedimientos": _normalizar_procedimientos(
                    item.procedimientos
                ),
                "es_cortesia": item.es_cortesia,
                "es_historico": True,
            }

            if item.tipo == "MOE":
                moe.append(fila)
            else:
                moi.append(fila)

        # ------------------------------------------------------
        # SUBTOTALES DEL FORMATO DE CONSULTA
        # ------------------------------------------------------

        orden.repuestos_consulta = repuestos
        orden.moi_consulta = moi
        orden.moe_consulta = moe

        orden.subtotal_repuestos_consulta = sum(
            (
                _decimal(item["subtotal"])
                for item in repuestos
            ),
            Decimal("0.00"),
        )

        orden.subtotal_moi_consulta = sum(
            (
                _decimal(item["subtotal"])
                for item in moi
            ),
            Decimal("0.00"),
        )

        orden.subtotal_moe_consulta = sum(
            (
                _decimal(item["subtotal"])
                for item in moe
            ),
            Decimal("0.00"),
        )

        # ------------------------------------------------------
        # ABONOS - SOLO CONSULTA
        # ------------------------------------------------------

        orden.abonos_consulta = list(
            orden.abonos.all()
        )

        orden.total_abonado_consulta = sum(
            (
                _decimal(abono.monto)
                for abono in orden.abonos_consulta
                if abono.estado != "ANULADO"
            ),
            Decimal("0.00"),
        )

        orden.saldo_pendiente_consulta = max(
            _decimal(orden.total_final)
            - orden.total_abonado_consulta,
            Decimal("0.00"),
        )

    return render(
        request,
        "historial/detalle_expediente.html",
        {
            "expediente": expediente,
            "ordenes": ordenes,
            "total_ordenes": len(ordenes),
        },
    )
