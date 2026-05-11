from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importamos las vistas de autenticación
from django.contrib.auth import views as auth_views
# IMPORTANTE: Importamos RedirectView para manejar la raíz
from django.views.generic import RedirectView 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(
        template_name='login.html', 
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),

    # Rutas de tus aplicaciones
    path('', include('ordenes_de_trabajo.urls')),
    
    # 🔥 AQUÍ INCLUIMOS TU APP DE INVENTARIO 🔥
    path('inventario/', include('inventario.urls')), 
]

# Servir archivos multimedia (Fotos y Firmas) durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)