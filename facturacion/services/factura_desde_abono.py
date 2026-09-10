from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from facturacion.models import (
    DetalleFacturaVenta,
    FacturaVenta,
)

from ordenes_de_trabajo.models import (
    AbonoOrdenTrabajo,
)


CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")
UNO = Decimal("1.00")


# =========================================================
# DECIMALES
# =========================================================

def _d(valor, default="0.00"):
    if valor is None:
        return Decimal(default)

    return Decimal(str(valor))


def _q2(valor):
    return _d(valor).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )


# =========================================================
# DESCOMPONER MONTO DEL ABONO
# =========================================================

def _descomponer_monto_abono(
    monto,
    porcentaje_iva,
):
    """
    El monto registrado en la OT representa dinero realmente recibido.

    Por tanto, al facturar el abono:

        BASE + IVA = MONTO DEL ABONO

    El servicio NO aumenta el valor recibido para "sumarle IVA".

    Solo se soportan las tarifas que actualmente admite el modelo:
    - 0%
    - 15%

    Si con la precisión actual de centavos no es posible representar
    exactamente el monto recibido con IVA 15%, se bloquea la creación
    de la factura en lugar de generar una diferencia de centavos.
    """

    monto = _q2(monto)
    porcentaje_iva = _q2(porcentaje_iva)

    if monto <= CERO:
        raise ValidationError(
            "El monto del abono debe ser mayor a $0.00."
        )

    # -----------------------------------------------------
    # IVA 0%
    # -----------------------------------------------------

    if porcentaje_iva == CERO:
        return {
            "base":
                monto,

            "iva":
                CERO,

            "codigo_porcentaje_iva":
                "0",

            "subtotal_gravado":
                CERO,

            "subtotal_iva_0":
                monto,
        }

    # -----------------------------------------------------
    # IVA 15%
    # -----------------------------------------------------

    if porcentaje_iva == Decimal("15.00"):

        factor = (
            UNO
            + (
                porcentaje_iva
                / Decimal("100")
            )
        )

        base = _q2(
            monto / factor
        )

        iva = _q2(
            base
            * porcentaje_iva
            / Decimal("100")
        )

        total_reconstruido = _q2(
            base + iva
        )

        if total_reconstruido != monto:
            raise ValidationError(
                (
                    "El monto del abono no puede representarse "
                    "exactamente con IVA 15% usando la precisión "
                    "actual de centavos. "
                    f"Abono: ${monto:.2f} | "
                    f"Base calculada: ${base:.2f} | "
                    f"IVA calculado: ${iva:.2f} | "
                    f"Total resultante: ${total_reconstruido:.2f}. "
                    "La factura NO fue creada."
                )
            )

        return {
            "base":
                base,

            "iva":
                iva,

            "codigo_porcentaje_iva":
                "4",

            "subtotal_gravado":
                base,

            "subtotal_iva_0":
                CERO,
        }

    # -----------------------------------------------------
    # TARIFA NO SOPORTADA
    # -----------------------------------------------------

    raise ValidationError(
        (
            "La tarifa de IVA de la OT no está soportada "
            "por el flujo actual de facturación de abonos. "
            f"IVA encontrado: {porcentaje_iva}%."
        )
    )


# =========================================================
# CREAR FACTURA DESDE ABONO
# =========================================================

@transaction.atomic
def crear_factura_desde_abono(
    abono,
    datos_comprador,
):
    """
    Crea una FacturaVenta BORRADOR a partir de un abono de una OT.

    IMPORTANTE:

    - NO modifica el total de la Orden de Trabajo.
    - NO modifica descuento ni IVA de la Orden de Trabajo.
    - NO cambia el estado del abono a FACTURADO.
    - NO genera XML.
    - NO firma XML.
    - NO envía nada al SRI.
    - NO reserva secuencial.
    - NO genera clave de acceso.

    El abono permanece REGISTRADO mientras la factura esté en:
    BORRADOR / GENERADO / FIRMADO / RECIBIDO / RECHAZADO.

    El cambio del abono a FACTURADO deberá realizarse únicamente
    cuando la factura quede AUTORIZADA por el SRI.
    """

    # =====================================================
    # BLOQUEAR ABONO
    # =====================================================

    abono = (
        AbonoOrdenTrabajo.objects
        # Bloqueamos únicamente la fila del abono.
        #
        # Algunas relaciones cargadas con select_related() son nullable
        # (por ejemplo cliente/sucursal). PostgreSQL las resuelve mediante
        # OUTER JOIN y no permite aplicar FOR UPDATE sobre el lado nullable.
        #
        # of=("self",) conserva el bloqueo pesimista que necesitamos para
        # evitar doble facturación del mismo abono, sin intentar bloquear
        # las tablas relacionadas.
        .select_for_update(of=("self",))
        .select_related(
            "orden",
            "orden__cliente",
            "orden__sucursal",
            "orden__sucursal__empresa",
        )
        .get(
            pk=abono.pk,
        )
    )

    orden = abono.orden

    # =====================================================
    # VALIDAR ESTADO DEL ABONO
    # =====================================================

    if abono.estado != "REGISTRADO":
        raise ValidationError(
            (
                "Solo se puede crear una factura desde un "
                "abono que se encuentre REGISTRADO."
            )
        )

    # =====================================================
    # EVITAR DOBLE FACTURACIÓN DEL MISMO ABONO
    # =====================================================

    factura_existente = (
        FacturaVenta.objects
        .filter(
            abono_origen=abono,
        )
        .first()
    )

    if factura_existente:
        raise ValidationError(
            (
                "Este abono ya tiene una factura asociada "
                f"(factura #{factura_existente.pk})."
            )
        )

    # =====================================================
    # VALIDAR PERÍODO DE FACTURACIÓN MAO
    # =====================================================

    if not orden.facturable_en_mao:
        raise ValidationError(
            (
                "La Orden de Trabajo asociada al abono pertenece "
                "al período de facturación anterior y no puede "
                "facturarse nuevamente en MAO."
            )
        )

    # =====================================================
    # SUCURSAL / EMPRESA
    # =====================================================

    if not orden.sucursal_id:
        raise ValidationError(
            "La OT asociada al abono no tiene sucursal."
        )

    empresa = getattr(
        orden.sucursal,
        "empresa",
        None,
    )

    if empresa is None:
        raise ValidationError(
            (
                "La sucursal de la OT no tiene una "
                "EmpresaEmisora configurada."
            )
        )

    # =====================================================
    # COMPRADOR
    # =====================================================

    if not datos_comprador:
        raise ValidationError(
            (
                "Los datos del comprador son obligatorios "
                "para crear la factura del abono."
            )
        )

    campos_comprador = {
        "tipo_identificacion_comprador",
        "identificacion_comprador",
        "razon_social_comprador",
        "direccion_comprador",
        "telefono_comprador",
        "correo_comprador",
    }

    faltantes = [
        campo
        for campo in (
            "tipo_identificacion_comprador",
            "identificacion_comprador",
            "razon_social_comprador",
        )
        if not datos_comprador.get(campo)
    ]

    if faltantes:
        raise ValidationError(
            (
                "Faltan datos obligatorios del comprador "
                "para la factura del abono."
            )
        )

    datos_comprador_limpios = {
        campo:
            datos_comprador.get(campo, "")
        for campo in campos_comprador
    }

    # =====================================================
    # MONTO
    # =====================================================

    monto_abono = _q2(
        abono.monto
    )

    if monto_abono <= CERO:
        raise ValidationError(
            (
                "El abono no tiene un monto válido "
                "para facturación."
            )
        )

    # =====================================================
    # IVA
    # =====================================================

    porcentaje_iva = _q2(
        orden.porcentaje_iva
        or CERO
    )

    # Mantener el mismo criterio de seguridad usado en
    # la factura normal: si existe IVA pero la OT aún no
    # lo suma al total, no interpretamos fiscalmente el abono.
    if (
        porcentaje_iva > CERO
        and not orden.sumar_iva_al_total
    ):
        raise ValidationError(
            (
                "La OT tiene IVA configurado pero no sumado "
                "al total. Antes de facturar el abono debes "
                "definir correctamente el tratamiento del IVA."
            )
        )

    valores = _descomponer_monto_abono(
        monto=monto_abono,
        porcentaje_iva=porcentaje_iva,
    )

    base = valores["base"]
    iva = valores["iva"]

    # =====================================================
    # FIRMA ELECTRÓNICA
    # =====================================================

    firma = None

    if hasattr(
        empresa,
        "obtener_firma_vigente",
    ):
        firma = (
            empresa
            .obtener_firma_vigente()
        )

    # La ausencia de firma NO bloquea el BORRADOR.
    # La firma sí será obligatoria al emitir.

    # =====================================================
    # INFORMACIÓN ADICIONAL
    # =====================================================

    datos_adicionales = [
        f"Anticipo / abono de OT: {orden.numero_orden}",
        f"Abono ID: {abono.pk}",
        f"Monto recibido: ${monto_abono:.2f}",
    ]

    if orden.placa:
        datos_adicionales.append(
            f"Placa: {orden.placa}"
        )

    if orden.vehiculo:
        datos_adicionales.append(
            f"Vehículo: {orden.vehiculo}"
        )

    if abono.observacion:
        datos_adicionales.append(
            f"Observación abono: {abono.observacion}"
        )

    # =====================================================
    # CREAR CABECERA DE FACTURA
    # =====================================================

    factura = FacturaVenta.objects.create(

        # Una factura de abono NO factura la OT completa.
        orden=None,

        # Trazabilidad directa al abono.
        abono_origen=abono,

        sucursal=
            orden.sucursal,

        empresa=
            empresa,

        firma_electronica=
            firma,

        # -----------------------------------------
        # SNAPSHOT DE ORIGEN
        # -----------------------------------------

        numero_orden_origen=
            str(orden.numero_orden),

        placa_snapshot=
            (orden.placa or "").strip(),

        vehiculo_snapshot=
            (orden.vehiculo or "").strip(),

        anio_vehiculo_snapshot=
            orden.anio_vehiculo,

        color_snapshot=
            (
                getattr(
                    orden,
                    "color",
                    None,
                )
                or ""
            ).strip(),

        kilometraje_snapshot=
            orden.kilometraje,

        # -----------------------------------------
        # COMPRADOR
        # -----------------------------------------

        **datos_comprador_limpios,

        # -----------------------------------------
        # IVA
        # -----------------------------------------

        porcentaje_iva=
            porcentaje_iva,

        # -----------------------------------------
        # SNAPSHOT ECONÓMICO DEL ABONO
        # -----------------------------------------

        total_sin_impuestos=
            base,

        total_descuento=
            CERO,

        subtotal_gravado=
            valores[
                "subtotal_gravado"
            ],

        subtotal_iva_0=
            valores[
                "subtotal_iva_0"
            ],

        valor_iva=
            iva,

        importe_total=
            monto_abono,

        # -----------------------------------------
        # TRAZABILIDAD
        # -----------------------------------------

        comentario=(
            f"Factura generada desde abono "
            f"#{abono.pk} de "
            f"{orden.numero_orden}"
        ),

        observaciones=(
            " | ".join(
                datos_adicionales
            )
        ),
    )

    # =====================================================
    # CREAR LÍNEA ANTICIPO
    # =====================================================

    descripcion = (
        f"ANTICIPO / ABONO {orden.numero_orden}"
    )

    if abono.observacion:
        descripcion = (
            f"{descripcion} - "
            f"{abono.observacion}"
        )

    descripcion = descripcion[:500]

    detalle = DetalleFacturaVenta.objects.create(

        factura=
            factura,

        tipo_origen=
            "ANTICIPO",

        orden_origen=
            0,

        codigo_principal=
            f"ANT-{abono.pk}"[:50],

        codigo_auxiliar=
            str(
                orden.numero_orden
            )[:50],

        descripcion=
            descripcion,

        cantidad=
            UNO,

        precio_unitario=
            base,

        descuento=
            CERO,

        # Estos campos son recalculados también por
        # DetalleFacturaVenta.save(), pero se incluyen
        # explícitamente para dejar clara la intención.
        precio_total_sin_impuesto=
            base,

        codigo_impuesto=
            "2",

        codigo_porcentaje_iva=
            valores[
                "codigo_porcentaje_iva"
            ],

        tarifa_iva=
            porcentaje_iva,

        base_imponible=
            base,

        valor_iva=
            iva,

        unidad_medida=
            "SERVICIO",

        observaciones=(
            (
                f"Abono registrado el "
                f"{abono.fecha:%d/%m/%Y %H:%M}"
            )
        ),
    )

    # =====================================================
    # VERIFICACIÓN FINAL
    # =====================================================

    factura.refresh_from_db()
    detalle.refresh_from_db()

    if _q2(
        factura.total_descuento
    ) != CERO:
        raise ValidationError(
            (
                "La factura del abono generó un "
                "descuento inesperado."
            )
        )

    if _q2(
        factura.total_sin_impuestos
    ) != base:
        raise ValidationError(
            (
                "La base de la factura del abono "
                "no coincide con la base calculada."
            )
        )

    if _q2(
        factura.valor_iva
    ) != iva:
        raise ValidationError(
            (
                "El IVA de la factura del abono "
                "no coincide con el IVA calculado."
            )
        )

    if _q2(
        factura.importe_total
    ) != monto_abono:
        raise ValidationError(
            (
                "El total de la factura del abono no "
                "coincide exactamente con el monto recibido. "
                f"Factura: ${_q2(factura.importe_total):.2f} | "
                f"Abono: ${monto_abono:.2f}. "
                "La factura NO fue creada."
            )
        )

    if detalle.tipo_origen != "ANTICIPO":
        raise ValidationError(
            (
                "La línea creada no quedó identificada "
                "como ANTICIPO."
            )
        )

    # IMPORTANTE:
    # NO modificar abono.estado aquí.
    #
    # El abono seguirá REGISTRADO hasta que la factura
    # sea realmente AUTORIZADA por el SRI.

    return factura
