from django.urls import path

from . import views


app_name = "accesos"


urlpatterns = [
    path(
        "roles/",
        views.roles_lista,
        name="roles_lista",
    ),

    path(
        "roles/nuevo/",
        views.rol_crear,
        name="rol_crear",
    ),

    path(
        "roles/<int:pk>/editar/",
        views.rol_editar,
        name="rol_editar",
    ),

    path(
        "roles/<int:pk>/eliminar/",
        views.rol_eliminar,
        name="rol_eliminar",
    ),
]