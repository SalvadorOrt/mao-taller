from django.urls import path

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

    # =====================================================
    # API INTELIGENTE DEL CATÁLOGO
    # =====================================================

    # -----------------------------------------------------
    # MOTOR DE SUGERENCIAS
    # -----------------------------------------------------

    path(
        "catalogo/api/sugerir/",
        catalogo.catalogo_sugerir_producto,
        name="inventario_catalogo_sugerir",
    ),

    # -----------------------------------------------------
    # FAMILIA -> CATEGORÍAS
    # -----------------------------------------------------

    path(
        "catalogo/api/familia/<int:familia_id>/categorias/",
        catalogo.catalogo_categorias_familia,
        name="inventario_catalogo_categorias_familia",
    ),

    # -----------------------------------------------------
    # CATEGORÍA -> ATRIBUTOS
    # -----------------------------------------------------

    path(
        "catalogo/api/categoria/<int:categoria_id>/atributos/",
        catalogo.catalogo_atributos_categoria,
        name="inventario_catalogo_atributos_categoria",
    ),

    # =====================================================
    # PRODUCTO / CÓDIGO
    # =====================================================

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
    # CATEGORÍAS
    # =====================================================

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

    # Se conserva por compatibilidad.
    # NO se mostrará en Nuevo repuesto.
    path(
        "maestros/categorias/crear-rapida/",
        maestros.categoria_crear_rapida,
        name="categoria_crear_rapida",
    ),

    # =====================================================
    # MARCAS
    # =====================================================

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

    # =====================================================
    # ATRIBUTOS
    # =====================================================

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

    # Se conserva por compatibilidad.
    # NO se mostrará en Nuevo repuesto.
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

    # Alias necesario porque fisico.py utiliza
    # redirect("inventario_fisico_lista")
    path(
        "fisico/",
        fisico.inventario_fisico_lista,
        name="inventario_fisico_lista",
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

    # -----------------------------------------------------
    # GENERAR LÍNEAS DEL CONTEO
    # -----------------------------------------------------

    path(
        "fisico/<int:inventario_id>/generar-detalles/",
        fisico.inventario_fisico_generar_detalles,
        name="inventario_fisico_generar_detalles",
    ),

    # -----------------------------------------------------
    # AGREGAR / ESCANEAR PRODUCTO
    # -----------------------------------------------------

    path(
        "fisico/<int:inventario_id>/agregar-linea/",
        fisico.inventario_fisico_agregar_linea,
        name="inventario_fisico_agregar_linea",
    ),

    # -----------------------------------------------------
    # ACTUALIZAR CONTEO
    # -----------------------------------------------------

    path(
        "fisico/detalle/<int:detalle_id>/actualizar/",
        fisico.inventario_fisico_actualizar_conteo,
        name="inventario_fisico_actualizar_conteo",
    ),

    # -----------------------------------------------------
    # CERRAR INVENTARIO
    # -----------------------------------------------------

    path(
        "fisico/<int:inventario_id>/cerrar/",
        fisico.inventario_fisico_cerrar,
        name="inventario_fisico_cerrar",
    ),

    # -----------------------------------------------------
    # APLICAR AJUSTES
    # -----------------------------------------------------

    path(
        "fisico/<int:inventario_id>/aplicar-ajustes/",
        fisico.inventario_fisico_aplicar_ajustes,
        name="inventario_fisico_aplicar_ajustes",
    ),
]