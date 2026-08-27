from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView


urlpatterns = [
    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),

    path(
        "logout/",
        auth_views.LogoutView.as_view(
            next_page="login",
        ),
        name="logout",
    ),

    # =====================================================
    # RAÍZ DEL SISTEMA
    # =====================================================

    path(
        "",
        RedirectView.as_view(
            url="/dashboard/",
            permanent=False,
        ),
    ),

    # =====================================================
    # ACCESOS
    # =====================================================

    path(
        "accesos/",
        include("accesos.urls"),
    ),

    # =====================================================
    # ÓRDENES DE TRABAJO
    # =====================================================

    path(
        "",
        include("ordenes_de_trabajo.urls"),
    ),

    # =====================================================
    # AVALÚOS
    # =====================================================

    path(
        "avaluos/",
        include("avaluos.urls"),
    ),

    # =====================================================
    # INVENTARIO
    # =====================================================

    path(
        "inventario/",
        include("inventario.urls"),
    ),

    # =====================================================
    # FACTURACIÓN
    # =====================================================

    path(
        "facturacion/",
        include("facturacion.urls"),
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )