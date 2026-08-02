from django.urls import path

from .views import (
    crear,
    detalle,
    listado,
)


app_name = "avaluos"


urlpatterns = [

    # ==========================================================
    # ÓRDENES PENDIENTES DE AVALÚO
    # ==========================================================
    path(
        "",
        listado.ordenes_pendientes,
        name="ordenes_pendientes",
    ),

    # ==========================================================
    # INICIAR AVALÚO DESDE UNA ORDEN DE TRABAJO
    # ==========================================================
    path(
        "orden/<int:orden_id>/iniciar/",
        crear.iniciar_avaluo,
        name="iniciar_avaluo",
    ),

    # ==========================================================
    # DETALLE DEL AVALÚO
    # Abre el Paso 1 por defecto
    # ==========================================================
    path(
        "<int:pk>/",
        detalle.detalle_avaluo,
        name="detalle_avaluo",
    ),

    # ==========================================================
    # DETALLE DEL AVALÚO POR PASOS
    # ==========================================================
    path(
        "<int:pk>/paso/<int:paso>/",
        detalle.detalle_avaluo,
        name="detalle_avaluo_paso",
    ),

    # ==========================================================
    # FOTOGRAFÍAS
    # ==========================================================
    path(
        "foto/<int:foto_id>/eliminar/",
        detalle.eliminar_foto_avaluo,
        name="eliminar_foto_avaluo",
    ),
]