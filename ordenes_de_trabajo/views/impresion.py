# ordenes_de_trabajo/views/impresion.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.clickjacking import xframe_options_sameorigin
from decimal import Decimal
from empresa.models import EmpresaEmisora
from ..models import OrdenTrabajo, OrdenChecklistRecepcion, OrdenCroquisDanio

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

# ==========================================
# IMPRESIÓN 2: RESUMEN DE ORDEN (Cliente)
# ==========================================
@login_required
@xframe_options_sameorigin
def imprimir_resumen_orden(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "sucursal__empresa",
            "cliente",
            "expediente"
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

    # ==========================================
    # TOTALES ECONÓMICOS
    # ==========================================
    total_final = Decimal(orden.total_general or 0)
    subtotal = total_final / Decimal("1.15")
    iva = total_final - subtotal

    return render(request, "impresion/resumen_orden.html", {
        "orden": orden,
        "empresa": empresa_ligada,
        "repuestos": repuestos,
        "servicios": servicios,
        "repuestos_historicos": repuestos_historicos,
        "servicios_historicos": servicios_historicos,

        # Totales para el HTML
        "subtotal": subtotal,
        "iva": iva,
        "total_final": total_final,
    })