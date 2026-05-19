from django.urls import path
#  AGREGA 'clientes' a esta línea de importación:
from .views import ordenes, api, impresion, dashboard, clientes

urlpatterns = [

    # Dashboard
    path('', dashboard.dashboard_taller, name='inicio'),
    path('dashboard/', dashboard.dashboard_taller, name='dashboard'),
    path('cambiar-sucursal/', dashboard.cambiar_sucursal_activa, name='cambiar_sucursal_activa'),

    # Órdenes
    path('ordenes/', ordenes.lista_ordenes, name='lista_ordenes'),
    path('vehiculo/nuevo/', ordenes.crear_orden, name='crear_orden'),
    path('orden/<int:pk>/', ordenes.detalle_orden, name='detalle_orden'),
    path('orden/<int:pk>/cerrar/', ordenes.cerrar_orden, name='cerrar_orden'),
    path('orden/<int:pk>/anular/', ordenes.anular_orden, name='anular_orden'),
    path('orden/<int:pk>/reabrir/', ordenes.reabrir_orden, name='reabrir_orden'),
    path('orden/<int:pk>/editar-recepcion/', ordenes.editar_recepcion_orden, name='editar_recepcion_orden'),

    # Cotizaciones
    path('cotizacion/nueva/', ordenes.crear_cotizacion, name='crear_cotizacion'),
    path('orden/<int:pk_orden>/cotizar/', ordenes.nueva_cotizacion_desde_ot, name='nueva_cotizacion_desde_ot'),
    path('cotizacion/<int:pk>/detalle/', ordenes.detalle_cotizacion, name='detalle_cotizacion'),
    path('cotizacion/<int:pk>/aprobar/', ordenes.aprobar_cotizacion, name='aprobar_cotizacion'),
    path('cotizacion/<int:pk>/imprimir/', impresion.imprimir_cotizacion, name='imprimir_cotizacion'),

    # Impresión
    path('orden/<int:pk>/imprimir/', impresion.imprimir_tecnico, name='imprimir_tecnico'),
    path('orden/<int:pk>/imprimir-resumen/', impresion.imprimir_resumen_orden, name='imprimir_resumen'),

    # Historial
    path('historial/', ordenes.historial_vehiculos, name='historial_vehiculos'),
    path('expediente/<int:pk>/', ordenes.detalle_expediente, name='detalle_expediente'),

    #  NUEVO: Módulo de Clientes
    path('clientes/', clientes.lista_clientes, name='lista_clientes'),
    # APIs
    path('api/regcheck/', api.consultar_regcheck, name='api_regcheck'),
    path('api/buscar-placa/', api.buscar_vehiculo_por_placa, name='api_buscar_placa'),
    path('api/consultar_cedula/', api.consultar_cedula_api, name='api_cedula'),
    path('api/buscar-repuestos/', api.api_buscar_repuestos_ot, name='api_buscar_repuestos'),
    path('api/buscar-servicios-ot/', api.api_buscar_servicios_ot, name='api_buscar_servicios_ot'),
]