from django.urls import path

from .views import (
    crear,
    detalle,
    listado,
)


app_name = "avaluos"


urlpatterns = [
    # ==========================================================
    # ÓRDENES PENDIENTES
    # ==========================================================
    path(
        "",
        listado.ordenes_pendientes,
        name="ordenes_pendientes",
    ),

    # ==========================================================
    # INICIAR AVALÚO DESDE UNA OT
    # ==========================================================
    path(
        "orden/<int:orden_id>/iniciar/",
        crear.iniciar_avaluo,
        name="iniciar_avaluo",
    ),

    # ==========================================================
    # DETALLE DEL AVALÚO
    # ==========================================================
    path(
        "<int:pk>/",
        detalle.detalle_avaluo,
        name="detalle_avaluo",
    ),
]