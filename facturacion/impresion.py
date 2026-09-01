# facturacion/impresion.py

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .models import FacturaVenta
from .services.factura_desde_orden import (
    _distribuir_descuento,
    _obtener_lineas_facturables,
    _preparar_impuestos,
)
from ordenes_de_trabajo.models import OrdenTrabajo


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
# VISTA PREVIA DESDE OT — SIN CREAR FACTURA
# ==========================================================

CENTAVO = Decimal("0.01")
CERO = Decimal("0.00")


class _ColeccionPreview:
    """Pequeño adaptador para que la plantilla pueda usar .all()."""

    def __init__(self, items=None):
        self._items = list(items or [])

    def all(self):
        return self._items


def _q2(valor):
    return decimal_seguro(valor).quantize(
        CENTAVO,
        rounding=ROUND_HALF_UP,
    )


def _datos_comprador_preview(request, orden):
    """
    Toma primero los datos actualmente visibles en la pantalla
    POR FACTURAR (query string). Si no llegan, usa el cliente de la OT.

    Esta función NO guarda ni modifica ningún registro.
    """

    tipo = (request.GET.get("tipo_identificacion_comprador") or "").strip()
    identificacion = (request.GET.get("identificacion_comprador") or "").strip()
    razon_social = (request.GET.get("razon_social_comprador") or "").strip()
    direccion = (request.GET.get("direccion_comprador") or "").strip()
    telefono = (request.GET.get("telefono_comprador") or "").strip()
    correo = (request.GET.get("correo_comprador") or "").strip().lower()

    if tipo == "07":
        return {
            "tipo_identificacion_comprador": "07",
            "identificacion_comprador": "9999999999999",
            "razon_social_comprador": "CONSUMIDOR FINAL",
            "direccion_comprador": "",
            "telefono_comprador": "",
            "correo_comprador": "",
        }

    if tipo and identificacion and razon_social:
        return {
            "tipo_identificacion_comprador": tipo,
            "identificacion_comprador": identificacion,
            "razon_social_comprador": razon_social,
            "direccion_comprador": direccion,
            "telefono_comprador": telefono,
            "correo_comprador": correo,
        }

    cliente = orden.cliente

    if not cliente:
        return {
            "tipo_identificacion_comprador": "07",
            "identificacion_comprador": "9999999999999",
            "razon_social_comprador": "CONSUMIDOR FINAL",
            "direccion_comprador": "",
            "telefono_comprador": "",
            "correo_comprador": "",
        }

    tipo_documento = (getattr(cliente, "tipo_documento", "") or "").strip().upper()
    mapa_sri = {
        "R": "04",
        "C": "05",
        "P": "06",
    }

    tipo_sri = mapa_sri.get(tipo_documento, "05")

    if tipo_documento == "R":
        razon_social_cliente = (
            (getattr(cliente, "razon_social", "") or "").strip()
            or (getattr(cliente, "nombre_completo", "") or "").strip()
        )
    else:
        razon_social_cliente = (
            getattr(cliente, "nombre_completo", "") or ""
        ).strip()

    return {
        "tipo_identificacion_comprador": tipo_sri,
        "identificacion_comprador": (
            getattr(cliente, "identificacion", "") or ""
        ).strip(),
        "razon_social_comprador": razon_social_cliente or "POR DEFINIR",
        "direccion_comprador": (
            getattr(cliente, "direccion", "") or ""
        ).strip(),
        "telefono_comprador": (
            getattr(cliente, "telefono", "") or ""
        ).strip(),
        "correo_comprador": (
            getattr(cliente, "email", "") or ""
        ).strip().lower(),
    }


def _detalle_preview(linea, indice):
    procedimientos = [
        SimpleNamespace(
            descripcion=(procedimiento.get("descripcion") or "").strip(),
            orden=procedimiento.get("orden", 0),
        )
        for procedimiento in linea.get("procedimientos", [])
        if (procedimiento.get("descripcion") or "").strip()
    ]

    return SimpleNamespace(
        pk=indice,
        tipo_origen=linea.get("tipo_origen", ""),
        orden_origen=linea.get("orden_origen", 0),
        codigo_principal=linea.get("codigo_principal", ""),
        codigo_auxiliar=linea.get("codigo_auxiliar", ""),
        descripcion=linea.get("descripcion", ""),
        cantidad=decimal_seguro(linea.get("cantidad")),
        precio_unitario=decimal_seguro(linea.get("precio_unitario")),
        descuento=decimal_seguro(linea.get("descuento")),
        precio_total_sin_impuesto=decimal_seguro(
            linea.get("precio_total_sin_impuesto")
        ),
        observaciones=linea.get("observaciones", ""),
        procedimientos=_ColeccionPreview(procedimientos),
    )


def _nombre_documento_preview(orden, razon_social):
    partes = [
        "FAC-VISTA-PREVIA",
        limpiar_nombre_archivo(orden.numero_orden, "OT"),
    ]

    placa = limpiar_nombre_archivo(getattr(orden, "placa", ""), "")
    if placa:
        partes.append(placa)

    partes.append(limpiar_nombre_archivo(razon_social, "SIN-COMPRADOR"))
    partes.append("FACTURA")

    return "_".join(partes)


@login_required
@xframe_options_sameorigin
def vista_previa_factura_ot(request, orden_id):
    """
    Vista previa imprimible de una OT antes de crear FacturaVenta.

    GARANTÍAS:
    - NO crea FacturaVenta.
    - NO reserva secuencial.
    - NO genera clave de acceso.
    - NO genera XML.
    - NO firma.
    - NO envía nada al SRI.
    """

    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related(
            "sucursal",
            "sucursal__empresa",
            "cliente",
        )
        .prefetch_related(
            "servicios_detalles__procedimientos_detalle",
            "insumos_detalles",
        ),
        pk=orden_id,
        estado="CERRADA",
        es_migrada=False,
    )

    if not orden.sucursal_id:
        raise ValidationError("La OT no tiene una sucursal configurada.")

    empresa = getattr(orden.sucursal, "empresa", None)

    if empresa is None:
        raise ValidationError(
            "La sucursal de la OT no tiene una EmpresaEmisora configurada."
        )

    lineas = _obtener_lineas_facturables(orden)

    if not lineas:
        raise ValidationError(
            "La OT no tiene repuestos ni servicios para mostrar en la factura."
        )

    subtotal_ot = _q2(orden.subtotal_sin_iva)
    descuento = _q2(orden.valor_descuento)
    porcentaje_iva = _q2(orden.porcentaje_iva or CERO)
    iva = _q2(orden.valor_iva)
    total_final = _q2(orden.total_final)
    base_ot = _q2(subtotal_ot - descuento)

    lineas = _distribuir_descuento(lineas, descuento)
    lineas = _preparar_impuestos(lineas, porcentaje_iva)

    detalles = [
        _detalle_preview(linea, indice)
        for indice, linea in enumerate(lineas, start=1)
    ]

    repuestos = sorted(
        [item for item in detalles if item.tipo_origen == "REP"],
        key=lambda item: (item.orden_origen, item.pk),
    )
    servicios_moi = sorted(
        [item for item in detalles if item.tipo_origen == "MOI"],
        key=lambda item: (item.orden_origen, item.pk),
    )
    servicios_moe = sorted(
        [item for item in detalles if item.tipo_origen == "MOE"],
        key=lambda item: (item.orden_origen, item.pk),
    )

    subtotal_repuestos = _q2(sum(
        (decimal_seguro(item.precio_total_sin_impuesto) for item in repuestos),
        CERO,
    ))
    subtotal_moi = _q2(sum(
        (decimal_seguro(item.precio_total_sin_impuesto) for item in servicios_moi),
        CERO,
    ))
    subtotal_moe = _q2(sum(
        (decimal_seguro(item.precio_total_sin_impuesto) for item in servicios_moe),
        CERO,
    ))

    datos_comprador = _datos_comprador_preview(request, orden)

    if porcentaje_iva > CERO:
        subtotal_gravado = base_ot
        subtotal_iva_0 = CERO
    else:
        subtotal_gravado = CERO
        subtotal_iva_0 = base_ot

    datos_adicionales = [f"OT: {orden.numero_orden}"]

    if orden.placa:
        datos_adicionales.append(f"Placa: {orden.placa}")

    if orden.vehiculo:
        datos_adicionales.append(f"Vehículo: {orden.vehiculo}")

    if orden.kilometraje is not None:
        datos_adicionales.append(f"Kilometraje: {orden.kilometraje}")

    # Objeto exclusivamente EN MEMORIA. Nunca se guarda.
    factura = FacturaVenta(
        orden=orden,
        sucursal=orden.sucursal,
        empresa=empresa,
        numero_orden_origen=str(orden.numero_orden),
        placa_snapshot=(orden.placa or "").strip(),
        vehiculo_snapshot=(orden.vehiculo or "").strip(),
        anio_vehiculo_snapshot=orden.anio_vehiculo,
        color_snapshot=(getattr(orden, "color", None) or "").strip(),
        kilometraje_snapshot=orden.kilometraje,
        fecha_emision=timezone.localdate(),
        estado="BORRADOR",
        porcentaje_iva=porcentaje_iva,
        total_sin_impuestos=base_ot,
        total_descuento=descuento,
        subtotal_gravado=subtotal_gravado,
        subtotal_iva_0=subtotal_iva_0,
        valor_iva=iva,
        importe_total=total_final,
        comentario=f"Factura generada desde {orden.numero_orden}",
        observaciones=" | ".join(datos_adicionales),
        **datos_comprador,
    )

    nombre_archivo = _nombre_documento_preview(
        orden,
        factura.razon_social_comprador,
    )

    return render(
        request,
        "facturacion/impresion/ride_factura.html",
        {
            "factura": factura,
            "empresa": empresa,
            "es_vista_previa": True,
            "numero_factura": "POR EMITIR",
            "numero_autorizacion": "",
            "clave_acceso": "",
            "mostrar_clave_acceso": False,
            "mostrar_autorizacion": False,
            "detalles": detalles,
            "repuestos": repuestos,
            "servicios_moi": servicios_moi,
            "servicios_moe": servicios_moe,
            "detalles_manuales": [],
            "otros_detalles": [],
            "subtotal_repuestos": subtotal_repuestos,
            "subtotal_moi": subtotal_moi,
            "subtotal_moe": subtotal_moe,
            "subtotal_manual": CERO,
            "subtotal_otros": CERO,
            "total_sin_impuestos": base_ot,
            "descuento": descuento,
            "subtotal_gravado": subtotal_gravado,
            "subtotal_iva_0": subtotal_iva_0,
            "porcentaje_iva": porcentaje_iva,
            "iva": iva,
            "propina": CERO,
            "total_final": total_final,
            "pagos": [],
            "total_pagado": CERO,
            "saldo_pendiente": total_final,
            "nombre_archivo": nombre_archivo,
        },
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

            "es_vista_previa":
                False,

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