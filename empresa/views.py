from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Prefetch
from django.core.paginator import Paginator

from inventario.models import CodigoProducto, StockSucursal
from ordenes_de_trabajo.views.utils import obtener_sucursal_activa

# =========================================================
# LISTADO GLOBAL DE INVENTARIO (Catálogo y Stock)
# =========================================================
@login_required
def lista_inventario(request):
    LIMITE_RESULTADOS = 30
    sucursal_activa = obtener_sucursal_activa(request)
    
    # 1. Base Query: Traemos productos activos con sus relaciones necesarias
    # Usamos select_related para evitar el error N+1 en Marca y Categoría
    productos_base = (
        CodigoProducto.objects.filter(activo=True, producto__activo=True)
        .select_related('producto', 'producto__categoria', 'marca')
        .order_by('producto__nombre_base')
    )

    # 2. OPTIMIZACIÓN: Traer SOLO el stock de la sucursal activa
    # Con Prefetch, logramos que Django haga una sola consulta extra para todo el stock
    stock_prefetch = Prefetch(
        'stocks_por_sucursal',
        queryset=StockSucursal.objects.filter(sucursal=sucursal_activa),
        to_attr='stock_local'
    )
    productos = productos_base.prefetch_related(stock_prefetch)

    # 3. Buscador Global
    q = request.GET.get("q", "").strip()
    if q:
        productos = productos.filter(
            Q(codigo__icontains=q) |
            Q(codigo_barras__icontains=q) |
            Q(producto__nombre_base__icontains=q) |
            Q(nombre_comercial__icontains=q)
        )

    # 4. Filtros adicionales (Opcional: puedes agregar por marca o categoría luego)
    categoria_id = request.GET.get("categoria", "")
    if categoria_id:
        productos = productos.filter(producto__categoria_id=categoria_id)

    total_filtrado = productos.count()

    # 5. Paginación
    paginator = Paginator(productos, LIMITE_RESULTADOS)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "inventario/lista_inventario.html", {
        "page_obj": page_obj,
        "q": q,
        "categoria_filtro": categoria_id,
        "total_filtrado": total_filtrado,
        "sucursal_activa": sucursal_activa,
    })