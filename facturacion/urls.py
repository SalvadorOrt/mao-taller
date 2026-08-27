from django.urls import path

from . import views


app_name = "facturacion"


urlpatterns = [

    path(
        "",
        views.dashboard_facturacion,
        name="dashboard",
    ),

    path(
        "orden/<int:orden_id>/facturar/",
        views.crear_factura_desde_ot,
        name="crear_factura_desde_ot",
    ),

    path(
        "facturas/<int:factura_id>/",
        views.detalle_factura,
        name="detalle_factura",
    ),
]