from django.urls import path

from .views import torre

app_name = "cotizaciones"

urlpatterns = [
    path("", torre.lista, name="lista"),
    path("sucursal/", torre.cambiar_sucursal, name="cambiar_sucursal"),
    path("codigos-producto/", torre.codigos_producto, name="codigos_producto"),
    path("solicitudes/nueva/", torre.solicitud_nueva, name="solicitud_nueva"),
    path("solicitudes/<int:pk>/", torre.detalle, name="detalle"),
    path("solicitudes/<int:pk>/editar/", torre.solicitud_editar, name="solicitud_editar"),
    path("solicitudes/<int:solicitud_pk>/repuestos/nuevo/", torre.item_nuevo, name="item_nuevo"),
    path("repuestos/<int:pk>/editar/", torre.item_editar, name="item_editar"),
    path("repuestos/<int:pk>/comprado/", torre.item_comprado, name="item_comprado"),
    path("repuestos/<int:item_pk>/ofertas/nueva/", torre.oferta_nueva, name="oferta_nueva"),
    path("repuestos/<int:item_pk>/fotos/nueva/", torre.foto_nueva, name="foto_nueva"),
    path("ofertas/<int:pk>/editar/", torre.oferta_editar, name="oferta_editar"),
    path("ofertas/<int:pk>/seleccionar/", torre.oferta_seleccionar, name="oferta_seleccionar"),
    path("fotos/<int:pk>/", torre.foto, name="foto"),
]
