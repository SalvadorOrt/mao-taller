from django.urls import path

from . import views

app_name = "cotizaciones"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("sucursal/", views.cambiar_sucursal, name="cambiar_sucursal"),
    path("codigos-producto/", views.codigos_producto, name="codigos_producto"),
    path("solicitudes/nueva/", views.solicitud_nueva, name="solicitud_nueva"),
    path("solicitudes/<int:pk>/", views.detalle, name="detalle"),
    path("solicitudes/<int:pk>/editar/", views.solicitud_editar, name="solicitud_editar"),
    path("solicitudes/<int:solicitud_pk>/repuestos/nuevo/", views.item_nuevo, name="item_nuevo"),
    path("repuestos/<int:pk>/editar/", views.item_editar, name="item_editar"),
    path("repuestos/<int:pk>/comprado/", views.item_comprado, name="item_comprado"),
    path("repuestos/<int:item_pk>/ofertas/nueva/", views.oferta_nueva, name="oferta_nueva"),
    path("repuestos/<int:item_pk>/fotos/nueva/", views.foto_nueva, name="foto_nueva"),
    path("ofertas/<int:pk>/editar/", views.oferta_editar, name="oferta_editar"),
    path("ofertas/<int:pk>/seleccionar/", views.oferta_seleccionar, name="oferta_seleccionar"),
    path("fotos/<int:pk>/", views.foto, name="foto"),
]
