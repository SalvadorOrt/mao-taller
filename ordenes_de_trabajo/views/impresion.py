# ordenes_de_trabajo/views/impresion.py

import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_sameorigin

from empresa.models import EmpresaEmisora

from ..models import (
    ConfiguracionTributaria,
    Cotizacion,
    OrdenChecklistRecepcion,
    OrdenCroquisDanio,
    OrdenTrabajo,
)


# ==========================================================
# UTILIDADES
# ==========================================================

def limpiar_nombre_archivo(valor, valor_defecto="SIN-DATO"):
    """
    Convierte cualquier valor en un texto seguro para utilizar
    como nombre de archivo.

    Ejemplos:
        "OT-24522"       -> "OT-24522"
        "PDI 4385"       -> "PDI-4385"
        "José Pérez"     -> "JOSE-PEREZ"
        "ABC/123"        -> "ABC-123"
    """

    if valor is None:
        return valor_defecto

    texto = str(valor).strip()

    if not texto:
        return valor_defecto

    # Elimina tildes y caracteres Unicode problemáticos.
    texto = unicodedata.normalize(
        "NFKD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = texto.upper()

    # Todo lo que no sea letra, número, guion o guion bajo
    # se convierte en guion.
    texto = re.sub(
        r"[^A-Z0-9_-]+",
        "-",
        texto,
    )

    # Elimina guiones repetidos.
    texto = re.sub(
        r"-{2,}",
        "-",
        texto,
    )

    # Elimina guiones sobrantes al inicio/final.
    texto = texto.strip("-_")

    return texto or valor_defecto


def nombre_documento_orden(
    orden,
    tipo_documento,
):
    """
    Estructura estándar:

        OT-24522_PDI4385_FICHA-TECNICA
        OT-24522_PDI4385_RESUMEN-ORDEN
        OT-24522_PDI4385_PROFORMA
    """

    numero_orden = limpiar_nombre_archivo(
        orden.numero_orden,
        f"OT-{orden.pk}",
    )

    placa = limpiar_nombre_archivo(
        orden.placa,
        "SIN-PLACA",
    )

    tipo_documento = limpiar_nombre_archivo(
        tipo_documento,
        "DOCUMENTO",
    )

    return (
        f"{numero_orden}_"
        f"{placa}_"
        f"{tipo_documento}"
    )


def nombre_documento_cotizacion(cotizacion):
    """
    Estructura estándar:

        COT-00125_PDI4385_COTIZACION

    Si numero_cotizacion ya contiene COT-,
    no vuelve a agregarlo.
    """

    numero = limpiar_nombre_archivo(
        cotizacion.numero_cotizacion,
        str(cotizacion.pk),
    )

    placa = limpiar_nombre_archivo(
        cotizacion.placa,
        "SIN-PLACA",
    )

    if not numero.startswith("COT-"):
        numero = f"COT-{numero}"

    return (
        f"{numero}_"
        f"{placa}_"
        f"COTIZACION"
    )


# ==========================================================
# IVA ACTIVO
# ==========================================================

def obtener_porcentaje_iva_activo():
    config = (
        ConfiguracionTributaria.objects
        .filter(
            activa=True
        )
        .order_by(
            "-fecha_inicio",
            "-id",
        )
        .first()
    )

    if config:
        return Decimal(
            str(config.porcentaje_iva)
        )

    return Decimal("0.00")


# ==========================================================
# IMPRIMIR FICHA TÉCNICA
# ==========================================================

@login_required
@xframe_options_sameorigin
def imprimir_tecnico(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "sucursal__empresa",
            "cliente",
            "expediente",
        ),
        pk=pk,
    )

    # ======================================================
    # EMPRESA
    # ======================================================

    empresa_ligada = (
        orden.sucursal.empresa
        if orden.sucursal
        else None
    )

    if not empresa_ligada:
        empresa_ligada = (
            EmpresaEmisora.objects
            .filter(
                activo=True
            )
            .first()
        )

    # ======================================================
    # CHECKLIST / CROQUIS
    # ======================================================

    chk = (
        OrdenChecklistRecepcion.objects
        .filter(
            orden=orden
        )
        .first()
    )

    croquis = (
        OrdenCroquisDanio.objects
        .filter(
            orden=orden
        )
        .first()
    )

    # ======================================================
    # NOMBRE DEL DOCUMENTO
    # ======================================================
    #
    # Ejemplo:
    #
    # OT-24522_PDI4385_FICHA-TECNICA
    #
    # Cuando Chrome/Edge utilice el título de la página
    # al guardar como PDF, propondrá este nombre.
    # ======================================================

    nombre_archivo = nombre_documento_orden(
        orden,
        "FICHA-TECNICA",
    )

    # ======================================================
    # RENDER
    # ======================================================

    return render(
        request,
        "impresion/imprimir_tecnico.html",
        {
            "orden": orden,
            "empresa": empresa_ligada,
            "chk": chk,
            "croquis": croquis,

            # Nombre para impresión / PDF
            "nombre_archivo": nombre_archivo,
        },
    )


# ==========================================================
# IMPRIMIR RESUMEN DE ORDEN
# ==========================================================

@login_required
@xframe_options_sameorigin
def imprimir_resumen_orden(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects
        .select_related(
            "sucursal__empresa",
            "cliente",
            "expediente",
        )
        .prefetch_related(
            "insumos_detalles",
            "servicios_detalles",
            "servicios_detalles__procedimientos_detalle",
            "insumos_historicos",
            "servicios_historicos",
            "recomendaciones_items",
        ),
        pk=pk,
    )

    # ======================================================
    # EMPRESA
    # ======================================================

    empresa_ligada = (
        orden.sucursal.empresa
        if orden.sucursal
        else None
    )

    if not empresa_ligada:
        empresa_ligada = (
            EmpresaEmisora.objects
            .filter(
                activo=True
            )
            .first()
        )

    # ======================================================
    # DETALLES
    # ======================================================

    repuestos = (
        orden.insumos_detalles.all()
    )

    servicios = (
        orden.servicios_detalles.all()
    )

    recomendaciones = (
        orden.recomendaciones_items.all()
    )

    # ======================================================
    # HISTÓRICOS
    # ======================================================

    repuestos_historicos = (
        orden.insumos_historicos.all()
        if orden.es_migrada
        else []
    )

    servicios_historicos = (
        orden.servicios_historicos.all()
        if orden.es_migrada
        else []
    )

    # ======================================================
    # SUBTOTAL REPUESTOS
    # ======================================================

    subtotal_repuestos = (
        sum(
            Decimal(
                rep.subtotal or 0
            )
            for rep in repuestos
        )
        +
        sum(
            Decimal(
                rep.subtotal or 0
            )
            for rep in repuestos_historicos
        )
    )

    # ======================================================
    # SUBTOTAL MANO DE OBRA INTERNA
    # ======================================================

    subtotal_moi = (
        sum(
            Decimal(
                serv.subtotal or 0
            )
            for serv in servicios
            if (
                serv.tipo_servicio != "EXT"
                and getattr(
                    serv.servicio,
                    "categoria",
                    None,
                ) != "EXT"
            )
        )
        +
        sum(
            Decimal(
                serv.subtotal or 0
            )
            for serv in servicios_historicos
            if serv.tipo == "MO"
        )
    )

    # ======================================================
    # SUBTOTAL MANO DE OBRA EXTERNA
    # ======================================================

    subtotal_moe = (
        sum(
            Decimal(
                serv.subtotal or 0
            )
            for serv in servicios
            if (
                serv.tipo_servicio == "EXT"
                or getattr(
                    serv.servicio,
                    "categoria",
                    None,
                ) == "EXT"
            )
        )
        +
        sum(
            Decimal(
                serv.subtotal or 0
            )
            for serv in servicios_historicos
            if serv.tipo == "MOE"
        )
    )

    # ======================================================
    # ACTUALIZAR TOTALES DE LA ORDEN
    # ======================================================

    orden.calcular_total()

    # ======================================================
    # TOTALES
    # ======================================================

    subtotal = Decimal(
        orden.subtotal_sin_iva
        or 0
    )

    descuento = Decimal(
        orden.valor_descuento
        or 0
    )

    porcentaje_descuento = Decimal(
        orden.descuento_porcentaje
        or 0
    )

    porcentaje_iva = Decimal(
        orden.porcentaje_iva
        or 0
    )

    iva = Decimal(
        orden.valor_iva
        or 0
    )

    total_final = Decimal(
        orden.total_final
        or 0
    )

    # ======================================================
    # NOMBRE DEL DOCUMENTO
    # ======================================================
    #
    # Ejemplo:
    #
    # OT-24522_PDI4385_RESUMEN-ORDEN
    #
    # ======================================================

    nombre_archivo = nombre_documento_orden(
        orden,
        "RESUMEN-ORDEN",
    )

    # ======================================================
    # RENDER
    # ======================================================

    return render(
        request,
        "impresion/resumen_orden.html",
        {
            "orden": orden,
            "empresa": empresa_ligada,

            "repuestos": repuestos,
            "servicios": servicios,

            "repuestos_historicos":
                repuestos_historicos,

            "servicios_historicos":
                servicios_historicos,

            "recomendaciones":
                recomendaciones,

            "subtotal_repuestos":
                subtotal_repuestos,

            "subtotal_moi":
                subtotal_moi,

            "subtotal_moe":
                subtotal_moe,

            "subtotal":
                subtotal,

            "descuento":
                descuento,

            "porcentaje_descuento":
                porcentaje_descuento,

            "porcentaje_iva":
                porcentaje_iva,

            "iva":
                iva,

            "total_final":
                total_final,

            # Nombre para impresión / PDF
            "nombre_archivo":
                nombre_archivo,
        },
    )


# ==========================================================
# IMPRIMIR COTIZACIÓN
# ==========================================================

@login_required
@xframe_options_sameorigin
def imprimir_cotizacion(request, pk):
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related(
            "sucursal__empresa",
            "cliente",
            "orden",
        ),
        pk=pk,
    )

    # ======================================================
    # EMPRESA
    # ======================================================

    empresa = (
        cotizacion.sucursal.empresa
        if cotizacion.sucursal
        else None
    )

    if not empresa:
        empresa = (
            EmpresaEmisora.objects
            .filter(
                activo=True
            )
            .first()
        )

    # ======================================================
    # DETALLES
    # ======================================================

    repuestos = (
        cotizacion
        .insumos_cotizados
        .all()
    )

    servicios = (
        cotizacion
        .servicios_cotizados
        .all()
    )

    # ======================================================
    # SUBTOTAL REPUESTOS
    # ======================================================

    sub_rep = sum(
        Decimal(
            item.subtotal or 0
        )
        for item in repuestos
    )

    # ======================================================
    # SUBTOTAL MANO DE OBRA INTERNA
    # ======================================================

    sub_moi = sum(
        Decimal(
            item.subtotal or 0
        )
        for item in servicios
        if item.tipo_servicio == "MEC"
    )

    # ======================================================
    # SUBTOTAL MANO DE OBRA EXTERNA
    # ======================================================

    sub_moe = sum(
        Decimal(
            item.subtotal or 0
        )
        for item in servicios
        if item.tipo_servicio == "EXT"
    )

    # ======================================================
    # SUBTOTAL
    # ======================================================

    subtotal = (
        sub_rep
        + sub_moi
        + sub_moe
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    # ======================================================
    # IVA
    # ======================================================

    porcentaje_iva = (
        obtener_porcentaje_iva_activo()
    )

    iva = (
        subtotal
        * porcentaje_iva
        / Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    # ======================================================
    # TOTAL
    # ======================================================

    total = (
        subtotal
        + iva
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

    # ======================================================
    # NOMBRE DEL DOCUMENTO
    # ======================================================
    #
    # Ejemplo:
    #
    # COT-00125_PDI4385_COTIZACION
    #
    # ======================================================

    nombre_archivo = (
        nombre_documento_cotizacion(
            cotizacion
        )
    )

    # ======================================================
    # RENDER
    # ======================================================

    return render(
        request,
        "impresion/imprimir_cotizacion.html",
        {
            "cotizacion":
                cotizacion,

            "empresa":
                empresa,

            "repuestos":
                repuestos,

            "servicios":
                servicios,

            "subtotal_repuestos":
                sub_rep,

            "subtotal_moi":
                sub_moi,

            "subtotal_moe":
                sub_moe,

            "subtotal":
                subtotal,

            "porcentaje_iva":
                porcentaje_iva,

            "iva":
                iva,

            "total":
                total,

            # Nombre para impresión / PDF
            "nombre_archivo":
                nombre_archivo,
        },
    )