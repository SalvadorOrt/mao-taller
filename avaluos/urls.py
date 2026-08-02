from django.urls import path

from .views import avaluos


app_name = "avaluos"


urlpatterns = [
    # ==========================================================
    # ÓRDENES ABIERTAS PENDIENTES
    # ==========================================================
    path(
        "",
        avaluos.ordenes_pendientes,
        name="ordenes_pendientes",
    ),

    # ==========================================================
    # INICIAR AVALÚO DESDE UNA OT
    # ==========================================================
    path(
        "orden/<int:orden_id>/iniciar/",
        avaluos.iniciar_avaluo,
        name="iniciar_avaluo",
    ),

    # ==========================================================
    # DETALLE DEL AVALÚO
    # ==========================================================
    path(
        "<int:pk>/",
        avaluos.detalle_avaluo,
        name="detalle_avaluo",
    ),
]