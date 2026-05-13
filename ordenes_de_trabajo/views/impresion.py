# ordenes_de_trabajo/views/impresion.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_sameorigin
from decimal import Decimal
from empresa.models import EmpresaEmisora
from ..models import OrdenTrabajo, OrdenChecklistRecepcion, OrdenCroquisDanio
from ..models import OrdenTrabajo, OrdenChecklistRecepcion, OrdenCroquisDanio, Cotizacion
# ==========================================
# IMPRESIÓN 1: FICHA TÉCNICA (Uso Interno)
# ==========================================
@login_required
@xframe_options_sameorigin
def imprimir_tecnico(request, pk):
    orden = get_object_or_404(OrdenTrabajo.objects.select_related('sucursal__empresa'), pk=pk)
    
    empresa_ligada = orden.sucursal.empresa if orden.sucursal else None
    if not empresa_ligada:
        empresa_ligada = EmpresaEmisora.objects.filter(activo=True).first()

    chk = OrdenChecklistRecepcion.objects.filter(orden=orden).first()
    croquis = OrdenCroquisDanio.objects.filter(orden=orden).first()

    return render(request, "impresion/imprimir_tecnico.html", {
        "orden": orden,
        "empresa": empresa_ligada,
        "chk": chk,         
        "croquis": croquis, 
    })

@login_required
@xframe_options_sameorigin
def imprimir_resumen_orden(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "sucursal__empresa",
            "cliente",
            "expediente"
        ).prefetch_related(
            "insumos_detalles",
            "servicios_detalles",
            "insumos_historicos",
            "servicios_historicos",
        ),
        pk=pk
    )

    empresa_ligada = orden.sucursal.empresa if orden.sucursal else None
    if not empresa_ligada:
        empresa_ligada = EmpresaEmisora.objects.filter(activo=True).first()

    repuestos = orden.insumos_detalles.all()
    servicios = orden.servicios_detalles.all()

    repuestos_historicos = orden.insumos_historicos.all() if orden.es_migrada else []
    servicios_historicos = orden.servicios_historicos.all() if orden.es_migrada else []

    subtotal_repuestos = sum(
        Decimal(rep.subtotal or 0) for rep in repuestos
    ) + sum(
        Decimal(rep.subtotal or 0) for rep in repuestos_historicos
    )

    subtotal_moi = sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios
        if serv.tipo_servicio != "EXT" and getattr(serv.servicio, "categoria", None) != "EXT"
    ) + sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios_historicos
        if serv.tipo == "MO"
    )

    subtotal_moe = sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios
        if serv.tipo_servicio == "EXT" or getattr(serv.servicio, "categoria", None) == "EXT"
    ) + sum(
        Decimal(serv.subtotal or 0)
        for serv in servicios_historicos
        if serv.tipo == "MOE"
    )

    subtotal = subtotal_repuestos + subtotal_moi + subtotal_moe
    iva = subtotal * Decimal("0.15")
    total_final = subtotal + iva

    return render(request, "impresion/resumen_orden.html", {
        "orden": orden,
        "empresa": empresa_ligada,
        "repuestos": repuestos,
        "servicios": servicios,
        "repuestos_historicos": repuestos_historicos,
        "servicios_historicos": servicios_historicos,

        "subtotal_repuestos": subtotal_repuestos,
        "subtotal_moi": subtotal_moi,
        "subtotal_moe": subtotal_moe,
        "subtotal": subtotal,
        "iva": iva,
        "total_final": total_final,
    })


@login_required
@xframe_options_sameorigin
def imprimir_cotizacion(request, pk):
    """
    Genera la vista de impresión para una Proforma/Cotización.
    """
    # 1. Obtenemos la cotización con sus relaciones
    cotizacion = get_object_or_404(
        Cotizacion.objects.select_related(
            "sucursal__empresa",
            "cliente",
            "orden"
        ).prefetch_related(
            "insumos_cotizados",
            "servicios_cotizados",
        ),
        pk=pk
    )

    # 2. Obtenemos los datos de la empresa para el logo y RUC
    empresa_ligada = cotizacion.sucursal.empresa if cotizacion.sucursal else None
    if not empresa_ligada:
        empresa_ligada = EmpresaEmisora.objects.filter(activo=True).first()

    # 3. Clasificamos los subtotales para el desglose
    repuestos = cotizacion.insumos_cotizados.all()
    servicios = cotizacion.servicios_cotizados.all()

    subtotal_repuestos = sum(Decimal(rep.subtotal or 0) for rep in repuestos)
    
    # Mano de Obra Interna (MEC)
    subtotal_moi = sum(
        Decimal(serv.subtotal or 0) 
        for serv in servicios 
        if serv.tipo_servicio == "MEC"
    )

    # Mano de Obra Externa (EXT)
    subtotal_moe = sum(
        Decimal(serv.subtotal or 0) 
        for serv in servicios 
        if serv.tipo_servicio == "EXT"
    )

    # 4. Cálculos finales
    subtotal = subtotal_repuestos + subtotal_moi + subtotal_moe
    iva = subtotal * Decimal("0.15") # IVA Ecuador 15%
    total_final = subtotal + iva

    return render(request, "impresion/imprimir_cotizacion.html", {
        "cotizacion": cotizacion,
        "empresa": empresa_ligada,
        "repuestos": repuestos,
        "servicios": servicios,
        "subtotal_repuestos": subtotal_repuestos,
        "subtotal_moi": subtotal_moi,
        "subtotal_moe": subtotal_moe,
        "subtotal": subtotal,
        "iva": iva,
        "total_final": total_final,
    })