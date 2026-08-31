from django.urls import path

from . import views
from . import impresion


app_name = "facturacion"


urlpatterns = [
    # ======================================================
    # DASHBOARD
    # ======================================================
    path(
        "",
        views.dashboard_facturacion,
        name="dashboard",
    ),

    # ======================================================
    # CREAR FACTURA DESDE ORDEN DE TRABAJO
    # ======================================================
    path(
        "buscar-ordenes/",
        views.buscar_ordenes_facturacion,
        name="buscar_ordenes_facturacion",
    ),

    path(
        "orden/<int:orden_id>/",
        views.detalle_orden_facturacion,
        name="detalle_orden_facturacion",
    ),

    path(
        "orden/<int:orden_id>/facturar/",
        views.crear_factura_desde_ot,
        name="crear_factura_desde_ot",
    ),

    # ======================================================
    # FACTURA MANUAL / VENTA DIRECTA
    # ======================================================
    path(
        "manual/nueva/",
        views.nueva_factura_manual,
        name="nueva_factura_manual",
    ),

    path(
        "manual/guardar/",
        views.crear_factura_manual,
        name="crear_factura_manual",
    ),

    # ======================================================
    # DETALLE / EDICIÓN DE BORRADOR
    # ======================================================
    path(
        "facturas/<int:factura_id>/",
        views.detalle_factura,
        name="detalle_factura",
    ),

    path(
        "facturas/<int:factura_id>/comprador/",
        views.actualizar_comprador,
        name="actualizar_comprador",
    ),

    path(
        "facturas/<int:factura_id>/pago/",
        views.guardar_forma_pago,
        name="guardar_forma_pago",
    ),

    # ======================================================
    # EMISIÓN SRI
    # ======================================================
    path(
        "facturas/<int:factura_id>/emitir/",
        views.emitir_factura,
        name="emitir_factura",
    ),

    path(
        "facturas/<int:factura_id>/reintentar/",
        views.reintentar_factura,
        name="reintentar_factura",
    ),

    path(
        "facturas/<int:factura_id>/consultar-sri/",
        views.consultar_estado_sri,
        name="consultar_estado_sri",
    ),

    # ======================================================
    # RIDE / FACTURA PARA IMPRIMIR O GUARDAR COMO PDF
    # ======================================================
    path(
        "facturas/<int:factura_id>/ride/",
        impresion.ride_factura,
        name="ride_factura",
    ),

    # ======================================================
    # XML
    # ======================================================
    path(
        "facturas/<int:factura_id>/xml/",
        views.descargar_xml_factura,
        name="descargar_xml_factura",
    ),

    # ======================================================
    # CORREO
    # ======================================================
    path(
        "facturas/<int:factura_id>/correo/",
        views.enviar_factura_correo,
        name="enviar_factura_correo",
    ),

    # ======================================================
    # ANULACIÓN
    # ======================================================
    path(
        "facturas/<int:factura_id>/anular/",
        views.anular_factura,
        name="anular_factura",
    ),
]
