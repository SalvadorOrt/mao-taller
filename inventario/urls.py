from django.urls import path

# Importamos los submódulos de vistas directamente
from . import views
from .views import (
    catalogo,
    dashboard,
    fisico,
    maestros,
    movimientos,
    stock,
)

urlpatterns = [

    # =====================================================
    # USUARIOS
    # =====================================================
    path(
        "usuarios/",
        views.lista_usuarios,
        name="lista_usuarios",
    ),
    path(
        "usuarios/nuevo/",
        views.gestionar_usuario,
        name="crear_usuario",
    ),
    path(
        "usuarios/editar/<int:pk>/",
        views.gestionar_usuario,
        name="editar_usuario",
    ),

    # =====================================================
    # DASHBOARD
    # =====================================================
    path(
        "",
        dashboard.dashboard_inventario,
        name="inventario_dashboard",
    ),

    # =====================================================
    # CATÁLOGO
    # =====================================================
    path(
        "catalogo/",
        catalogo.catalogo_lista,
        name="inventario_catalogo",
    ),

    path(
        "catalogo/nuevo/",
        catalogo.catalogo_crear,
        name="inventario_catalogo_crear",
    ),

    path(
        "catalogo/<int:codigo_id>/",
        catalogo.catalogo_detalle,
        name="inventario_catalogo_detalle",
    ),

    path(
        "catalogo/<int:codigo_id>/editar/",
        catalogo.catalogo_editar_codigo,
        name="inventario_catalogo_editar",
    ),

    path(
        "catalogo/<int:codigo_id>/toggle/",
        catalogo.catalogo_toggle_codigo,
        name="inventario_catalogo_toggle",
    ),

    path(
        "catalogo/producto/<int:producto_id>/nuevo-codigo/",
        catalogo.catalogo_crear_codigo_equivalente,
        name="inventario_catalogo_nuevo_codigo",
    ),

    # =====================================================
    # MAESTROS
    # =====================================================

    # Categorías
    path(
        "maestros/categorias/",
        maestros.categoria_lista,
        name="categoria_lista",
    ),

    path(
        "maestros/categorias/nuevo/",
        maestros.categoria_gestionar,
        name="categoria_crear",
    ),

    path(
        "maestros/categorias/<int:pk>/editar/",
        maestros.categoria_gestionar,
        name="categoria_editar",
    ),

    path(
        "maestros/categorias/crear-rapida/",
        maestros.categoria_crear_rapida,
        name="categoria_crear_rapida",
    ),

    # Marcas
    path(
        "maestros/marcas/",
        maestros.marca_lista,
        name="marca_lista",
    ),

    path(
        "maestros/marcas/nuevo/",
        maestros.marca_gestionar,
        name="marca_crear",
    ),

    path(
        "maestros/marcas/<int:pk>/editar/",
        maestros.marca_gestionar,
        name="marca_editar",
    ),

    path(
        "maestros/marcas/crear-rapida/",
        maestros.marca_crear_rapida,
        name="marca_crear_rapida",
    ),

    # Atributos
    path(
        "maestros/atributos/",
        maestros.atributo_lista,
        name="atributo_lista",
    ),

    path(
        "maestros/atributos/nuevo/",
        maestros.atributo_gestionar,
        name="atributo_crear",
    ),

    path(
        "maestros/atributos/<int:pk>/editar/",
        maestros.atributo_gestionar,
        name="atributo_editar",
    ),

    path(
        "maestros/atributos/crear-rapido/",
        maestros.atributo_crear_rapido,
        name="atributo_crear_rapido",
    ),

    # =====================================================
    # STOCK
    # =====================================================
    path(
        "stock/",
        stock.stock_lista,
        name="inventario_stock",
    ),

    path(
        "stock/alertas/",
        stock.stock_alertas,
        name="inventario_stock_alertas",
    ),

    path(
        "stock/producto/<int:codigo_id>/",
        stock.stock_detalle_producto,
        name="inventario_stock_detalle_producto",
    ),

    path(
        "stock/<int:stock_id>/ubicacion/",
        stock.stock_editar_ubicacion,
        name="inventario_stock_editar_ubicacion",
    ),

    # =====================================================
    # MOVIMIENTOS
    # =====================================================
    path(
        "movimientos/",
        movimientos.movimiento_lista,
        name="inventario_movimientos",
    ),

    path(
        "movimientos/nuevo/",
        movimientos.movimiento_crear,
        name="inventario_movimiento_crear",
    ),

    path(
        "movimientos/<int:movimiento_id>/",
        movimientos.movimiento_detalle,
        name="inventario_movimiento_detalle",
    ),

    path(
        "movimientos/producto/<int:codigo_id>/",
        movimientos.movimiento_historial_producto,
        name="inventario_historial_producto",
    ),

    path(
        "movimientos/producto/<int:codigo_id>/entrada/",
        movimientos.movimiento_entrada_rapida,
        name="inventario_movimiento_entrada_rapida",
    ),

    path(
        "movimientos/producto/<int:codigo_id>/salida/",
        movimientos.movimiento_salida_rapida,
        name="inventario_movimiento_salida_rapida",
    ),

    # =====================================================
    # INVENTARIO FÍSICO
    # =====================================================
    path(
        "fisico/",
        fisico.inventario_fisico_lista,
        name="inventario_fisico",
    ),

    path(
        "fisico/nuevo/",
        fisico.inventario_fisico_crear,
        name="inventario_fisico_crear",
    ),

    path(
        "fisico/<int:inventario_id>/",
        fisico.inventario_fisico_detalle,
        name="inventario_fisico_detalle",
    ),
]