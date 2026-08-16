"""
stock.py

Aquí no se crean productos. Solo se consulta stock.

Debe permitir:

- ver stock por sucursal
- filtrar por sucursal
- buscar producto
- ver productos sin stock
- ver stock negativo
- actualizar ubicación

Modelo principal:

StockSucursal
"""

from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from accesos.permissions import permiso_requerido

from ordenes_de_trabajo.models import Sucursal
from ordenes_de_trabajo.views.utils import (
    obtener_sucursal_activa,
    usuario_puede_cambiar_sucursal,
)

from ..models import (
    Categoria,
    CodigoProducto,
    MarcaRepuesto,
    StockSucursal,
)


# =========================================================
# SEGURIDAD DE SUCURSAL
# =========================================================

def usuario_puede_acceder_stock(
    request,
    stock,
):
    """
    Valida si el usuario puede acceder al stock indicado.

    Puede acceder cuando:

    - tiene permiso para operar entre sucursales, o
    - el stock pertenece a su sucursal activa.
    """

    if usuario_puede_cambiar_sucursal(
        request
    ):
        return True

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    if not sucursal_activa:
        return False

    return (
        stock.sucursal_id
        == sucursal_activa.id
    )


# =========================================================
# LISTADO DE STOCK
# =========================================================

@permiso_requerido(
    "inventario.view_stocksucursal"
)
def stock_lista(request):
    LIMITE_RESULTADOS = 100

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    # =====================================================
    # SUCURSALES DISPONIBLES
    # =====================================================

    if puede_cambiar_sucursal:
        sucursales = (
            Sucursal.objects
            .filter(
                activa=True
            )
            .order_by(
                "nombre"
            )
        )
    else:
        sucursales = Sucursal.objects.none()

    # =====================================================
    # SUCURSAL SOLICITADA
    # =====================================================

    sucursal_id_req = request.GET.get(
        "sucursal_filtro"
    )

    if puede_cambiar_sucursal:

        if sucursal_id_req is None:
            sucursal_filtro = (
                str(sucursal_activa.id)
                if sucursal_activa
                else "todas"
            )

        else:
            sucursal_id_req = (
                sucursal_id_req.strip()
            )

            if sucursal_id_req == "todas":
                sucursal_filtro = "todas"

            elif sucursal_id_req.isdigit():
                sucursal_valida = (
                    Sucursal.objects
                    .filter(
                        pk=int(
                            sucursal_id_req
                        ),
                        activa=True,
                    )
                    .exists()
                )

                if sucursal_valida:
                    sucursal_filtro = (
                        sucursal_id_req
                    )

                elif sucursal_activa:
                    sucursal_filtro = str(
                        sucursal_activa.id
                    )

                else:
                    sucursal_filtro = "todas"

            elif sucursal_activa:
                sucursal_filtro = str(
                    sucursal_activa.id
                )

            else:
                sucursal_filtro = "todas"

    else:
        # Usuario sin permiso:
        # ignoramos completamente lo enviado por URL.
        sucursal_filtro = (
            str(sucursal_activa.id)
            if sucursal_activa
            else ""
        )

    # =====================================================
    # FILTROS
    # =====================================================

    q = (
        request.GET
        .get(
            "q",
            "",
        )
        .strip()
    )

    categoria_id = (
        request.GET
        .get(
            "categoria",
            "",
        )
        .strip()
    )

    marca_id = (
        request.GET
        .get(
            "marca",
            "",
        )
        .strip()
    )

    estado_stock = (
        request.GET
        .get(
            "estado_stock",
            "",
        )
        .strip()
    )

    # =====================================================
    # QUERY BASE
    # =====================================================

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

    # =====================================================
    # SEGURIDAD DE SUCURSAL
    # =====================================================

    if (
        not puede_cambiar_sucursal
        and not sucursal_activa
    ):
        stocks = stocks.none()

    elif (
        sucursal_filtro
        and sucursal_filtro != "todas"
    ):
        stocks = stocks.filter(
            sucursal_id=sucursal_filtro
        )

    # =====================================================
    # BÚSQUEDA
    # =====================================================

    if q:
        stocks = stocks.filter(
            Q(
                codigo_producto__codigo__icontains=q
            )
            |
            Q(
                codigo_producto__codigo_normalizado__icontains=q
            )
            |
            Q(
                codigo_producto__codigo_barras__icontains=q
            )
            |
            Q(
                codigo_producto__nombre_comercial__icontains=q
            )
            |
            Q(
                codigo_producto__producto__sku_interno__icontains=q
            )
            |
            Q(
                codigo_producto__producto__nombre_base__icontains=q
            )
            |
            Q(
                codigo_producto__marca__nombre__icontains=q
            )
            |
            Q(
                codigo_producto__producto__categoria__nombre__icontains=q
            )
            |
            Q(
                ubicacion__icontains=q
            )
        )

    # =====================================================
    # CATEGORÍA
    # =====================================================

    if categoria_id.isdigit():
        stocks = stocks.filter(
            codigo_producto__producto__categoria_id=(
                int(categoria_id)
            )
        )

    # =====================================================
    # MARCA
    # =====================================================

    if marca_id.isdigit():
        stocks = stocks.filter(
            codigo_producto__marca_id=(
                int(marca_id)
            )
        )

    # =====================================================
    # ESTADO DEL STOCK
    # =====================================================

    if estado_stock == "con_stock":
        stocks = stocks.filter(
            cantidad__gt=0
        )

    elif estado_stock == "sin_stock":
        stocks = stocks.filter(
            cantidad=0
        )

    elif estado_stock == "stock_negativo":
        stocks = stocks.filter(
            cantidad__lt=0
        )

    elif estado_stock == "stock_bajo":
        stocks = stocks.filter(
            cantidad__gt=0,
            cantidad__lte=2,
        )

    # =====================================================
    # RESUMEN
    # =====================================================

    total_filtrado = stocks.count()

    resumen = stocks.aggregate(
        cantidad_total=Sum(
            "cantidad"
        ),
    )

    cantidad_total = (
        resumen["cantidad_total"]
        or 0
    )

    stocks = stocks[
        :LIMITE_RESULTADOS
    ]

    # =====================================================
    # MAESTROS
    # =====================================================

    categorias = (
        Categoria.objects
        .all()
        .order_by(
            "nombre"
        )
    )

    marcas = (
        MarcaRepuesto.objects
        .all()
        .order_by(
            "nombre"
        )
    )

    # =====================================================
    # TEMPLATE
    # =====================================================

    return render(
        request,
        "inventario/stock/lista.html",
        {
            "stocks": stocks,

            "sucursales": sucursales,
            "sucursal_activa": (
                sucursal_activa
            ),
            "sucursal_filtro": (
                sucursal_filtro
            ),
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),

            "q": q,
            "categoria_id": categoria_id,
            "marca_id": marca_id,
            "estado_stock": estado_stock,

            "categorias": categorias,
            "marcas": marcas,

            "total_filtrado": (
                total_filtrado
            ),
            "cantidad_total": (
                cantidad_total
            ),
            "limite_resultados": (
                LIMITE_RESULTADOS
            ),
        },
    )


# =========================================================
# DETALLE DE PRODUCTO / STOCK
# =========================================================

@permiso_requerido(
    "inventario.view_stocksucursal"
)
def stock_detalle_producto(
    request,
    codigo_id,
):
    codigo = get_object_or_404(
        CodigoProducto.objects
        .select_related(
            "producto",
            "producto__categoria",
            "marca",
        ),
        id=codigo_id,
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

    sucursal_activa = obtener_sucursal_activa(
        request
    )

    stocks = (
        StockSucursal.objects
        .filter(
            codigo_producto=codigo
        )
        .select_related(
            "sucursal"
        )
        .order_by(
            "sucursal__nombre"
        )
    )

    movimientos = (
        codigo.movimientos
        .select_related(
            "sucursal"
        )
        .order_by(
            "-fecha"
        )
    )

    # =====================================================
    # SEGURIDAD DE SUCURSAL
    # =====================================================

    if not puede_cambiar_sucursal:

        if sucursal_activa:
            stocks = stocks.filter(
                sucursal=sucursal_activa
            )

            movimientos = movimientos.filter(
                sucursal=sucursal_activa
            )

        else:
            stocks = stocks.none()
            movimientos = movimientos.none()

    total_stock = (
        stocks.aggregate(
            total=Sum(
                "cantidad"
            )
        )["total"]
        or 0
    )

    movimientos = movimientos[:30]

    return render(
        request,
        "inventario/stock/detalle_producto.html",
        {
            "codigo": codigo,
            "producto": codigo.producto,
            "stocks": stocks,
            "total_stock": total_stock,
            "movimientos": movimientos,
            "sucursal_activa": (
                sucursal_activa
            ),
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),
        },
    )


# =========================================================
# EDITAR UBICACIÓN
# =========================================================

@permiso_requerido(
    "inventario.change_stocksucursal"
)
def stock_editar_ubicacion(
    request,
    stock_id,
):
    stock = get_object_or_404(
        StockSucursal.objects
        .select_related(
            "sucursal",
            "codigo_producto",
            "codigo_producto__producto",
            "codigo_producto__marca",
        ),
        id=stock_id,
    )

    # =====================================================
    # SEGURIDAD DE SUCURSAL
    # =====================================================

    if not usuario_puede_acceder_stock(
        request,
        stock,
    ):
        messages.error(
            request,
            (
                "No tienes permisos para modificar "
                "el stock de esa sucursal."
            ),
        )

        return redirect(
            "inventario_stock_lista"
        )

    if request.method == "POST":
        ubicacion = (
            request.POST
            .get(
                "ubicacion",
                "",
            )
            .strip()
        )

        stock.ubicacion = (
            ubicacion
            or None
        )

        stock.save(
            update_fields=[
                "ubicacion",
                "actualizado_en",
            ]
        )

        messages.success(
            request,
            "Ubicación actualizada correctamente.",
        )

        return redirect(
            "inventario_stock_lista"
        )

    return render(
        request,
        "inventario/stock/form_ubicacion.html",
        {
            "stock": stock,
        },
    )


# =========================================================
# ALERTAS
# =========================================================

@permiso_requerido(
    "inventario.view_stocksucursal"
)
def stock_alertas(request):
    sucursal_activa = obtener_sucursal_activa(
        request
    )

    puede_cambiar_sucursal = (
        usuario_puede_cambiar_sucursal(
            request
        )
    )

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
            "cantidad",
            "codigo_producto__producto__nombre_base",
        )
    )

    # =====================================================
    # SEGURIDAD DE SUCURSAL
    # =====================================================

    if sucursal_activa:
        stocks = stocks.filter(
            sucursal=sucursal_activa
        )

    elif not puede_cambiar_sucursal:
        stocks = stocks.none()

    sin_stock = stocks.filter(
        cantidad=0
    )

    stock_negativo = stocks.filter(
        cantidad__lt=0
    )

    stock_bajo = stocks.filter(
        cantidad__gt=0,
        cantidad__lte=2,
    )

    return render(
        request,
        "inventario/stock/alertas.html",
        {
            "sucursal_activa": (
                sucursal_activa
            ),
            "puede_cambiar_sucursal": (
                puede_cambiar_sucursal
            ),

            "sin_stock": (
                sin_stock[:50]
            ),
            "stock_negativo": (
                stock_negativo[:50]
            ),
            "stock_bajo": (
                stock_bajo[:50]
            ),

            "total_sin_stock": (
                sin_stock.count()
            ),
            "total_stock_negativo": (
                stock_negativo.count()
            ),
            "total_stock_bajo": (
                stock_bajo.count()
            ),
        },
    )