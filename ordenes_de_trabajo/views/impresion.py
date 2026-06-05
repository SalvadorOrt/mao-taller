# ordenes_de_trabajo/views/impresion.py

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


def obtener_porcentaje_iva_activo():
    config = ConfiguracionTributaria.objects.filter(
        activa=True
    ).order_by("-fecha_inicio", "-id").first()

    if config:
        return Decimal(str(config.porcentaje_iva))

    return Decimal("0.00")


@login_required
@xframe_options_sameorigin
def imprimir_tecnico(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related("sucursal__empresa"),
        pk=pk,
    )

    empresa_ligada = orden.sucursal.empresa if orden.sucursal else None

    if not empresa_ligada:
        empresa_ligada = EmpresaEmisora.objects.filter(activo=True).first()

    chk = OrdenChecklistRecepcion.objects.filter(orden=orden).first()
    croquis = OrdenCroquisDanio.objects.filter(orden=orden).first()

    return render(
        request,
        "impresion/imprimir_tecnico.html",
        {
            "orden": orden,
            "empresa": empresa_ligada,
            "chk": chk,
            "croquis": croquis,
        },
    )


@login_required
@xframe_options_sameorigin
def imprimir_resumen_orden(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "sucursal__empresa",
            "cliente",
            "expediente",
        ).prefetch_related(
            "insumos_detalles",
            "servicios_detalles",
            "servicios_detalles__procedimientos_detalle",
            "insumos_historicos",
            "servicios_historicos",
            "recomendaciones_items",
        ),
        pk=pk,
    )

    empresa_ligada = orden.sucursal.empresa if orden.sucursal else None

    if not empresa_ligada:
        empresa_ligada = EmpresaEmisora.objects.filter(activo=True).first()

    repuestos = orden.insumos_detalles.all()
    servicios = orden.servicios_detalles.all()
    recomendaciones = orden.recomendaciones_items.all()

    repuestos_historicos = orden.insumos_historicos.all() if orden.es_migrada else []
    servicios_historicos = orden.servicios_historicos.all() if orden.es_migrada else []

    subtotal_repuestos = sum(
        Decimal(rep.subtotal or 0)
        for rep in repuestos
    ) + sum(
        Decimal(rep.subtotal or 0)
        for rep in repuestos_historicos
    )

    subtotal_moi = sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios
        if (
            serv.tipo_servicio != "EXT"
            and getattr(serv.servicio, "categoria", None) != "EXT"
        )
    ) + sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios_historicos
        if serv.tipo == "MO"
    )

    subtotal_moe = sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios
        if (
            serv.tipo_servicio == "EXT"
            or getattr(serv.servicio, "categoria", None) == "EXT"
        )
    ) + sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios_historicos
        if serv.tipo == "MOE"
    )

    orden.calcular_total()

    subtotal = Decimal(orden.subtotal_sin_iva or 0)
    descuento = Decimal(orden.valor_descuento or 0)
    porcentaje_descuento = Decimal(orden.descuento_porcentaje or 0)
    porcentaje_iva = Decimal(orden.porcentaje_iva or 0)
    iva = Decimal(orden.valor_iva or 0)
    total_final = Decimal(orden.total_final or 0)

    return render(
        request,
        "impresion/resumen_orden.html",
        {
            "orden": orden,
            "empresa": empresa_ligada,
            "repuestos": repuestos,
            "servicios": servicios,
            "repuestos_historicos": repuestos_historicos,
            "servicios_historicos": servicios_historicos,
            "recomendaciones": recomendaciones,
            "subtotal_repuestos": subtotal_repuestos,
            "subtotal_moi": subtotal_moi,
            "subtotal_moe": subtotal_moe,
            "subtotal": subtotal,
            "descuento": descuento,
            "porcentaje_descuento": porcentaje_descuento,
            "porcentaje_iva": porcentaje_iva,
            "iva": iva,
            "total_final": total_final,
        },
    )


@login_required
@xframe_options_sameorigin
def imprimir_cotizacion(request, pk):
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related("sucursal__empresa"),
        pk=pk,
    )

    empresa = cotizacion.sucursal.empresa if cotizacion.sucursal else None

    if not empresa:
        empresa = EmpresaEmisora.objects.filter(activo=True).first()

    repuestos = cotizacion.insumos_cotizados.all()
    servicios = cotizacion.servicios_cotizados.all()

    sub_rep = sum(
        Decimal(item.subtotal or 0)
        for item in repuestos
    )

    sub_moi = sum(
        Decimal(item.subtotal or 0)
        for item in servicios
        if item.tipo_servicio == "MEC"
    )

    sub_moe = sum(
        Decimal(item.subtotal or 0)
        for item in servicios
        if item.tipo_servicio == "EXT"
    )

    subtotal = (
        sub_rep + sub_moi + sub_moe
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    porcentaje_iva = obtener_porcentaje_iva_activo()

    iva = (
        subtotal * porcentaje_iva / Decimal("100")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    total = (
        subtotal + iva
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return render(
        request,
        "impresion/imprimir_cotizacion.html",
        {
            "cotizacion": cotizacion,
            "empresa": empresa,
            "repuestos": repuestos,
            "servicios": servicios,
            "subtotal_repuestos": sub_rep,
            "subtotal_moi": sub_moi,
            "subtotal_moe": sub_moe,
            "subtotal": subtotal,
            "porcentaje_iva": porcentaje_iva,
            "iva": iva,
            "total": total,
        },
    )