# facturacion/impresion.py

import re
import unicodedata
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import FacturaVenta


# ==========================================================
# UTILIDADES
# ==========================================================

def limpiar_nombre_archivo(
    valor,
    valor_defecto="SIN-DATO",
):
    """
    Convierte un valor en texto seguro para utilizar
    como nombre de archivo.

    Ejemplos:

        "001-001-000000123"
            -> "001-001-000000123"

        "PDI 4385"
            -> "PDI-4385"

        "José Pérez"
            -> "JOSE-PEREZ"

        "ABC/123"
            -> "ABC-123"
    """

    if valor is None:
        return valor_defecto

    texto = str(valor).strip()

    if not texto:
        return valor_defecto

    # ======================================================
    # ELIMINAR TILDES / CARACTERES UNICODE
    # ======================================================

    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    # ======================================================
    # MAYÚSCULAS
    # ======================================================

    texto = texto.upper()

    # ======================================================
    # CARACTERES SEGUROS
    # ======================================================

    texto = re.sub(
        r"[^A-Z0-9_-]+",
        "-",
        texto,
    )

    # ======================================================
    # EVITAR GUIONES REPETIDOS
    # ======================================================

    texto = re.sub(
        r"-{2,}",
        "-",
        texto,
    )

    # ======================================================
    # LIMPIAR EXTREMOS
    # ======================================================

    texto = texto.strip("-_")

    return texto or valor_defecto


# ==========================================================
# NOMBRE DEL DOCUMENTO DE FACTURA
# ==========================================================

def nombre_documento_factura(
    factura,
):
    """
    Genera el nombre que utilizará el navegador cuando
    el usuario seleccione:

        Guardar como PDF

    Factura autorizada / con secuencial:

        FAC-001-001-000000123_PDI4385_CLIENTE_FACTURA

    Factura que todavía está en borrador:

        FAC-BORRADOR-25_PDI4385_CLIENTE_FACTURA

    IMPORTANTE:
    La información sale exclusivamente del snapshot
    de FacturaVenta.
    """

    # ======================================================
    # NÚMERO FACTURA
    # ======================================================

    establecimiento = (
        str(factura.establecimiento or "").strip()
    )

    punto_emision = (
        str(factura.punto_emision or "").strip()
    )

    secuencial = (
        str(factura.secuencial or "").strip()
    )

    if (
        establecimiento
        and punto_emision
        and secuencial
    ):

        numero = limpiar_nombre_archivo(
            factura.numero_factura,
            f"FACTURA-{factura.pk}",
        )

        numero = f"FAC-{numero}"

    else:

        numero = (
            f"FAC-BORRADOR-{factura.pk}"
        )

    # ======================================================
    # PLACA SNAPSHOT
    # ======================================================

    placa = limpiar_nombre_archivo(
        factura.placa_snapshot,
        "",
    )

    # ======================================================
    # COMPRADOR SNAPSHOT
    # ======================================================

    comprador = limpiar_nombre_archivo(
        factura.razon_social_comprador,
        "SIN-COMPRADOR",
    )

    # ======================================================
    # RESULTADO
    # ======================================================

    partes = [
        numero,
    ]

    if placa:
        partes.append(
            placa
        )

    partes.extend(
        [
            comprador,
            "FACTURA",
        ]
    )

    return "_".join(
        partes
    )


# ==========================================================
# CONVERSIÓN SEGURA A DECIMAL
# ==========================================================

def decimal_seguro(
    valor,
):
    """
    Convierte None u otros valores válidos a Decimal.

    Evita utilizar float para cantidades monetarias.
    """

    if valor is None:
        return Decimal("0.00")

    return Decimal(
        str(valor)
    )


# ==========================================================
# FACTURA / RIDE
# ==========================================================

@login_required
@xframe_options_sameorigin
def ride_factura(
    request,
    factura_id,
):
    """
    Renderiza la representación imprimible de una factura.

    Esta vista NO genera un archivo PDF en el servidor.

    El flujo es:

        detalle_factura.html
                ↓
        iframe oculto
                ↓
        ride_factura()
                ↓
        ride_factura.html
                ↓
        window.print()
                ↓
        Chrome:
        Imprimir / Guardar como PDF

    Toda la información económica y del comprador se obtiene
    del snapshot de FacturaVenta y DetalleFacturaVenta.

    El RIDE utiliza detalles congelados de FacturaVenta:
        - REP: Repuestos e insumos
        - MOI: Mano de obra interna
        - MOE: Mano de obra externa
        - MANUAL: Venta directa sin Orden de Trabajo

    No se reconstruye la factura desde la Orden de Trabajo.
    """

    # ======================================================
    # CARGAR FACTURA
    # ======================================================

    factura = get_object_or_404(
        FacturaVenta.objects
        .select_related(
            "empresa",
            "sucursal",
            "firma_electronica",
        )
        .prefetch_related(
            "detalles",
            "detalles__procedimientos",
            "pagos",
            "pagos__entidad_financiera",
        ),
        pk=factura_id,
    )

    # ======================================================
    # EMPRESA EMISORA
    # ======================================================
    #
    # FacturaVenta ya tiene un snapshot/vínculo obligatorio
    # con EmpresaEmisora.
    #
    # NO buscamos la empresa desde OrdenTrabajo.
    # ======================================================

    empresa = factura.empresa

    # ======================================================
    # TODOS LOS DETALLES CONGELADOS
    # ======================================================

    detalles = list(
        factura.detalles.all()
    )

    # ======================================================
    # REPUESTOS
    # ======================================================

    repuestos = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "REP"
    ]

    # ======================================================
    # MANO DE OBRA INTERNA
    # ======================================================

    servicios_moi = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "MOI"
    ]

    # ======================================================
    # MANO DE OBRA EXTERNA
    # ======================================================

    servicios_moe = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "MOE"
    ]

    # ======================================================
    # VENTA MANUAL / DIRECTA
    # ======================================================

    detalles_manuales = [
        detalle
        for detalle in detalles
        if detalle.tipo_origen == "MANUAL"
    ]

    # ======================================================
    # ORDEN VISUAL
    # ======================================================
    #
    # Aunque el modelo ya tiene ordering, ordenamos
    # explícitamente para que el documento sea determinista.
    # ======================================================

    repuestos.sort(
        key=lambda item: (
            item.orden_origen,
            item.pk,
        )
    )

    servicios_moi.sort(
        key=lambda item: (
            item.orden_origen,
            item.pk,
        )
    )

    servicios_moe.sort(
        key=lambda item: (
            item.orden_origen,
            item.pk,
        )
    )

    detalles_manuales.sort(
        key=lambda item: (
            item.orden_origen,
            item.pk,
        )
    )

    # ======================================================
    # PAGOS
    # ======================================================

    pagos = list(
        factura.pagos.all()
    )

    # ======================================================
    # SUBTOTAL REPUESTOS
    # ======================================================

    subtotal_repuestos = sum(
        (
            decimal_seguro(
                item.precio_total_sin_impuesto
            )
            for item in repuestos
        ),
        Decimal("0.00"),
    )

    # ======================================================
    # SUBTOTAL M.O.I.
    # ======================================================

    subtotal_moi = sum(
        (
            decimal_seguro(
                item.precio_total_sin_impuesto
            )
            for item in servicios_moi
        ),
        Decimal("0.00"),
    )

    # ======================================================
    # SUBTOTAL M.O.E.
    # ======================================================

    subtotal_moe = sum(
        (
            decimal_seguro(
                item.precio_total_sin_impuesto
            )
            for item in servicios_moe
        ),
        Decimal("0.00"),
    )

    # ======================================================
    # SUBTOTAL VENTA MANUAL
    # ======================================================

    subtotal_manual = sum(
        (
            decimal_seguro(
                item.precio_total_sin_impuesto
            )
            for item in detalles_manuales
        ),
        Decimal("0.00"),
    )

    # ======================================================
    # TOTAL PAGADO
    # ======================================================

    total_pagado = sum(
        (
            decimal_seguro(
                pago.total
            )
            for pago in pagos
        ),
        Decimal("0.00"),
    )

    # ======================================================
    # TOTALES OFICIALES
    # ======================================================
    #
    # IMPORTANTE:
    #
    # Los totales principales NO se recalculan desde la OT
    # ni se reemplazan por los subtotales anteriores.
    #
    # Se leen directamente del comprobante congelado.
    # ======================================================

    total_sin_impuestos = decimal_seguro(
        factura.total_sin_impuestos
    )

    descuento = decimal_seguro(
        factura.total_descuento
    )

    subtotal_gravado = decimal_seguro(
        factura.subtotal_gravado
    )

    subtotal_iva_0 = decimal_seguro(
        factura.subtotal_iva_0
    )

    porcentaje_iva = decimal_seguro(
        factura.porcentaje_iva
    )

    iva = decimal_seguro(
        factura.valor_iva
    )

    propina = decimal_seguro(
        factura.propina
    )

    total_final = decimal_seguro(
        factura.importe_total
    )

    # ======================================================
    # SALDO
    # ======================================================

    saldo_pendiente = (
        total_final
        - total_pagado
    )

    if saldo_pendiente < Decimal("0.00"):
        saldo_pendiente = Decimal("0.00")

    # ======================================================
    # IDENTIFICACIÓN DEL DOCUMENTO
    # ======================================================

    numero_factura = (
        factura.numero_factura
        if (
            factura.establecimiento
            and factura.punto_emision
            and factura.secuencial
        )
        else f"BORRADOR-{factura.pk}"
    )

    # ======================================================
    # AUTORIZACIÓN
    # ======================================================

    numero_autorizacion = (
        factura.numero_autorizacion
        or ""
    )

    clave_acceso = (
        factura.clave_acceso
        or ""
    )

    # En BORRADOR no debe inventarse ni mostrarse una clave.
    # La plantilla puede usar estos booleanos para omitir por
    # completo las secciones todavía inexistentes.
    mostrar_clave_acceso = bool(
        clave_acceso
    )

    mostrar_autorizacion = bool(
        numero_autorizacion
    )

    # ======================================================
    # NOMBRE PARA GUARDAR COMO PDF
    # ======================================================

    nombre_archivo = (
        nombre_documento_factura(
            factura
        )
    )

    # ======================================================
    # RENDER
    # ======================================================

    return render(
        request,
        "facturacion/impresion/ride_factura.html",
        {
            # ===============================================
            # OBJETOS PRINCIPALES
            # ===============================================

            "factura":
                factura,

            "empresa":
                empresa,

            # ===============================================
            # IDENTIFICACIÓN
            # ===============================================

            "numero_factura":
                numero_factura,

            "numero_autorizacion":
                numero_autorizacion,

            "clave_acceso":
                clave_acceso,

            "mostrar_clave_acceso":
                mostrar_clave_acceso,

            "mostrar_autorizacion":
                mostrar_autorizacion,

            # ===============================================
            # DETALLES
            # ===============================================

            "detalles":
                detalles,

            "repuestos":
                repuestos,

            "servicios_moi":
                servicios_moi,

            "servicios_moe":
                servicios_moe,

            "detalles_manuales":
                detalles_manuales,

            # Compatibilidad temporal con templates antiguos.
            "otros_detalles":
                detalles_manuales,

            # ===============================================
            # SUBTOTALES POR SECCIÓN
            # ===============================================

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

            # ===============================================
            # TOTALES DE FACTURA
            # ===============================================

            "total_sin_impuestos":
                total_sin_impuestos,

            "descuento":
                descuento,

            "subtotal_gravado":
                subtotal_gravado,

            "subtotal_iva_0":
                subtotal_iva_0,

            "porcentaje_iva":
                porcentaje_iva,

            "iva":
                iva,

            "propina":
                propina,

            "total_final":
                total_final,

            # ===============================================
            # PAGOS
            # ===============================================

            "pagos":
                pagos,

            "total_pagado":
                total_pagado,

            "saldo_pendiente":
                saldo_pendiente,

            # ===============================================
            # NOMBRE PARA IMPRESIÓN / PDF
            # ===============================================

            "nombre_archivo":
                nombre_archivo,
        },
    )