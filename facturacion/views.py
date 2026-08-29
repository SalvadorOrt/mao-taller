from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.views.decorators.http import require_POST

from ordenes_de_trabajo.models import OrdenTrabajo

from facturacion.models import (
    EntidadFinanciera,
    FacturaVenta,
    PagoFacturaVenta,
)

from facturacion.services.factura_desde_orden import (
    crear_factura_desde_orden,
)

from facturacion.services.emision_factura import (
    procesar_factura_completa,
)


# =========================================================
# UTILIDADES
# =========================================================

def _decimal(valor, default="0.00"):
    """
    Convierte un valor a Decimal de forma segura.
    """

    if valor in (
        None,
        "",
    ):
        return Decimal(default)

    try:
        return Decimal(str(valor))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return Decimal(default)


def _subtotal_bruto(detalles):
    """
    Calcula subtotal antes de descuento para una colección
    de DetalleFacturaVenta.
    """

    return sum(
        (
            _decimal(detalle.cantidad)
            * _decimal(detalle.precio_unitario)
            for detalle in detalles
        ),
        Decimal("0.00"),
    )


def _factura_editable(factura):
    """
    Solo una factura BORRADOR puede cambiar comprador
    o forma de pago.
    """

    return factura.estado == "BORRADOR"


def _entidades_financieras_activas():
    """
    Devuelve el catálogo activo de entidades financieras
    para los formularios de pago.
    """

    return (
        EntidadFinanciera.objects
        .filter(activo=True)
        .order_by("orden", "tipo", "nombre")
    )


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard_facturacion(request):
    """
    Dashboard principal de facturación.

    Muestra FACTURAS existentes, no órdenes de trabajo.

    Permite buscar por:
    - número de factura
    - número de OT de origen
    - placa
    - vehículo
    - nombre / razón social
    - cédula / RUC / identificación

    Las órdenes pendientes se buscan únicamente desde
    el modal "+ Nueva factura".
    """

    q = (
        request.GET.get("q", "")
        .strip()
    )

    facturas = (
        FacturaVenta.objects
        .select_related(
            "orden",
            "empresa",
            "sucursal",
        )
        .order_by(
            "-created_at",
            "-pk",
        )
    )

    if q:
        facturas = facturas.filter(
            Q(numero_factura__icontains=q)
            | Q(numero_orden_origen__icontains=q)
            | Q(placa_snapshot__icontains=q)
            | Q(vehiculo_snapshot__icontains=q)
            | Q(razon_social_comprador__icontains=q)
            | Q(identificacion_comprador__icontains=q)
        )

    total_facturas = facturas.count()

    total_borradores = (
        FacturaVenta.objects
        .filter(estado="BORRADOR")
        .count()
    )

    total_autorizadas = (
        FacturaVenta.objects
        .filter(estado="AUTORIZADO")
        .count()
    )

    total_rechazadas = (
        FacturaVenta.objects
        .filter(estado="RECHAZADO")
        .count()
    )

    context = {
        "facturas":
            facturas[:150],

        "q":
            q,

        "total_facturas":
            total_facturas,

        "total_borradores":
            total_borradores,

        "total_autorizadas":
            total_autorizadas,

        "total_rechazadas":
            total_rechazadas,
    }

    return render(
        request,
        "facturacion/dashboard.html",
        context,
    )


# =========================================================
# BUSCAR OT PARA NUEVA FACTURA
# =========================================================

@login_required
def buscar_ordenes_facturacion(request):
    """
    Endpoint JSON para el modal "+ Nueva factura".

    Solo devuelve órdenes:
    - CERRADAS
    - no migradas
    - sin factura asociada

    Busca por OT, placa, identificación, cliente o vehículo.
    """

    q = (
        request.GET.get("q", "")
        .strip()
    )

    if len(q) < 2:
        return JsonResponse(
            {
                "ok": True,
                "resultados": [],
                "mensaje": "Escribe al menos 2 caracteres para buscar.",
            }
        )

    ordenes = (
        OrdenTrabajo.objects
        .filter(
            estado="CERRADA",
            es_migrada=False,
            factura_electronica__isnull=True,
        )
        .select_related(
            "cliente",
            "sucursal",
        )
        .filter(
            Q(numero_orden__icontains=q)
            | Q(placa__icontains=q)
            | Q(cliente__identificacion__icontains=q)
            | Q(cliente__nombre_completo__icontains=q)
            | Q(vehiculo__icontains=q)
        )
        .order_by(
            "-fecha_ingreso",
            "-pk",
        )[:20]
    )

    resultados = []

    for orden in ordenes:
        cliente = getattr(
            orden,
            "cliente",
            None,
        )

        resultados.append(
            {
                "id": orden.pk,
                "numero_orden": str(
                    getattr(
                        orden,
                        "numero_orden",
                        "",
                    )
                    or ""
                ),
                "fecha": (
                    orden.fecha_ingreso.strftime("%d/%m/%Y")
                    if getattr(orden, "fecha_ingreso", None)
                    else ""
                ),
                "placa": str(
                    getattr(
                        orden,
                        "placa",
                        "",
                    )
                    or ""
                ),
                "cliente": str(
                    getattr(
                        orden,
                        "nombre_cliente_final",
                        "",
                    )
                    or getattr(
                        cliente,
                        "nombre_completo",
                        "",
                    )
                    or "-"
                ),
                "identificacion": str(
                    getattr(
                        cliente,
                        "identificacion",
                        "",
                    )
                    or ""
                ),
                "vehiculo": str(
                    getattr(
                        orden,
                        "vehiculo",
                        "",
                    )
                    or "-"
                ),
                "sucursal": str(
                    getattr(
                        getattr(
                            orden,
                            "sucursal",
                            None,
                        ),
                        "nombre",
                        "",
                    )
                    or "-"
                ),
                "total": format(
                    _decimal(
                        getattr(
                            orden,
                            "total_final",
                            0,
                        )
                    ),
                    ".2f",
                ),
                "url": (
                    f"/facturacion/orden/{orden.pk}/"
                ),
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "resultados": resultados,
            "total": len(resultados),
        }
    )


# =========================================================
# CREAR FACTURA DESDE OT
# =========================================================

@login_required
@require_POST
def crear_factura_desde_ot(
    request,
    orden_id,
):

    orden = get_object_or_404(
        OrdenTrabajo,
        pk=orden_id,
    )

    try:

        factura = (
            crear_factura_desde_orden(
                orden=orden,
            )
        )

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:dashboard"
        )

    except Exception as exc:

        messages.error(
            request,
            (
                "No se pudo crear la factura. "
                f"Detalle: {exc}"
            ),
        )

        return redirect(
            "facturacion:dashboard"
        )

    messages.success(
        request,
        (
            f"Factura "
            f"{factura.numero_factura} "
            "creada correctamente en borrador."
        ),
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# DETALLE DE FACTURA
# =========================================================

@login_required
def detalle_factura(
    request,
    factura_id,
):

    factura = get_object_or_404(
        FacturaVenta.objects
        .select_related(
            "orden",
            "empresa",
            "sucursal",
            "firma_electronica",
        )
        .prefetch_related(
            "detalles__procedimientos",
            "pagos",
        ),
        pk=factura_id,
    )

    # =====================================================
    # SEPARAR SNAPSHOT POR ORIGEN
    # =====================================================

    detalles = list(
        factura.detalles.all()
    )

    repuestos = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "REP"
    ]

    mano_obra_interna = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "MOI"
    ]

    mano_obra_externa = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "MOE"
    ]

    otros_detalles = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "OTRO"
    ]

    # =====================================================
    # SUBTOTALES VISUALES
    # =====================================================

    subtotal_repuestos = (
        _subtotal_bruto(
            repuestos
        )
    )

    subtotal_moi = (
        _subtotal_bruto(
            mano_obra_interna
        )
    )

    subtotal_moe = (
        _subtotal_bruto(
            mano_obra_externa
        )
    )

    subtotal_otros = (
        _subtotal_bruto(
            otros_detalles
        )
    )

    subtotal_bruto = (
        subtotal_repuestos
        + subtotal_moi
        + subtotal_moe
        + subtotal_otros
    )

    # =====================================================
    # PAGOS
    # =====================================================

    pagos = list(
        factura.pagos.all()
    )

    total_pagado = (
        factura.total_pagado()
    )

    saldo_pendiente = (
        factura.saldo_pendiente()
    )

    # =====================================================
    # ESTADO
    # =====================================================

    puede_editar = (
        _factura_editable(
            factura
        )
    )

    puede_emitir = (
        factura.estado
        in {
            "BORRADOR",
            "GENERADO",
            "FIRMADO",
            "RECIBIDO",
        }
    )

    context = {
        "factura":
            factura,

        # -----------------------------------------
        # EDICIÓN
        # -----------------------------------------

        "puede_editar":
            puede_editar,

        "puede_emitir":
            puede_emitir,

        # -----------------------------------------
        # DETALLES
        # -----------------------------------------

        "repuestos":
            repuestos,

        "mano_obra_interna":
            mano_obra_interna,

        "mano_obra_externa":
            mano_obra_externa,

        "otros_detalles":
            otros_detalles,

        # -----------------------------------------
        # SUBTOTALES
        # -----------------------------------------

        "subtotal_repuestos":
            subtotal_repuestos,

        "subtotal_moi":
            subtotal_moi,

        "subtotal_moe":
            subtotal_moe,

        "subtotal_otros":
            subtotal_otros,

        "subtotal_bruto":
            subtotal_bruto,

        # -----------------------------------------
        # PAGOS
        # -----------------------------------------

        "pagos":
            pagos,

        "total_pagado":
            total_pagado,

        "saldo_pendiente":
            saldo_pendiente,

        # -----------------------------------------
        # CHOICES
        # -----------------------------------------

        "tipos_identificacion":
            FacturaVenta.TIPOS_IDENTIFICACION,

        "formas_pago":
            FacturaVenta.FORMAS_PAGO,

        "entidades_financieras":
            _entidades_financieras_activas(),
    }

    return render(
        request,
        "facturacion/detalle_factura.html",
        context,
    )


# =========================================================
# ACTUALIZAR COMPRADOR
# =========================================================

@login_required
@require_POST
@transaction.atomic
def actualizar_comprador(
    request,
    factura_id,
):

    factura = get_object_or_404(
        FacturaVenta.objects
        .select_for_update(),
        pk=factura_id,
    )

    if not _factura_editable(
        factura
    ):

        messages.error(
            request,
            (
                "El comprador solo puede "
                "modificarse mientras la factura "
                "está en BORRADOR."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # CONSUMIDOR FINAL
    # =====================================================

    consumidor_final = (
        request.POST.get(
            "consumidor_final"
        )
        == "1"
    )

    if consumidor_final:

        factura.tipo_identificacion_comprador = (
            "07"
        )

        factura.razon_social_comprador = (
            "CONSUMIDOR FINAL"
        )

        factura.identificacion_comprador = (
            "9999999999999"
        )

        factura.direccion_comprador = ""
        factura.telefono_comprador = ""
        factura.correo_comprador = ""

    else:

        tipo_identificacion = (
            request.POST.get(
                "tipo_identificacion_comprador",
                "",
            )
            .strip()
        )

        razon_social = (
            request.POST.get(
                "razon_social_comprador",
                "",
            )
            .strip()
        )

        identificacion = (
            request.POST.get(
                "identificacion_comprador",
                "",
            )
            .strip()
        )

        direccion = (
            request.POST.get(
                "direccion_comprador",
                "",
            )
            .strip()
        )

        telefono = (
            request.POST.get(
                "telefono_comprador",
                "",
            )
            .strip()
        )

        correo = (
            request.POST.get(
                "correo_comprador",
                "",
            )
            .strip()
            .lower()
        )

        if tipo_identificacion not in {
            "04",
            "05",
            "06",
        }:

            messages.error(
                request,
                (
                    "Selecciona un tipo de "
                    "identificación válido."
                ),
            )

            return redirect(
                "facturacion:detalle_factura",
                factura_id=factura.pk,
            )

        if not razon_social:

            messages.error(
                request,
                (
                    "El nombre o razón social "
                    "del comprador es obligatorio."
                ),
            )

            return redirect(
                "facturacion:detalle_factura",
                factura_id=factura.pk,
            )

        if not identificacion:

            messages.error(
                request,
                (
                    "La identificación del "
                    "comprador es obligatoria."
                ),
            )

            return redirect(
                "facturacion:detalle_factura",
                factura_id=factura.pk,
            )

        factura.tipo_identificacion_comprador = (
            tipo_identificacion
        )

        factura.razon_social_comprador = (
            razon_social
        )

        factura.identificacion_comprador = (
            identificacion
        )

        factura.direccion_comprador = (
            direccion
        )

        factura.telefono_comprador = (
            telefono
        )

        factura.correo_comprador = (
            correo
        )

    try:

        factura.save(
            update_fields=[
                "tipo_identificacion_comprador",
                "razon_social_comprador",
                "identificacion_comprador",
                "direccion_comprador",
                "telefono_comprador",
                "correo_comprador",
                "updated_at",
            ]
        )

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    messages.success(
        request,
        "Comprador actualizado correctamente.",
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# GUARDAR FORMA DE PAGO
# =========================================================

@login_required
@require_POST
@transaction.atomic
def guardar_forma_pago(
    request,
    factura_id,
):

    factura = get_object_or_404(
        FacturaVenta.objects
        .select_for_update(),
        pk=factura_id,
    )

    if not _factura_editable(factura):

        messages.error(
            request,
            (
                "La forma de pago solo puede "
                "modificarse mientras la factura "
                "está en BORRADOR."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # FORMA DE PAGO
    # =====================================================

    forma_pago = (
        request.POST.get("forma_pago", "")
        or request.POST.get("codigo_sri_pago", "")
    ).strip()

    formas_validas = {
        codigo
        for codigo, _nombre
        in FacturaVenta.FORMAS_PAGO
    }

    if forma_pago not in formas_validas:

        messages.error(
            request,
            "Selecciona una forma de pago válida.",
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # PLAZO
    # =====================================================

    try:
        plazo = int(
            request.POST.get("plazo", "0")
            or 0
        )
    except (TypeError, ValueError):
        plazo = 0

    if plazo < 0:
        plazo = 0

    unidad_tiempo = (
        request.POST.get(
            "unidad_tiempo",
            "Días",
        ).strip()
        or "Días"
    )

    # =====================================================
    # ENTIDAD FINANCIERA
    # =====================================================

    entidad_financiera = None

    entidad_financiera_id = (
        request.POST.get(
            "entidad_financiera_id",
            "",
        ).strip()
    )

    entidad_financiera_nombre = (
        request.POST.get(
            "entidad_financiera_nombre",
            "",
        ).strip()
    )

    referencia = (
        request.POST.get("referencia_pago", "")
        or request.POST.get("referencia", "")
    ).strip()

    observacion = (
        request.POST.get("observacion_pago", "")
        or request.POST.get("observacion", "")
    ).strip()

    if entidad_financiera_id:

        try:
            entidad_financiera = (
                EntidadFinanciera.objects
                .get(
                    pk=entidad_financiera_id,
                    activo=True,
                )
            )

        except (
            EntidadFinanciera.DoesNotExist,
            ValueError,
        ):

            messages.error(
                request,
                (
                    "La entidad financiera seleccionada "
                    "no existe o está inactiva."
                ),
            )

            return redirect(
                "facturacion:detalle_factura",
                factura_id=factura.pk,
            )

    # Si la forma de pago no usa sistema financiero,
    # eliminamos cualquier dato residual del formulario.
    if forma_pago not in PagoFacturaVenta.FORMAS_PAGO_CON_ENTIDAD:
        entidad_financiera = None
        entidad_financiera_nombre = ""
        referencia = ""

    # =====================================================
    # UNA SOLA FORMA DE PAGO POR EL TOTAL
    # =====================================================

    factura.pagos.all().delete()

    try:

        PagoFacturaVenta.objects.create(
            factura=factura,
            forma_pago=forma_pago,
            total=factura.importe_total,
            entidad_financiera=entidad_financiera,
            entidad_financiera_nombre=entidad_financiera_nombre,
            referencia=referencia,
            observacion=observacion,
            plazo=plazo,
            unidad_tiempo=unidad_tiempo,
        )

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    messages.success(
        request,
        "Forma de pago guardada correctamente.",
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# EMITIR FACTURA
# =========================================================

@login_required
@require_POST
def emitir_factura(
    request,
    factura_id,
):

    factura = get_object_or_404(
        FacturaVenta.objects
        .select_related(
            "empresa",
            "sucursal",
            "firma_electronica",
        )
        .prefetch_related(
            "detalles",
            "pagos",
        ),
        pk=factura_id,
    )

    # =====================================================
    # YA AUTORIZADA
    # =====================================================

    if factura.estado == "AUTORIZADO":

        messages.info(
            request,
            (
                "La factura ya se encuentra "
                "AUTORIZADA por el SRI."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # RECHAZADA
    # =====================================================

    if factura.estado == "RECHAZADO":

        messages.error(
            request,
            (
                "La factura está RECHAZADA. "
                "No se reenviará automáticamente. "
                "Primero revisa el mensaje del SRI."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # VALIDAR PAGO
    # =====================================================

    if not factura.tiene_pagos_completos():

        messages.error(
            request,
            (
                "Antes de emitir debes registrar "
                "la forma de pago por el total "
                "de la factura."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # PROCESAR
    # =====================================================

    try:

        procesar_factura_completa(
            factura
        )

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    except Exception as exc:

        messages.error(
            request,
            (
                "Ocurrió un error durante "
                "la emisión electrónica. "
                f"Detalle: {exc}"
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    # =====================================================
    # LEER ESTADO FINAL REAL
    # =====================================================

    factura.refresh_from_db()

    if factura.estado == "AUTORIZADO":

        messages.success(
            request,
            (
                "Factura autorizada correctamente "
                "por el SRI."
            ),
        )

    elif factura.estado == "RECIBIDO":

        messages.info(
            request,
            (
                "El SRI recibió la factura. "
                "La autorización todavía está "
                "en procesamiento."
            ),
        )

    elif factura.estado == "FIRMADO":

        messages.info(
            request,
            (
                "El XML quedó firmado. "
                "Todavía no ha sido recibido "
                "por el SRI."
            ),
        )

    elif factura.estado == "GENERADO":

        messages.info(
            request,
            (
                "El XML fue generado, pero "
                "el proceso de emisión aún "
                "no ha terminado."
            ),
        )

    elif factura.estado == "RECHAZADO":

        messages.error(
            request,
            (
                "El SRI rechazó el comprobante. "
                "Revisa el mensaje mostrado "
                "en la sección Estado SRI."
            ),
        )

    else:

        messages.info(
            request,
            (
                "Proceso ejecutado. "
                f"Estado actual: {factura.estado}."
            ),
        )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )
# =========================================================
# DETALLE DE OT PARA FACTURACIÓN
# =========================================================

@login_required
def detalle_orden_facturacion(
    request,
    orden_id,
):
    """
    Pantalla de consulta de una OT cerrada antes de emitir.

    IMPORTANTE:
    - NO crea FacturaVenta.
    - NO consume secuencial.
    - NO genera XML.
    - NO envía nada al SRI.

    Solo muestra la OT con:
    - repuestos
    - mano de obra interna
    - mano de obra externa
    - procedimientos
    - resumen económico
    """

    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related(
            "cliente",
            "sucursal",
            "sucursal__empresa",
        )
        .prefetch_related(
            "servicios_detalles__procedimientos_detalle",
            "insumos_detalles",
        ),
        pk=orden_id,
        estado="CERRADA",
        es_migrada=False,
    )

    # =====================================================
    # SI YA EXISTE FACTURA
    # =====================================================

    factura_existente = (
        FacturaVenta.objects
        .filter(
            orden=orden,
        )
        .first()
    )

    if factura_existente:
        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura_existente.pk,
        )

    # =====================================================
    # REPUESTOS
    # =====================================================

    repuestos = list(
        orden.insumos_detalles.all()
    )

    # =====================================================
    # SERVICIOS
    # =====================================================

    servicios = list(
        orden.servicios_detalles.all()
    )

    mano_obra_interna = [
        item
        for item in servicios
        if item.tipo_servicio == "MEC"
    ]

    mano_obra_externa = [
        item
        for item in servicios
        if item.tipo_servicio == "EXT"
    ]

    # =====================================================
    # SUBTOTALES
    # =====================================================

    subtotal_repuestos = sum(
        (
            _decimal(item.subtotal)
            for item in repuestos
        ),
        Decimal("0.00"),
    )

    subtotal_moi = sum(
        (
            _decimal(item.subtotal)
            for item in mano_obra_interna
        ),
        Decimal("0.00"),
    )

    subtotal_moe = sum(
        (
            _decimal(item.subtotal)
            for item in mano_obra_externa
        ),
        Decimal("0.00"),
    )

    subtotal_bruto = (
        subtotal_repuestos
        + subtotal_moi
        + subtotal_moe
    )

    # =====================================================
    # TOTALES DE LA OT
    # =====================================================

    descuento = _decimal(
        getattr(
            orden,
            "valor_descuento",
            0,
        )
    )

    subtotal_sin_iva = (
        subtotal_bruto
        - descuento
    )

    if subtotal_sin_iva < Decimal("0.00"):
        subtotal_sin_iva = Decimal("0.00")

    porcentaje_iva = _decimal(
        getattr(
            orden,
            "porcentaje_iva",
            15,
        )
    )

    valor_iva = (
        subtotal_sin_iva
        * porcentaje_iva
        / Decimal("100")
    ).quantize(
        Decimal("0.01")
    )

    total_calculado = (
        subtotal_sin_iva
        + valor_iva
    ).quantize(
        Decimal("0.01")
    )

    # Si la OT ya tiene total_final, usamos el valor oficial.
    total_final = _decimal(
        getattr(
            orden,
            "total_final",
            total_calculado,
        )
    )

    # =====================================================
    # CONTEXTO
    # =====================================================

    context = {
        "orden":
            orden,

        # -----------------------------------------
        # DETALLES
        # -----------------------------------------

        "repuestos":
            repuestos,

        "mano_obra_interna":
            mano_obra_interna,

        "mano_obra_externa":
            mano_obra_externa,

        # -----------------------------------------
        # SUBTOTALES
        # -----------------------------------------

        "subtotal_repuestos":
            subtotal_repuestos,

        "subtotal_moi":
            subtotal_moi,

        "subtotal_moe":
            subtotal_moe,

        "subtotal_bruto":
            subtotal_bruto,

        # -----------------------------------------
        # TOTALES
        # -----------------------------------------

        "subtotal_sin_iva":
            subtotal_sin_iva,

        "descuento":
            descuento,

        "porcentaje_iva":
            porcentaje_iva,

        "valor_iva":
            valor_iva,

        "total_final":
            total_final,

        # -----------------------------------------
        # FACTURACIÓN
        # -----------------------------------------

        "tipos_identificacion":
            FacturaVenta.TIPOS_IDENTIFICACION,

        "formas_pago":
            FacturaVenta.FORMAS_PAGO,

        "entidades_financieras":
            _entidades_financieras_activas(),
    }

    return render(
        request,
        "facturacion/detalle_orden_facturacion.html",
        context,
    )