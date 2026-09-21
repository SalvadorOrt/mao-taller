from django.urls import path

from . import views


app_name = "asistencia"


urlpatterns = [
    # =====================================================
    # MARCACIÓN ONLINE
    # =====================================================

    path(
        "api/marcar/",
        views.api_marcar_asistencia,
        name="api_marcar_asistencia",
    ),

    # =====================================================
    # SINCRONIZACIÓN OFFLINE
    # =====================================================

    path(
        "api/sincronizar/",
        views.api_sincronizar_marcacion,
        name="api_sincronizar_marcacion",
    ),

    # =====================================================
    # ACTUALIZACIÓN DE CACHÉ DE TERMINAL
    # =====================================================

    path(
        "api/cache/",
        views.api_cache_terminal,
        name="api_cache_terminal",
    ),
]