from django.urls import path
from . import views

urlpatterns = [

    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    path('usuarios/nuevo/', views.gestionar_usuario, name='crear_usuario'),
    path('usuarios/editar/<int:pk>/', views.gestionar_usuario, name='editar_usuario'),
]