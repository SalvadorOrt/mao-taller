'''
stock.py

Aquí no se crean productos. Solo se consulta stock.

Debe permitir:

ver stock por sucursal
filtrar por sucursal
buscar producto
ver productos sin stock
ver stock negativo
actualizar ubicación

Modelo principal:

StockSucursal
'''

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum, Count
from django.shortcuts import render, redirect, get_object_or_404

from ordenes_de_trabajo.models import Sucursal
from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

from ..models import StockSucursal, CodigoProducto, Categoria, MarcaRepuesto


@login_required
def stock_lista(request):
    LIMITE_RESULTADOS = 100

    sucursal_activa = obtener_sucursal_activa(request)

    sucursales = (
        Sucursal.objects.filter(activa=True).order_by("nombre")
        if usuario_puede_cambiar_sucursal(request)
        else []
    )

    sucursal_id_req = request.GET.get("sucursal_filtro")

    if sucursal_id_req is None:
        sucursal_filtro = str(sucursal_activa.id) if sucursal_activa else "todas"
    else:
        sucursal_filtro = sucursal_id_req

    q = request.GET.get("q", "").strip()
    categoria_id = request.GET.get("categoria", "").strip()
    marca_id = request.GET.get("marca", "").strip()
    estado_stock = request.GET.get("estado_stock", "").strip()

    stocks = (
        StockSucursal.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__producto__categoria",
            "codigo_producto__marca",
        )
        .order_by(
            "codigo_producto__producto__nombre_base",
            "codigo_producto__codigo",
            "sucursal__nombre",
        )
    )

    if sucursal_filtro and sucursal_filtro != "todas":
        stocks = stocks.filter(sucursal_id=sucursal_filtro)

    if q:
        stocks = stocks.filter(
            Q(codigo_producto__codigo__icontains=q) |
            Q(codigo_producto__codigo_normalizado__icontains=q) |
            Q(codigo_producto__codigo_barras__icontains=q) |
            Q(codigo_producto__nombre_comercial__icontains=q) |
            Q(codigo_producto__producto__sku_interno__icontains=q) |
            Q(codigo_producto__producto__nombre_base__icontains=q) |
            Q(codigo_producto__marca__nombre__icontains=q) |
            Q(codigo_producto__producto__categoria__nombre__icontains=q) |
            Q(ubicacion__icontains=q)
        )

    if categoria_id:
        stocks = stocks.filter(codigo_producto__producto__categoria_id=categoria_id)

    if marca_id:
        stocks = stocks.filter(codigo_producto__marca_id=marca_id)

    if estado_stock == "con_stock":
        stocks = stocks.filter(cantidad__gt=0)

    elif estado_stock == "sin_stock":
        stocks = stocks.filter(cantidad=0)

    elif estado_stock == "stock_negativo":
        stocks = stocks.filter(cantidad__lt=0)

    elif estado_stock == "stock_bajo":
        stocks = stocks.filter(cantidad__gt=0, cantidad__lte=2)

    total_filtrado = stocks.count()

    resumen = stocks.aggregate(
        cantidad_total=Sum("cantidad"),
    )

    cantidad_total = resumen["cantidad_total"] or 0

    stocks = stocks[:LIMITE_RESULTADOS]

    categorias = Categoria.objects.all().order_by("nombre")
    marcas = MarcaRepuesto.objects.all().order_by("nombre")

    return render(request, "inventario/stock/lista.html", {
        "stocks": stocks,
        "sucursales": sucursales,
        "sucursal_activa": sucursal_activa,
        "sucursal_filtro": sucursal_filtro,
        "puede_cambiar_sucursal": usuario_puede_cambiar_sucursal(request),

        "q": q,
        "categoria_id": categoria_id,
        "marca_id": marca_id,
        "estado_stock": estado_stock,

        "categorias": categorias,
        "marcas": marcas,

        "total_filtrado": total_filtrado,
        "cantidad_total": cantidad_total,
        "limite_resultados": LIMITE_RESULTADOS,
    })


@login_required
def stock_detalle_producto(request, codigo_id):
    codigo = get_object_or_404(
        CodigoProducto.objects.select_related(
            "producto",
            "producto__categoria",
            "marca",
        ),
        id=codigo_id,
    )

    stocks = (
        StockSucursal.objects
        .filter(codigo_producto=codigo)
        .select_related("sucursal")
        .order_by("sucursal__nombre")
    )

    total_stock = stocks.aggregate(total=Sum("cantidad"))["total"] or 0

    movimientos = (
        codigo.movimientos
        .select_related("sucursal")
        .order_by("-fecha")[:30]
    )

    return render(request, "inventario/stock/detalle_producto.html", {
        "codigo": codigo,
        "producto": codigo.producto,
        "stocks": stocks,
        "total_stock": total_stock,
        "movimientos": movimientos,
    })


@login_required
def stock_editar_ubicacion(request, stock_id):
    stock = get_object_or_404(
        StockSucursal.objects.select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__marca",
        ),
        id=stock_id,
    )

    if request.method == "POST":
        ubicacion = request.POST.get("ubicacion", "").strip()

        stock.ubicacion = ubicacion or None
        stock.save(update_fields=["ubicacion", "actualizado_en"])

        messages.success(request, "Ubicación actualizada correctamente.")
        return redirect("inventario_stock_lista")

    return render(request, "inventario/stock/form_ubicacion.html", {
        "stock": stock,
    })


@login_required
def stock_alertas(request):
    sucursal_activa = obtener_sucursal_activa(request)

    stocks = (
        StockSucursal.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__producto__categoria",
            "codigo_producto__marca",
        )
        .order_by("cantidad", "codigo_producto__producto__nombre_base")
    )

    if sucursal_activa:
        stocks = stocks.filter(sucursal=sucursal_activa)

    sin_stock = stocks.filter(cantidad=0)
    stock_negativo = stocks.filter(cantidad__lt=0)
    stock_bajo = stocks.filter(cantidad__gt=0, cantidad__lte=2)

    return render(request, "inventario/stock/alertas.html", {
        "sucursal_activa": sucursal_activa,
        "sin_stock": sin_stock[:50],
        "stock_negativo": stock_negativo[:50],
        "stock_bajo": stock_bajo[:50],
        "total_sin_stock": sin_stock.count(),
        "total_stock_negativo": stock_negativo.count(),
        "total_stock_bajo": stock_bajo.count(),
    })