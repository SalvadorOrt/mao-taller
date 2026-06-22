'''
dashboard.py

Resumen general.

Debe mostrar:

total productos
productos activos
productos sin stock
stock negativo
últimos movimientos
alertas

Usa consultas de:

Producto
CodigoProducto
StockSucursal
MovimientoStock
'''

from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.shortcuts import render

from ordenes_de_trabajo.models import Sucursal
from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

from ..models import (
    Producto,
    CodigoProducto,
    StockSucursal,
    MovimientoStock,
    InventarioFisico,
)


@login_required
def dashboard_inventario(request):
    sucursal_activa = obtener_sucursal_activa(request)

    sucursales = (
        Sucursal.objects.filter(activa=True).order_by("nombre")
        if usuario_puede_cambiar_sucursal(request)
        else []
    )

    sucursal_id_req = request.GET.get("sucursal", "").strip()

    if sucursal_id_req:
        sucursal_filtro = sucursal_id_req
    elif sucursal_activa:
        sucursal_filtro = str(sucursal_activa.id)
    else:
        sucursal_filtro = ""

    stocks = (
        StockSucursal.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__marca",
            "codigo_producto__producto__categoria",
        )
    )

    movimientos = (
        MovimientoStock.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__marca",
        )
    )

    inventarios = InventarioFisico.objects.select_related("sucursal")

    if sucursal_filtro:
        stocks = stocks.filter(sucursal_id=sucursal_filtro)
        movimientos = movimientos.filter(sucursal_id=sucursal_filtro)
        inventarios = inventarios.filter(sucursal_id=sucursal_filtro)

    total_productos = Producto.objects.filter(activo=True).count()
    total_codigos = CodigoProducto.objects.filter(activo=True).count()

    total_items_stock = stocks.count()
    cantidad_total_stock = stocks.aggregate(total=Sum("cantidad"))["total"] or Decimal("0.00")

    productos_con_stock = stocks.filter(cantidad__gt=0).count()
    productos_sin_stock = stocks.filter(cantidad=0).count()
    productos_stock_negativo = stocks.filter(cantidad__lt=0).count()
    productos_stock_bajo = stocks.filter(cantidad__gt=0, cantidad__lte=2).count()

    ultimos_movimientos = movimientos.order_by("-fecha")[:10]

    ultimos_inventarios = (
        inventarios
        .annotate(total_detalles=Count("detalles"))
        .order_by("-fecha_inicio")[:5]
    )

    stock_negativo = (
        stocks
        .filter(cantidad__lt=0)
        .order_by("cantidad")[:10]
    )

    stock_bajo = (
        stocks
        .filter(cantidad__gt=0, cantidad__lte=2)
        .order_by("cantidad")[:10]
    )

    codigos_sin_precio = (
        CodigoProducto.objects
        .select_related("producto", "marca")
        .filter(Q(precio_venta__isnull=True) | Q(precio_venta=0))
        .order_by("producto__nombre_base")[:10]
    )

    return render(request, "inventario/dashboard.html", {
        "sucursal_activa": sucursal_activa,
        "sucursales": sucursales,
        "sucursal_filtro": sucursal_filtro,
        "puede_cambiar_sucursal": usuario_puede_cambiar_sucursal(request),

        "total_productos": total_productos,
        "total_codigos": total_codigos,
        "total_items_stock": total_items_stock,
        "cantidad_total_stock": cantidad_total_stock,

        "productos_con_stock": productos_con_stock,
        "productos_sin_stock": productos_sin_stock,
        "productos_stock_negativo": productos_stock_negativo,
        "productos_stock_bajo": productos_stock_bajo,

        "ultimos_movimientos": ultimos_movimientos,
        "ultimos_inventarios": ultimos_inventarios,
        "stock_negativo": stock_negativo,
        "stock_bajo": stock_bajo,
        "codigos_sin_precio": codigos_sin_precio,
    })