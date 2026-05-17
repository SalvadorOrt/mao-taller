from django.urls import path

# ========================
# IMPORTS MODULARES
# ========================
from .views import ordenes
from .views import api
from .views import impresion
from .views import dashboard

urlpatterns = [

    # ========================
    # Dashboard y Configuración
    # ========================
    path('', dashboard.dashboard_taller, name='inicio'),
    path('dashboard/', dashboard.dashboard_taller, name='dashboard'),
    path(
        'cambiar-sucursal/',
        dashboard.cambiar_sucursal_activa,
        name='cambiar_sucursal_activa'
    ),

    # ========================
    # Órdenes de Trabajo
    # ========================
    path('ordenes/', ordenes.lista_ordenes, name='lista_ordenes'),

    path(
        'vehiculo/nuevo/',
        ordenes.crear_orden,
        name='crear_orden'
    ),

    path(
        'orden/<int:pk>/',
        ordenes.detalle_orden,
        name='detalle_orden'
    ),

    path(
        'orden/<int:pk>/cerrar/',
        ordenes.cerrar_orden,
        name='cerrar_orden'
    ),

    path(
        'orden/<int:pk>/anular/',
        ordenes.anular_orden,
        name='anular_orden'
    ),

    path(
        'orden/<int:pk>/reabrir/',
        ordenes.reabrir_orden,
        name='reabrir_orden'
    ),

    path(
        'orden/<int:pk>/editar-recepcion/',
        ordenes.editar_recepcion_orden,
        name='editar_recepcion_orden'
    ),
    path(
        'orden/<int:pk>/editar-vehiculo/',
        ordenes.editar_vehiculo_ot,
        name='editar_vehiculo_ot'
    ),
    # ========================
    # Cotizaciones / Proformas
    # ========================
    path(
        'cotizacion/nueva/',
        ordenes.crear_cotizacion,
        name='crear_cotizacion'
    ),

    path(
        'orden/<int:pk_orden>/cotizar/',
        ordenes.nueva_cotizacion_desde_ot,
        name='nueva_cotizacion_desde_ot'
    ),

    path(
        'cotizacion/<int:pk>/detalle/',
        ordenes.detalle_cotizacion,
        name='detalle_cotizacion'
    ),

    path(
        'cotizacion/<int:pk>/aprobar/',
        ordenes.aprobar_cotizacion,
        name='aprobar_cotizacion'
    ),

    path(
        'cotizacion/<int:pk>/imprimir/',
        impresion.imprimir_cotizacion,
        name='imprimir_cotizacion'
    ),

    # ========================
    # Impresión
    # ========================
    path(
        'orden/<int:pk>/imprimir/',
        impresion.imprimir_tecnico,
        name='imprimir_tecnico'
    ),

    path(
        'orden/<int:pk>/imprimir-resumen/',
        impresion.imprimir_resumen_orden,
        name='imprimir_resumen'
    ),

    # ========================
    # Historial y Expedientes
    # ========================
    path(
        'historial/',
        ordenes.historial_vehiculos,
        name='historial_vehiculos'
    ),

    path(
        'expediente/<int:pk>/',
        ordenes.detalle_expediente,
        name='detalle_expediente'
    ),

    # ========================
    # APIs AJAX
    # ========================

    #  CONSULTA PLACA (CACHE-ASIDE)
    path(
        'api/regcheck/',
        api.consultar_regcheck,
        name='api_regcheck'
    ),

    #  CONSULTA CÉDULA / RUC (CACHE-ASIDE)
    path(
        'api/consultar_cedula/',
        api.consultar_cedula_api,
        name='api_cedula'
    ),

    # ========================
    # APIs BÚSQUEDA
    # ========================
    path(
        'api/buscar-repuestos/',
        api.api_buscar_repuestos_ot,
        name='api_buscar_repuestos'
    ),

    path(
        'api/buscar-servicios-ot/',
        api.api_buscar_servicios_ot,
        name='api_buscar_servicios_ot'
    ),
]