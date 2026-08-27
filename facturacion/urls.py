from django.urls import path

from . import views


app_name = "facturacion"


urlpatterns = [

    # =====================================================
    # DASHBOARD
    # =====================================================

    path(
        "",
        views.dashboard_facturacion,
        name="dashboard",
    ),


    # =====================================================
    # CREAR FACTURA DESDE OT
    # =====================================================

    path(
        "orden/<int:orden_id>/facturar/",
        views.crear_factura_desde_ot,
        name="crear_factura_desde_ot",
    ),


    # =====================================================
    # DETALLE DE FACTURA
    # =====================================================

    path(
        "facturas/<int:factura_id>/",
        views.detalle_factura,
        name="detalle_factura",
    ),


    # =====================================================
    # ACTUALIZAR COMPRADOR
    # =====================================================

    path(
        "facturas/<int:factura_id>/comprador/",
        views.actualizar_comprador,
        name="actualizar_comprador",
    ),


    # =====================================================
    # FORMA DE PAGO
    # =====================================================

    path(
        "facturas/<int:factura_id>/pago/",
        views.guardar_forma_pago,
        name="guardar_forma_pago",
    ),


    # =====================================================
    # EMITIR
    # =====================================================

    path(
        "facturas/<int:factura_id>/emitir/",
        views.emitir_factura,
        name="emitir_factura",
    ),
]