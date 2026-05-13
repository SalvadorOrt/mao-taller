from django.urls import path
from . import views

urlpatterns = [
    # ========================
    # Dashboard y Configuración
    # ========================
    path('', views.dashboard_taller, name='inicio'),
    path('dashboard/', views.dashboard_taller, name='dashboard'),
    path('cambiar-sucursal/', views.cambiar_sucursal_activa, name='cambiar_sucursal_activa'),

    # ========================
    # Órdenes de Trabajo
    # ========================
    path('ordenes/', views.lista_ordenes, name='lista_ordenes'),
    path('vehiculo/nuevo/', views.crear_orden, name='crear_orden'),
    path('orden/<int:pk>/', views.detalle_orden, name='detalle_orden'),
    path('orden/<int:pk>/cerrar/', views.cerrar_orden, name='cerrar_orden'),
    path('orden/<int:pk>/anular/', views.anular_orden, name='anular_orden'),
    path('orden/<int:pk>/reabrir/', views.reabrir_orden, name='reabrir_orden'),
    path('orden/<int:pk>/editar-recepcion/', views.editar_recepcion_orden, name='editar_recepcion_orden'),

    # ========================
    # Cotizaciones / Proformas
    # ========================
    path('cotizacion/nueva/', views.crear_cotizacion, name='crear_cotizacion'),
    path('cotizacion/<int:pk>/convertir/', views.convertir_cotizacion_a_orden, name='convertir_cotizacion_a_orden'),

    # ========================
    # Impresión
    # ========================
    path('orden/<int:pk>/imprimir/', views.imprimir_tecnico, name='imprimir_tecnico'),
    path('orden/<int:pk>/imprimir-resumen/', views.imprimir_resumen_orden, name='imprimir_resumen'),
    
    # ========================
    # Historial y Expedientes
    # ========================
    path('historial/', views.historial_vehiculos, name='historial_vehiculos'),
    path('expediente/<int:pk>/', views.detalle_expediente, name='detalle_expediente'),

    # ========================
    # APIs Conexiones Externas
    # ========================
    path('api/regcheck/', views.consultar_regcheck, name='api_regcheck'),
    path('api/consultar_cedula/', views.consultar_cedula_api, name='api_cedula'),
    path('api/buscar-repuestos/', views.api_buscar_repuestos_ot, name='api_buscar_repuestos'),
    path('api/buscar-servicios-ot/', views.api_buscar_servicios_ot, name='api_buscar_servicios_ot'),
]