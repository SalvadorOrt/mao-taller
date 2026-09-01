from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
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
    consultar_comprobante_sri,
    firmar_comprobante,
    generar_comprobante,
    procesar_factura_completa,
    reenviar_comprobante_rechazado,
    enviar_comprobante_sri,
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


def _datos_facturacion_desde_post(request):
    """
    Lee y valida los datos de facturación enviados desde la
    pantalla de preparación de la OT.

    Estos datos son un SNAPSHOT para FacturaVenta.
    Nunca modifican OrdenTrabajo.cliente.
    """

    tipo_identificacion = (
        request.POST.get(
            "tipo_identificacion_comprador",
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

    razon_social = (
        request.POST.get(
            "razon_social_comprador",
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

    # Consumidor final puede venir por el tipo 07 o por
    # un campo explícito desde otros formularios.
    consumidor_final = (
        tipo_identificacion == "07"
        or request.POST.get("consumidor_final") == "1"
    )

    if consumidor_final:
        return {
            "tipo_identificacion_comprador": "07",
            "identificacion_comprador": "9999999999999",
            "razon_social_comprador": "CONSUMIDOR FINAL",
            "direccion_comprador": "",
            "telefono_comprador": "",
            "correo_comprador": "",
        }

    if tipo_identificacion not in {
        "04",
        "05",
        "06",
    }:
        raise ValidationError(
            "Selecciona un tipo de identificación válido "
            "para facturación."
        )

    if not identificacion:
        raise ValidationError(
            "La identificación para facturación es obligatoria."
        )

    if not razon_social:
        raise ValidationError(
            "El nombre o razón social para facturación es obligatorio."
        )

    if tipo_identificacion == "04":
        if not identificacion.isdigit() or len(identificacion) != 13:
            raise ValidationError(
                "El RUC debe contener exactamente 13 dígitos."
            )

    elif tipo_identificacion == "05":
        if not identificacion.isdigit() or len(identificacion) != 10:
            raise ValidationError(
                "La cédula debe contener exactamente 10 dígitos."
            )

    elif tipo_identificacion == "06":
        if len(identificacion) > 20:
            raise ValidationError(
                "El pasaporte no puede superar 20 caracteres."
            )

        identificacion = identificacion.upper()

    return {
        "tipo_identificacion_comprador":
            tipo_identificacion,

        "identificacion_comprador":
            identificacion,

        "razon_social_comprador":
            razon_social,

        "direccion_comprador":
            direccion,

        "telefono_comprador":
            telefono,

        "correo_comprador":
            correo,
    }


def _datos_pago_desde_post(request):
    """
    Lee los datos de forma de pago.

    Acepta los nombres actuales del formulario y algunos aliases
    anteriores para mantener compatibilidad durante la migración
    de la interfaz.
    """

    forma_pago = (
        request.POST.get("forma_pago", "")
        or request.POST.get("codigo_sri_pago", "")
        or request.POST.get("metodo_pago", "")
    ).strip()

    if not forma_pago:
        raise ValidationError(
            "Selecciona una forma de pago."
        )

    formas_validas = {
        codigo
        for codigo, _nombre
        in FacturaVenta.FORMAS_PAGO
    }

    if forma_pago not in formas_validas:
        raise ValidationError(
            "Selecciona una forma de pago válida."
        )

    try:
        plazo = int(
            request.POST.get("plazo", "0")
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        plazo = 0

    if plazo < 0:
        plazo = 0

    unidad_tiempo = (
        request.POST.get(
            "unidad_tiempo",
            "Días",
        )
        .strip()
        or "Días"
    )

    entidad_financiera = None

    entidad_financiera_id = (
        request.POST.get(
            "entidad_financiera_id",
            "",
        )
        .strip()
    )

    entidad_financiera_nombre = (
        request.POST.get(
            "entidad_financiera_nombre",
            "",
        )
        .strip()
    )

    # Compatibilidad con el nombre anterior del formulario.
    if not entidad_financiera_nombre:
        entidad_financiera_nombre = (
            request.POST.get(
                "banco_pago",
                "",
            )
            .strip()
        )

    referencia = (
        request.POST.get("referencia_pago", "")
        or request.POST.get("referencia", "")
    ).strip()

    observacion = (
        request.POST.get("observacion_pago", "")
        or request.POST.get("observacion", "")
    ).strip()

    # "OTRA" es una opción funcional del formulario, no un PK real.
    # En ese caso se guarda únicamente el nombre escrito manualmente.
    if entidad_financiera_id == "OTRA":
        entidad_financiera_id = ""

        if (
            forma_pago in PagoFacturaVenta.FORMAS_PAGO_CON_ENTIDAD
            and not entidad_financiera_nombre
        ):
            raise ValidationError(
                "Escribe el nombre de la entidad financiera."
            )

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
            ValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise ValidationError(
                "La entidad financiera seleccionada "
                "no existe o está inactiva."
            ) from exc

    if forma_pago not in PagoFacturaVenta.FORMAS_PAGO_CON_ENTIDAD:
        entidad_financiera = None
        entidad_financiera_nombre = ""
        referencia = ""

    return {
        "forma_pago":
            forma_pago,

        "entidad_financiera":
            entidad_financiera,

        "entidad_financiera_nombre":
            entidad_financiera_nombre,

        "referencia":
            referencia,

        "observacion":
            observacion,

        "plazo":
            plazo,

        "unidad_tiempo":
            unidad_tiempo,
    }


def _crear_pago_total(
    factura,
    datos_pago,
):
    """
    Registra una sola forma de pago por el total de la factura.
    """

    pago = PagoFacturaVenta(
        factura=factura,
        forma_pago=datos_pago["forma_pago"],
        total=factura.importe_total,
        entidad_financiera=(
            datos_pago["entidad_financiera"]
        ),
        entidad_financiera_nombre=(
            datos_pago["entidad_financiera_nombre"]
        ),
        referencia=datos_pago["referencia"],
        observacion=datos_pago["observacion"],
        plazo=datos_pago["plazo"],
        unidad_tiempo=datos_pago["unidad_tiempo"],
    )

    pago.full_clean()
    pago.save()

    return pago


def _mensaje_resultado_emision(
    request,
    factura,
):
    """
    Muestra un mensaje coherente con el estado persistido real.
    """
    factura.refresh_from_db()

    if factura.estado == "AUTORIZADO":
        messages.success(
            request,
            "Factura autorizada correctamente por el SRI.",
        )

    elif factura.estado == "RECIBIDO":
        messages.info(
            request,
            (
                "El SRI recibió la factura. "
                "La autorización todavía está en procesamiento."
            ),
        )

    elif factura.estado == "FIRMADO":
        messages.info(
            request,
            (
                "El XML está firmado. "
                "Todavía no ha sido recibido por el SRI."
            ),
        )

    elif factura.estado == "GENERADO":
        messages.info(
            request,
            (
                "El XML fue generado, pero el proceso de "
                "emisión todavía no ha terminado."
            ),
        )

    elif factura.estado == "RECHAZADO":
        messages.error(
            request,
            (
                "El SRI rechazó el comprobante. "
                "Revisa el mensaje de recepción/autorización."
            ),
        )

    else:
        messages.info(
            request,
            f"Estado actual de la factura: {factura.estado}.",
        )


def _archivo_xml_disponible(factura):
    """
    Devuelve el XML más avanzado disponible sin regenerar nada.

    Prioridad:
        AUTORIZADO > FIRMADO > GENERADO
    """
    if factura.xml_autorizado:
        return (
            factura.xml_autorizado,
            "AUTORIZADO",
        )

    if factura.xml_firmado:
        return (
            factura.xml_firmado,
            "FIRMADO",
        )

    if factura.xml_generado:
        return (
            factura.xml_generado,
            "GENERADO",
        )

    return (
        None,
        "",
    )


def _nombre_xml_factura(
    factura,
    etapa,
):
    """
    Nombre seguro para descargar el XML.
    """
    if factura.secuencial:
        numero = (
            f"{factura.establecimiento or '000'}-"
            f"{factura.punto_emision or '000'}-"
            f"{factura.secuencial}"
        )
    else:
        numero = f"BORRADOR-{factura.pk}"

    return (
        f"FACTURA_{numero}_{etapa}.xml"
        .replace(" ", "_")
    )


# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard_facturacion(request):
    """
    Dashboard principal de facturación.

    Muestra FACTURAS existentes, no órdenes de trabajo.

    Admite facturas provenientes de OT y facturas manuales sin OT.

    Permite buscar por:
    - número/secuencial de factura
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
        filtro = (
            Q(secuencial__icontains=q)
            | Q(establecimiento__icontains=q)
            | Q(punto_emision__icontains=q)
            | Q(numero_orden_origen__icontains=q)
            | Q(placa_snapshot__icontains=q)
            | Q(vehiculo_snapshot__icontains=q)
            | Q(razon_social_comprador__icontains=q)
            | Q(identificacion_comprador__icontains=q)
        )

        partes = [
            parte.strip()
            for parte in q.split("-")
            if parte.strip()
        ]

        if len(partes) == 3:
            filtro |= Q(
                establecimiento__iexact=partes[0],
                punto_emision__iexact=partes[1],
                secuencial__iexact=partes[2],
            )

        facturas = facturas.filter(filtro)

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
    """
    Guarda una FacturaVenta en estado BORRADOR a partir de una OT.

    Flujo:
    1. valida datos de facturación;
    2. valida forma de pago;
    3. crea el snapshot económico desde la OT;
    4. reemplaza el receptor por el snapshot seleccionado;
    5. registra una forma de pago por el total;
    6. NO genera XML;
    7. NO firma;
    8. NO envía nada al SRI.

    Si cualquier paso falla, toda la operación se revierte.
    """

    orden = get_object_or_404(
        OrdenTrabajo,
        pk=orden_id,
    )

    try:

        datos_facturacion = (
            _datos_facturacion_desde_post(
                request
            )
        )

        datos_pago = (
            _datos_pago_desde_post(
                request
            )
        )

        with transaction.atomic():

            # El servicio crea el snapshot económico y los detalles.
            # La factura nace obligatoriamente en BORRADOR.
            factura = (
                crear_factura_desde_orden(
                    orden=orden,
                )
            )

            # Reemplazamos únicamente el snapshot del receptor.
            # NO modificamos orden.cliente.
            for campo, valor in (
                datos_facturacion.items()
            ):
                setattr(
                    factura,
                    campo,
                    valor,
                )

            factura.full_clean()

            factura.save(
                update_fields=[
                    "tipo_identificacion_comprador",
                    "identificacion_comprador",
                    "razon_social_comprador",
                    "direccion_comprador",
                    "telefono_comprador",
                    "correo_comprador",
                    "updated_at",
                ]
            )

            _crear_pago_total(
                factura,
                datos_pago,
            )

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:detalle_orden_facturacion",
            orden_id=orden.pk,
        )

    except Exception as exc:

        messages.error(
            request,
            (
                "No se pudo guardar la factura. "
                f"Detalle: {exc}"
            ),
        )

        return redirect(
            "facturacion:detalle_orden_facturacion",
            orden_id=orden.pk,
        )

    messages.success(
        request,
        (
            f"Factura borrador #{factura.pk} "
            "guardada correctamente. "
            "Todavía no se ha reservado secuencial ni generado "
            "clave de acceso."
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

    manual_detalles = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "MANUAL"
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

    subtotal_manual = (
        _subtotal_bruto(
            manual_detalles
        )
    )

    subtotal_bruto = (
        subtotal_repuestos
        + subtotal_moi
        + subtotal_moe
        + subtotal_manual
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
        factura.estado == "BORRADOR"
    )

    puede_reintentar = (
        factura.estado
        in {
            "GENERADO",
            "FIRMADO",
            "RECIBIDO",
            "RECHAZADO",
        }
    )

    puede_consultar_sri = (
        factura.estado
        in {
            "RECIBIDO",
            "FIRMADO",
            "RECHAZADO",
        }
        and bool(factura.clave_acceso)
    )

    puede_descargar_xml = bool(
        factura.xml_autorizado
        or factura.xml_firmado
        or factura.xml_generado
    )

    puede_enviar_correo = (
        factura.estado == "AUTORIZADO"
        and bool(factura.xml_autorizado)
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

        "puede_reintentar":
            puede_reintentar,

        "puede_consultar_sri":
            puede_consultar_sri,

        "puede_descargar_xml":
            puede_descargar_xml,

        "puede_enviar_correo":
            puede_enviar_correo,

        # -----------------------------------------
        # DETALLES
        # -----------------------------------------

        "repuestos":
            repuestos,

        "mano_obra_interna":
            mano_obra_interna,

        "mano_obra_externa":
            mano_obra_externa,

        "manual_detalles":
            manual_detalles,

        # Compatibilidad temporal con templates antiguos.
        "otros_detalles":
            manual_detalles,

        # -----------------------------------------
        # SUBTOTALES
        # -----------------------------------------

        "subtotal_repuestos":
            subtotal_repuestos,

        "subtotal_moi":
            subtotal_moi,

        "subtotal_moe":
            subtotal_moe,

        "subtotal_manual":
            subtotal_manual,

        # Compatibilidad temporal con templates antiguos.
        "subtotal_otros":
            subtotal_manual,

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

        # Total oficial congelado de la factura.
        # Lo usa el modal de emisión.
        "total_final":
            factura.importe_total,

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
                "Los datos de facturación solo pueden "
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
                    "para facturación es obligatorio."
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
                    "La identificación para "
                    "facturación es obligatoria."
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
        "Datos de facturación actualizados correctamente.",
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
def guardar_forma_pago(
    request,
    factura_id,
):
    """
    Sustituye la forma de pago de una factura BORRADOR.

    La sustitución es atómica:
    si el nuevo pago no es válido, el pago anterior se conserva.
    """

    try:

        with transaction.atomic():

            factura = get_object_or_404(
                FacturaVenta.objects
                .select_for_update(),
                pk=factura_id,
            )

            if not _factura_editable(
                factura
            ):
                raise ValidationError(
                    "La forma de pago solo puede "
                    "modificarse mientras la factura "
                    "está en BORRADOR."
                )

            datos_pago = (
                _datos_pago_desde_post(
                    request
                )
            )

            # Primero construimos y validamos el pago nuevo.
            nuevo_pago = PagoFacturaVenta(
                factura=factura,
                forma_pago=(
                    datos_pago["forma_pago"]
                ),
                total=factura.importe_total,
                entidad_financiera=(
                    datos_pago[
                        "entidad_financiera"
                    ]
                ),
                entidad_financiera_nombre=(
                    datos_pago[
                        "entidad_financiera_nombre"
                    ]
                ),
                referencia=(
                    datos_pago["referencia"]
                ),
                observacion=(
                    datos_pago["observacion"]
                ),
                plazo=(
                    datos_pago["plazo"]
                ),
                unidad_tiempo=(
                    datos_pago["unidad_tiempo"]
                ),
            )

            nuevo_pago.full_clean()

            # Solo después de validar eliminamos el pago anterior.
            factura.pagos.all().delete()

            nuevo_pago.save()

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura_id,
        )

    except Exception as exc:

        messages.error(
            request,
            (
                "No se pudo guardar la forma de pago. "
                f"Detalle: {exc}"
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura_id,
        )

    messages.success(
        request,
        "Forma de pago guardada correctamente.",
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura_id,
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
    """
    Emite una factura BORRADOR usando en un solo POST los datos
    seleccionados en el modal de emisión.

    Nunca modifica OrdenTrabajo.cliente.
    """

    # =====================================================
    # GUARDAR SNAPSHOT + PAGO DEL MODAL
    # =====================================================

    try:
        with transaction.atomic():

            factura = get_object_or_404(
                FacturaVenta.objects
                .select_for_update(),
                pk=factura_id,
            )

            if factura.estado == "AUTORIZADO":
                raise ValidationError(
                    "La factura ya se encuentra AUTORIZADA por el SRI."
                )

            if factura.estado == "RECHAZADO":
                raise ValidationError(
                    "La factura está RECHAZADA. "
                    "No se reenviará automáticamente. "
                    "Primero revisa el mensaje del SRI y utiliza "
                    "la opción de reintento cuando corresponda."
                )

            if factura.estado != "BORRADOR":
                raise ValidationError(
                    "Esta factura ya inició su proceso de emisión. "
                    "Utiliza la opción Reintentar para continuar "
                    f"desde el estado {factura.estado}."
                )

            # ---------------------------------------------
            # 1. Datos de facturación
            # ---------------------------------------------

            datos_facturacion = (
                _datos_facturacion_desde_post(
                    request
                )
            )

            for campo, valor in (
                datos_facturacion.items()
            ):
                setattr(
                    factura,
                    campo,
                    valor,
                )

            factura.full_clean()

            factura.save(
                update_fields=[
                    "tipo_identificacion_comprador",
                    "identificacion_comprador",
                    "razon_social_comprador",
                    "direccion_comprador",
                    "telefono_comprador",
                    "correo_comprador",
                    "updated_at",
                ]
            )

            # ---------------------------------------------
            # 2. Forma de pago
            # ---------------------------------------------

            datos_pago = (
                _datos_pago_desde_post(
                    request
                )
            )

            nuevo_pago = PagoFacturaVenta(
                factura=factura,
                forma_pago=(
                    datos_pago["forma_pago"]
                ),
                total=factura.importe_total,
                entidad_financiera=(
                    datos_pago[
                        "entidad_financiera"
                    ]
                ),
                entidad_financiera_nombre=(
                    datos_pago[
                        "entidad_financiera_nombre"
                    ]
                ),
                referencia=(
                    datos_pago["referencia"]
                ),
                observacion=(
                    datos_pago["observacion"]
                ),
                plazo=(
                    datos_pago["plazo"]
                ),
                unidad_tiempo=(
                    datos_pago["unidad_tiempo"]
                ),
            )

            # Validamos el nuevo pago antes de tocar el anterior.
            nuevo_pago.full_clean()

            factura.pagos.all().delete()
            nuevo_pago.save()

            if not factura.tiene_pagos_completos():
                raise ValidationError(
                    "La forma de pago debe cubrir exactamente "
                    "el total de la factura antes de emitir."
                )

    except ValidationError as exc:

        messages.error(
            request,
            str(exc),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura_id,
        )

    except Exception as exc:

        messages.error(
            request,
            (
                "No se pudieron guardar los datos necesarios "
                "para emitir la factura. "
                f"Detalle: {exc}"
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura_id,
        )

    # =====================================================
    # RECARGAR DESPUÉS DEL COMMIT LOCAL
    # =====================================================

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
    # PREPARAR Y PROCESAR SRI
    # =====================================================

    try:
        # BORRADOR no consume secuencial ni clave.
        # Se reservan únicamente cuando el usuario confirma emitir.
        if not factura.tiene_datos_emision:
            factura.preparar_emision()

        factura.refresh_from_db()

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

    _mensaje_resultado_emision(
        request,
        factura,
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# REINTENTAR / CONTINUAR EMISIÓN
# =========================================================

@login_required
@require_POST
def reintentar_factura(
    request,
    factura_id,
):
    """
    Continúa únicamente desde la etapa persistida.

    GENERADO:
        firma -> recepción -> autorización

    FIRMADO:
        recepción -> autorización

    RECIBIDO:
        solo autorización

    RECHAZADO:
        reenvía exactamente el XML firmado existente mediante
        el flujo explícito del servicio. No genera otra clave,
        secuencial, XML ni firma.

    BORRADOR:
        debe utilizar el botón Emitir factura.
    """

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

    try:
        if factura.estado == "AUTORIZADO":
            messages.info(
                request,
                "La factura ya está AUTORIZADA por el SRI.",
            )

            return redirect(
                "facturacion:detalle_factura",
                factura_id=factura.pk,
            )

        if factura.estado == "BORRADOR":
            messages.info(
                request,
                (
                    "La factura continúa en BORRADOR. "
                    "Usa Emitir factura para iniciar la emisión."
                ),
            )

            return redirect(
                "facturacion:detalle_factura",
                factura_id=factura.pk,
            )

        if factura.estado == "GENERADO":
            firmar_comprobante(
                factura
            )
            factura.refresh_from_db()

            enviar_comprobante_sri(
                factura
            )
            factura.refresh_from_db()

            if factura.estado == "RECIBIDO":
                consultar_comprobante_sri(
                    factura
                )

        elif factura.estado == "FIRMADO":
            enviar_comprobante_sri(
                factura
            )
            factura.refresh_from_db()

            if factura.estado == "RECIBIDO":
                consultar_comprobante_sri(
                    factura
                )

        elif factura.estado == "RECIBIDO":
            consultar_comprobante_sri(
                factura
            )

        elif factura.estado == "RECHAZADO":
            reenviar_comprobante_rechazado(
                factura
            )
            factura.refresh_from_db()

            if factura.estado == "RECIBIDO":
                consultar_comprobante_sri(
                    factura
                )

        else:
            raise ValidationError(
                (
                    "No existe una operación de reintento "
                    f"para el estado {factura.estado}."
                )
            )

    except ValidationError as exc:
        messages.error(
            request,
            str(exc),
        )

    except Exception as exc:
        messages.error(
            request,
            (
                "No se pudo continuar la emisión. "
                f"Detalle: {exc}"
            ),
        )

    _mensaje_resultado_emision(
        request,
        factura,
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# CONSULTAR ESTADO EN SRI
# =========================================================

@login_required
@require_POST
def consultar_estado_sri(
    request,
    factura_id,
):
    """
    Consulta autorización sin reenviar ni regenerar el comprobante.
    """

    factura = get_object_or_404(
        FacturaVenta.objects
        .select_related(
            "empresa",
            "sucursal",
        ),
        pk=factura_id,
    )

    try:
        consultar_comprobante_sri(
            factura
        )

    except ValidationError as exc:
        messages.error(
            request,
            str(exc),
        )

    except Exception as exc:
        messages.error(
            request,
            (
                "No se pudo consultar el comprobante en el SRI. "
                f"Detalle: {exc}"
            ),
        )

    _mensaje_resultado_emision(
        request,
        factura,
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# DESCARGAR XML
# =========================================================

@login_required
def descargar_xml_factura(
    request,
    factura_id,
):
    """
    Descarga el XML más avanzado ya almacenado.

    No genera, firma ni envía nada.
    """

    factura = get_object_or_404(
        FacturaVenta,
        pk=factura_id,
    )

    archivo, etapa = (
        _archivo_xml_disponible(
            factura
        )
    )

    if not archivo:
        messages.error(
            request,
            (
                "La factura todavía no tiene un XML "
                "disponible para descargar."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    try:
        archivo.open("rb")
        contenido = archivo.read()
    finally:
        try:
            archivo.close()
        except Exception:
            pass

    response = HttpResponse(
        contenido,
        content_type="application/xml; charset=utf-8",
    )

    response["Content-Disposition"] = (
        'attachment; filename="'
        + _nombre_xml_factura(
            factura,
            etapa,
        )
        + '"'
    )

    return response


# =========================================================
# CORREO
# =========================================================

@login_required
@require_POST
def enviar_factura_correo(
    request,
    factura_id,
):
    """
    Punto de entrada reservado para el envío de RIDE + XML.

    No se simula un envío mientras el servicio de correo de
    facturación no esté implementado.
    """

    factura = get_object_or_404(
        FacturaVenta,
        pk=factura_id,
    )

    if factura.estado != "AUTORIZADO":
        messages.error(
            request,
            (
                "Solo una factura AUTORIZADA puede enviarse "
                "al cliente por correo."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    if not factura.correo_comprador:
        messages.error(
            request,
            (
                "La factura no tiene un correo del comprador "
                "registrado."
            ),
        )

        return redirect(
            "facturacion:detalle_factura",
            factura_id=factura.pk,
        )

    messages.info(
        request,
        (
            "El servicio de correo de facturación todavía "
            "no está implementado. No se envió ningún correo."
        ),
    )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# ANULACIÓN
# =========================================================

@login_required
@require_POST
def anular_factura(
    request,
    factura_id,
):
    """
    No altera localmente una factura electrónica autorizada.

    La anulación SRI requiere su flujo tributario específico;
    por seguridad este endpoint no cambia el estado por sí solo.
    """

    factura = get_object_or_404(
        FacturaVenta,
        pk=factura_id,
    )

    if factura.estado == "AUTORIZADO":
        messages.error(
            request,
            (
                "Una factura AUTORIZADA no puede anularse "
                "cambiando únicamente el estado local. "
                "Debe ejecutarse el procedimiento de anulación "
                "correspondiente ante el SRI."
            ),
        )
    else:
        messages.info(
            request,
            (
                "La anulación todavía no está habilitada para "
                "este flujo. No se modificó la factura."
            ),
        )

    return redirect(
        "facturacion:detalle_factura",
        factura_id=factura.pk,
    )


# =========================================================
# FACTURA MANUAL / VENTA DIRECTA
# =========================================================

@login_required
def nueva_factura_manual(
    request,
):
    """
    La infraestructura de FacturaVenta ya admite orden=None,
    pero la pantalla de captura de líneas manuales debe
    implementarse junto con su template/servicio.
    """

    messages.info(
        request,
        (
            "La pantalla de factura manual todavía está "
            "pendiente de implementar."
        ),
    )

    return redirect(
        "facturacion:dashboard",
    )


@login_required
@require_POST
def crear_factura_manual(
    request,
):
    """
    Endpoint reservado para la creación de venta directa.

    Se mantiene sin crear registros hasta implementar la captura
    y validación de DetalleFacturaVenta manual.
    """

    messages.error(
        request,
        (
            "La creación de factura manual todavía no está "
            "implementada. No se creó ninguna factura."
        ),
    )

    return redirect(
        "facturacion:dashboard",
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
    Pantalla de preparación de una OT cerrada antes de guardar la factura.

    IMPORTANTE:
    - NO crea FacturaVenta hasta presionar Guardar factura.
    - NO consume secuencial mientras solo se visualiza.
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