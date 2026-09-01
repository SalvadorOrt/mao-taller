from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction

from facturacion.models import (
    FacturaVenta,
    DetalleFacturaVenta,
    ProcedimientoDetalleFactura,
)

from ordenes_de_trabajo.models import (
    OrdenTrabajo,
)


CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")


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
# COMPRADOR
# =========================================================

def _datos_comprador(
    orden,
    comprador=None,
    consumidor_final=False,
):
    """
    Genera el snapshot del comprador.

    comprador=None
        -> usa el cliente de la OT.

    comprador=<Cliente>
        -> permite facturar a otra persona/empresa.

    consumidor_final=True
        -> consumidor final.
    """

    if consumidor_final:
        return {
            "tipo_identificacion_comprador": "07",
            "razon_social_comprador":
                "CONSUMIDOR FINAL",
            "identificacion_comprador":
                "9999999999999",
            "direccion_comprador": "",
            "telefono_comprador": "",
            "correo_comprador": "",
        }

    comprador = comprador or orden.cliente

    if comprador is None:
        raise ValidationError(
            "La Orden de Trabajo no tiene un "
            "cliente válido para facturación. "
            "Selecciona otros datos de facturación o utiliza "
            "Consumidor Final."
        )

    tipo = (
        comprador.tipo_documento
        or ""
    ).strip().upper()

    identificacion = (
        comprador.identificacion
        or ""
    ).strip()

    mapa_sri = {
        "R": "04",
        "C": "05",
        "P": "06",
    }

    tipo_sri = mapa_sri.get(tipo)

    if not tipo_sri:
        raise ValidationError(
            "El cliente seleccionado no tiene "
            "una identificación válida para "
            "facturación electrónica."
        )

    if tipo == "R":
        razon_social = (
            (
                getattr(
                    comprador,
                    "razon_social",
                    None,
                )
                or ""
            ).strip()
            or (
                comprador.nombre_completo
                or ""
            ).strip()
        )

    else:
        razon_social = (
            comprador.nombre_completo
            or ""
        ).strip()

    if not razon_social:
        raise ValidationError(
            "Los datos de facturación no tienen nombre "
            "o razón social."
        )

    return {
        "tipo_identificacion_comprador":
            tipo_sri,

        "razon_social_comprador":
            razon_social,

        "identificacion_comprador":
            identificacion,

        "direccion_comprador":
            (comprador.direccion or "").strip(),

        "telefono_comprador":
            (comprador.telefono or "").strip(),

        "correo_comprador":
            (comprador.email or "").strip(),
    }


# =========================================================
# CLONAR LÍNEAS OT
# =========================================================

def _obtener_lineas_facturables(orden):
    """
    Obtiene un snapshot estructurado de las líneas facturables de la OT.

    Conserva:
    - tipo_origen: REP / MOI / MOE
    - orden_origen: orden_item real de la OT
    - datos económicos
    - procedimientos de MOI

    La factura queda independiente de cambios posteriores en la OT.
    """

    lineas = []

    # =====================================================
    # MANO DE OBRA
    # =====================================================

    for item in orden.servicios_detalles.all():

        subtotal = _q2(item.subtotal)

        codigo = (
            f"SRV-{item.servicio_id}"
            if item.servicio_id
            else f"SRV-OT-{item.pk}"
        )

        descripcion = (
            item.descripcion_servicio
            or "SERVICIO"
        ).strip()

        if item.tipo_servicio == "EXT":
            tipo_origen = "MOE"
            tipo_mano_obra = "Mano de Obra Externa"
        else:
            tipo_origen = "MOI"
            tipo_mano_obra = "Mano de Obra Interna"

        procedimientos = []

        if tipo_origen == "MOI":
            for procedimiento in item.procedimientos_detalle.all():
                descripcion_procedimiento = (
                    procedimiento.descripcion
                    or ""
                ).strip()

                if descripcion_procedimiento:
                    procedimientos.append({
                        "descripcion":
                            descripcion_procedimiento[:500],
                        "orden":
                            procedimiento.orden_item,
                    })

        lineas.append({
            "tipo_origen":
                tipo_origen,

            "orden_origen":
                item.orden_item,

            "codigo_principal":
                codigo[:50],

            "codigo_auxiliar":
                str(orden.numero_orden)[:50],

            "descripcion":
                descripcion[:500],

            "cantidad":
                _d(item.cantidad),

            "precio_unitario":
                _d(item.precio_unitario),

            "subtotal_bruto":
                subtotal,

            "unidad_medida":
                "SERVICIO",

            "observaciones":
                tipo_mano_obra,

            "procedimientos":
                procedimientos,
        })

    # =====================================================
    # REPUESTOS
    # =====================================================

    for item in orden.insumos_detalles.all():

        subtotal = _q2(item.subtotal)

        codigo = (
            f"REP-{item.producto_id}"
            if item.producto_id
            else f"REP-OT-{item.pk}"
        )

        descripcion = (
            (
                item.descripcion_factura
                or ""
            ).strip()
            or (
                str(item.producto)
                if item.producto
                else "REPUESTO"
            )
        )

        codigo_auxiliar = (
            (
                item.codigo_barras_referencia
                or ""
            ).strip()
            or str(orden.numero_orden)
        )

        lineas.append({
            "tipo_origen":
                "REP",

            "orden_origen":
                item.orden_item,

            "codigo_principal":
                codigo[:50],

            "codigo_auxiliar":
                codigo_auxiliar[:50],

            "descripcion":
                descripcion[:500],

            "cantidad":
                _d(item.cantidad),

            "precio_unitario":
                _d(item.precio_unitario),

            "subtotal_bruto":
                subtotal,

            "unidad_medida":
                "UNIDAD",

            "observaciones":
                "",

            "procedimientos":
                [],
        })

    return lineas


# =========================================================
# DISTRIBUIR DESCUENTO
# =========================================================

def _distribuir_descuento(
    lineas,
    descuento_total,
):
    """
    La OT tiene un descuento GLOBAL.

    Para la factura electrónica se distribuye
    proporcionalmente entre las líneas.

    Se trabaja en centavos para garantizar:

    SUMA descuentos detalle
    =
    descuento OT
    """

    descuento_total = _q2(
        descuento_total
    )

    if descuento_total < CERO:
        raise ValidationError(
            "El descuento de la OT "
            "no puede ser negativo."
        )

    if not lineas:
        raise ValidationError(
            "La OT no tiene líneas para facturar."
        )

    total_bruto = sum(
        (
            _q2(
                linea["subtotal_bruto"]
            )
            for linea in lineas
        ),
        CERO,
    )

    total_bruto = _q2(
        total_bruto
    )

    if total_bruto <= CERO:
        raise ValidationError(
            "La OT no tiene un valor "
            "económico mayor a cero."
        )

    if descuento_total > total_bruto:
        raise ValidationError(
            "El descuento de la OT supera "
            "el subtotal facturable."
        )

    if descuento_total == CERO:

        for linea in lineas:
            linea["descuento"] = CERO

        return lineas

    total_centavos = int(
        (
            descuento_total
            * Decimal("100")
        ).to_integral_value(
            rounding=ROUND_HALF_UP
        )
    )

    asignaciones = []

    usados = 0

    for indice, linea in enumerate(lineas):

        bruto = _q2(
            linea["subtotal_bruto"]
        )

        exacto = (
            Decimal(total_centavos)
            * bruto
            / total_bruto
        )

        base = int(exacto)

        fraccion = (
            exacto
            - Decimal(base)
        )

        asignaciones.append({
            "indice": indice,
            "centavos": base,
            "fraccion": fraccion,
        })

        usados += base

    faltantes = (
        total_centavos
        - usados
    )

    asignaciones_ordenadas = sorted(
        asignaciones,
        key=lambda x: (
            x["fraccion"],
            -x["indice"],
        ),
        reverse=True,
    )

    for i in range(faltantes):
        asignaciones_ordenadas[
            i
        ]["centavos"] += 1

    for asignacion in asignaciones:

        descuento = (
            Decimal(
                asignacion["centavos"]
            )
            / Decimal("100")
        ).quantize(
            CENTAVO
        )

        linea = lineas[
            asignacion["indice"]
        ]

        if descuento > _q2(
            linea["subtotal_bruto"]
        ):
            raise ValidationError(
                "La distribución del descuento "
                "produjo un valor inválido."
            )

        linea["descuento"] = (
            descuento
        )

    suma_descuentos = _q2(
        sum(
            (
                linea["descuento"]
                for linea in lineas
            ),
            CERO,
        )
    )

    if suma_descuentos != descuento_total:
        raise ValidationError(
            "No se pudo distribuir exactamente "
            "el descuento de la OT."
        )

    return lineas


# =========================================================
# IVA POR DETALLE
# =========================================================

def _preparar_impuestos(
    lineas,
    porcentaje_iva,
):

    porcentaje_iva = _q2(
        porcentaje_iva
    )

    # Actualmente tu modelo Facturación
    # admite IVA 0% e IVA vigente 15%.

    if porcentaje_iva == Decimal("15.00"):
        codigo_porcentaje = "4"

    elif porcentaje_iva == Decimal("0.00"):
        codigo_porcentaje = "0"

    else:
        raise ValidationError(
            "La tarifa de IVA de la OT no "
            "está soportada por el modelo "
            "actual de facturación. "
            f"IVA encontrado: {porcentaje_iva}%."
        )

    for linea in lineas:

        bruto = _q2(
            linea["subtotal_bruto"]
        )

        descuento = _q2(
            linea.get(
                "descuento",
                CERO,
            )
        )

        base = _q2(
            bruto - descuento
        )

        if codigo_porcentaje == "4":

            iva = _q2(
                base
                * porcentaje_iva
                / Decimal("100")
            )

        else:
            iva = CERO

        linea[
            "precio_total_sin_impuesto"
        ] = base

        linea[
            "base_imponible"
        ] = base

        linea[
            "codigo_impuesto"
        ] = "2"

        linea[
            "codigo_porcentaje_iva"
        ] = codigo_porcentaje

        linea[
            "tarifa_iva"
        ] = porcentaje_iva

        linea[
            "valor_iva"
        ] = iva

    return lineas


# =========================================================
# CREAR FACTURA DESDE OT
# =========================================================

@transaction.atomic
def crear_factura_desde_orden(
    orden,
    comprador=None,
    consumidor_final=False,
):
    """
    CREA UN SNAPSHOT INMUTABLE DE LA OT.

    - NO modifica la Orden de Trabajo.
    - NO vuelve a calcular el descuento global.
    - NO cambia los precios de la OT.
    - NO genera XML.
    - NO firma XML.
    - NO envía nada al SRI.
    - La factura se crea en estado BORRADOR.

    Por defecto toma el cliente de la OT como receptor.
    La vista de preparación puede sustituir ese snapshot de
    facturación dentro de la misma transacción, sin modificar
    orden.cliente.
    """

    # =====================================================
    # BLOQUEAR OT
    # =====================================================

    orden = (
        OrdenTrabajo.objects
        .select_for_update(
            of=("self",)
        )
        .select_related(
            "sucursal",
            "sucursal__empresa",
            "cliente",
        )
        .prefetch_related(
            "servicios_detalles__procedimientos_detalle",
            "insumos_detalles",
        )
        .get(
            pk=orden.pk
        )
    )

    # =====================================================
    # VALIDAR ESTADO
    # =====================================================

    if orden.estado != "CERRADA":
        raise ValidationError(
            "Solo se puede facturar una "
            "Orden de Trabajo CERRADA."
        )

    # =====================================================
    # NO FACTURAR OTs HISTÓRICAS
    # =====================================================

    if orden.es_migrada:

        raise ValidationError(
            "Las órdenes históricas migradas "
            "no se facturan automáticamente."
        )

    # =====================================================
    # EVITAR DOBLE FACTURACIÓN
    # =====================================================

    if FacturaVenta.objects.filter(
        orden=orden
    ).exists():

        raise ValidationError(
            "Esta Orden de Trabajo "
            "ya tiene una factura."
        )

    # =====================================================
    # EMPRESA
    # =====================================================

    if not orden.sucursal_id:

        raise ValidationError(
            "La OT no tiene sucursal."
        )

    empresa = getattr(
        orden.sucursal,
        "empresa",
        None,
    )

    if empresa is None:

        raise ValidationError(
            "La sucursal no tiene una "
            "EmpresaEmisora configurada."
        )

    # =====================================================
    # EVITAR HISTÓRICOS MEZCLADOS
    # =====================================================

    if (
        orden.servicios_historicos.exists()
        or orden.insumos_historicos.exists()
    ):

        raise ValidationError(
            "Esta OT contiene registros "
            "históricos migrados y no puede "
            "facturarse automáticamente."
        )

    # =====================================================
    # IVA
    # =====================================================

    porcentaje_iva = _q2(
        orden.porcentaje_iva
        or CERO
    )

    # Si la OT calcula IVA pero no lo suma,
    # no debemos emitir automáticamente.

    if (
        porcentaje_iva > CERO
        and not orden.sumar_iva_al_total
    ):

        raise ValidationError(
            "La OT tiene IVA calculado pero "
            "no sumado al total. "
            "Antes de facturar debes definir "
            "correctamente si la venta lleva IVA."
        )

    # =====================================================
    # COMPRADOR
    # =====================================================

    datos_comprador = (
        _datos_comprador(
            orden=orden,
            comprador=comprador,
            consumidor_final=consumidor_final,
        )
    )

    # =====================================================
    # OBTENER LÍNEAS
    # =====================================================

    lineas = (
        _obtener_lineas_facturables(
            orden
        )
    )

    if not lineas:

        raise ValidationError(
            "La OT no tiene repuestos "
            "ni servicios para facturar."
        )

    # =====================================================
    # VALORES EXACTOS DE LA OT
    # =====================================================

    subtotal_ot = _q2(
        orden.subtotal_sin_iva
    )

    descuento_ot = _q2(
        orden.valor_descuento
    )

    base_ot = _q2(
        subtotal_ot
        - descuento_ot
    )

    iva_ot = _q2(
        orden.valor_iva
    )

    total_ot = _q2(
        orden.total_final
    )

    # =====================================================
    # COMPROBAR SUBTOTAL
    # =====================================================

    subtotal_lineas = _q2(
        sum(
            (
                _q2(
                    linea[
                        "subtotal_bruto"
                    ]
                )
                for linea in lineas
            ),
            CERO,
        )
    )

    if subtotal_lineas != subtotal_ot:

        raise ValidationError(
            "El subtotal de las líneas no "
            "coincide con el subtotal de la OT. "
            f"Líneas: ${subtotal_lineas} | "
            f"OT: ${subtotal_ot}."
        )

    # =====================================================
    # DISTRIBUIR DESCUENTO
    # =====================================================

    lineas = (
        _distribuir_descuento(
            lineas,
            descuento_ot,
        )
    )

    # =====================================================
    # PREPARAR IVA
    # =====================================================

    lineas = (
        _preparar_impuestos(
            lineas,
            porcentaje_iva,
        )
    )

    # =====================================================
    # COMPROBAR DETALLES
    # =====================================================

    base_detalles = _q2(
        sum(
            (
                linea[
                    "precio_total_sin_impuesto"
                ]
                for linea in lineas
            ),
            CERO,
        )
    )

    descuento_detalles = _q2(
        sum(
            (
                linea["descuento"]
                for linea in lineas
            ),
            CERO,
        )
    )

    iva_detalles = _q2(
        sum(
            (
                linea["valor_iva"]
                for linea in lineas
            ),
            CERO,
        )
    )

    # =====================================================
    # BASE EXACTA
    # =====================================================

    if base_detalles != base_ot:

        raise ValidationError(
            "La base imponible de los detalles "
            "no coincide con la OT. "
            f"Detalles: ${base_detalles} | "
            f"OT: ${base_ot}."
        )

    # =====================================================
    # DESCUENTO EXACTO
    # =====================================================

    if descuento_detalles != descuento_ot:

        raise ValidationError(
            "El descuento de los detalles "
            "no coincide con la OT."
        )

    # =====================================================
    # IVA EXACTO
    # =====================================================

    if iva_detalles != iva_ot:

        raise ValidationError(
            "El IVA calculado por detalle "
            "no coincide exactamente con "
            "el IVA de la OT. "
            f"Detalles: ${iva_detalles} | "
            f"OT: ${iva_ot}. "
            "La factura NO fue creada."
        )

    # =====================================================
    # TOTAL EXACTO
    # =====================================================

    total_detalles = _q2(
        base_detalles
        + iva_detalles
    )

    if total_detalles != total_ot:

        raise ValidationError(
            "El total de la factura no "
            "coincide con la OT. "
            f"Factura: ${total_detalles} | "
            f"OT: ${total_ot}."
        )

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

    # Si no existe firma, NO bloqueamos
    # la creación del borrador.
    #
    # Antes de firmar el XML sí será
    # obligatoria.

    # =====================================================
    # SUBTOTALES TRIBUTARIOS
    # =====================================================

    if porcentaje_iva > CERO:

        subtotal_gravado = (
            base_ot
        )

        subtotal_iva_0 = CERO

    else:

        subtotal_gravado = CERO

        subtotal_iva_0 = (
            base_ot
        )

    # =====================================================
    # INFORMACIÓN DE LA OT
    # =====================================================

    datos_adicionales = [
        f"OT: {orden.numero_orden}",
    ]

    if orden.placa:

        datos_adicionales.append(
            f"Placa: {orden.placa}"
        )

    if orden.vehiculo:

        datos_adicionales.append(
            f"Vehículo: {orden.vehiculo}"
        )

    if orden.kilometraje is not None:

        datos_adicionales.append(
            f"Kilometraje: "
            f"{orden.kilometraje}"
        )

    # =====================================================
    # CREAR FACTURA
    # =====================================================

    factura = (
        FacturaVenta.objects.create(

            orden=orden,

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
                (getattr(orden, "color", None) or "").strip(),

            kilometraje_snapshot=
                orden.kilometraje,

            # -----------------------------------------
            # COMPRADOR
            # -----------------------------------------

            **datos_comprador,

            # -----------------------------------------
            # IVA
            # -----------------------------------------

            porcentaje_iva=
                porcentaje_iva,

            # -----------------------------------------
            # SNAPSHOT ECONÓMICO
            # -----------------------------------------

            total_sin_impuestos=
                base_ot,

            total_descuento=
                descuento_ot,

            subtotal_gravado=
                subtotal_gravado,

            subtotal_iva_0=
                subtotal_iva_0,

            valor_iva=
                iva_ot,

            importe_total=
                total_ot,

            # -----------------------------------------
            # TRAZABILIDAD
            # -----------------------------------------

            comentario=(
                f"Factura generada desde "
                f"{orden.numero_orden}"
            ),

            observaciones=(
                " | ".join(
                    datos_adicionales
                )
            ),
        )
    )

    # =====================================================
    # CREAR DETALLES
    # =====================================================
    #
    # Usamos bulk_create para que
    # DetalleFacturaVenta.save()
    # NO recalcule la cabecera.
    #
    # La OT manda.
    # =====================================================

    detalles_factura = []

    for linea in lineas:

        detalle = (
            DetalleFacturaVenta(

                factura=
                    factura,

                tipo_origen=
                    linea[
                        "tipo_origen"
                    ],

                orden_origen=
                    linea[
                        "orden_origen"
                    ],

                codigo_principal=
                    linea[
                        "codigo_principal"
                    ],

                codigo_auxiliar=
                    linea[
                        "codigo_auxiliar"
                    ],

                descripcion=
                    linea[
                        "descripcion"
                    ],

                cantidad=
                    linea[
                        "cantidad"
                    ],

                precio_unitario=
                    linea[
                        "precio_unitario"
                    ],

                descuento=
                    linea[
                        "descuento"
                    ],

                precio_total_sin_impuesto=
                    linea[
                        "precio_total_sin_impuesto"
                    ],

                codigo_impuesto=
                    linea[
                        "codigo_impuesto"
                    ],

                codigo_porcentaje_iva=
                    linea[
                        "codigo_porcentaje_iva"
                    ],

                tarifa_iva=
                    linea[
                        "tarifa_iva"
                    ],

                base_imponible=
                    linea[
                        "base_imponible"
                    ],

                valor_iva=
                    linea[
                        "valor_iva"
                    ],

                unidad_medida=
                    linea[
                        "unidad_medida"
                    ],

                observaciones=
                    linea[
                        "observaciones"
                    ],
            )
        )

        detalles_factura.append(
            detalle
        )

    detalles_creados = (
        DetalleFacturaVenta.objects.bulk_create(
            detalles_factura
        )
    )

    # =====================================================
    # CONGELAR PROCEDIMIENTOS DE M.O.I.
    # =====================================================

    procedimientos_factura = []

    for detalle, linea in zip(
        detalles_creados,
        lineas,
    ):
        if linea["tipo_origen"] != "MOI":
            continue

        for procedimiento in linea.get(
            "procedimientos",
            [],
        ):
            procedimientos_factura.append(
                ProcedimientoDetalleFactura(
                    detalle=detalle,
                    descripcion=
                        procedimiento["descripcion"],
                    orden=
                        procedimiento["orden"],
                )
            )

    if procedimientos_factura:
        ProcedimientoDetalleFactura.objects.bulk_create(
            procedimientos_factura
        )

    # =====================================================
    # VERIFICACIÓN FINAL
    # =====================================================

    factura.refresh_from_db()

    if (
        _q2(
            factura.total_descuento
        )
        != descuento_ot
    ):
        raise ValidationError(
            "La factura no conservó "
            "el descuento de la OT."
        )

    if (
        _q2(
            factura.valor_iva
        )
        != iva_ot
    ):
        raise ValidationError(
            "La factura no conservó "
            "el IVA de la OT."
        )

    if (
        _q2(
            factura.importe_total
        )
        != total_ot
    ):
        raise ValidationError(
            "La factura no conservó "
            "el total final de la OT."
        )

    return factura