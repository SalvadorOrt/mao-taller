from django.urls import path

from . import views

from .views.dashboard import dashboard_inventario

from .views.catalogo import (
    catalogo_lista,
    catalogo_detalle,
    catalogo_crear,
    catalogo_editar_codigo,
    catalogo_crear_codigo_equivalente,
    catalogo_toggle_codigo,
)

from .views.stock import (
    stock_lista,
    stock_detalle_producto,
    stock_editar_ubicacion,
    stock_alertas,
)

from .views.movimientos import (
    movimiento_lista,
    movimiento_crear,
    movimiento_detalle,
    movimiento_historial_producto,
    movimiento_entrada_rapida,
    movimiento_salida_rapida,
)

from .views.fisico import (
    inventario_fisico_lista,
    inventario_fisico_crear,
    inventario_fisico_detalle,
)

urlpatterns = [

    # =====================================================
    # USUARIOS
    # =====================================================
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views.gestionar_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:pk>/', views.gestionar_usuario, name='editar_usuario'),

    # =====================================================
    # DASHBOARD INVENTARIO
    # =====================================================
    path('', dashboard_inventario, name='inventario_dashboard'),

    # =====================================================
    # CATÁLOGO
    # =====================================================
    path('catalogo/', catalogo_lista, name='inventario_catalogo'),
    path('catalogo/nuevo/', catalogo_crear, name='inventario_catalogo_crear'),
    path('catalogo/<int:codigo_id>/', catalogo_detalle, name='inventario_catalogo_detalle'),
    path('catalogo/<int:codigo_id>/editar/', catalogo_editar_codigo, name='inventario_catalogo_editar'),
    path('catalogo/<int:codigo_id>/toggle/', catalogo_toggle_codigo, name='inventario_catalogo_toggle'),
    path(
        'catalogo/producto/<int:producto_id>/nuevo-codigo/',
        catalogo_crear_codigo_equivalente,
        name='inventario_catalogo_nuevo_codigo'
    ),

    # =====================================================
    # STOCK
    # =====================================================
    path('stock/', stock_lista, name='inventario_stock'),
    path('stock/alertas/', stock_alertas, name='inventario_stock_alertas'),
    path(
        'stock/producto/<int:codigo_id>/',
        stock_detalle_producto,
        name='inventario_stock_detalle_producto'
    ),
    path(
        'stock/<int:stock_id>/ubicacion/',
        stock_editar_ubicacion,
        name='inventario_stock_editar_ubicacion'
    ),

    # =====================================================
    # MOVIMIENTOS
    # =====================================================
    path('movimientos/', movimiento_lista, name='inventario_movimientos'),
    path('movimientos/nuevo/', movimiento_crear, name='inventario_movimiento_crear'),
    path(
        'movimientos/<int:movimiento_id>/',
        movimiento_detalle,
        name='inventario_movimiento_detalle'
    ),
    path(
        'movimientos/producto/<int:codigo_id>/',
        movimiento_historial_producto,
        name='inventario_historial_producto'
    ),
    path(
        'movimientos/producto/<int:codigo_id>/entrada/',
        movimiento_entrada_rapida,
        name='inventario_movimiento_entrada_rapida'
    ),
    path(
        'movimientos/producto/<int:codigo_id>/salida/',
        movimiento_salida_rapida,
        name='inventario_movimiento_salida_rapida'
    ),

    # =====================================================
    # INVENTARIO FÍSICO
    # =====================================================
    path('fisico/', inventario_fisico_lista, name='inventario_fisico'),
    path('fisico/nuevo/', inventario_fisico_crear, name='inventario_fisico_crear'),
    path(
        'fisico/<int:inventario_id>/',
        inventario_fisico_detalle,
        name='inventario_fisico_detalle'
    ),
]