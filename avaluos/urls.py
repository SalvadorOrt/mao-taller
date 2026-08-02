from django.urls import path

from .views import avaluos

app_name = "avaluos"

urlpatterns = [
    path(
        "",
        avaluos.ordenes_pendientes,
        name="ordenes_pendientes",
    ),
]