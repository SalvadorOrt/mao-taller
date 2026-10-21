from django.http import HttpResponse
from django.urls import include, path

def stub(request, *args, **kwargs):
    return HttpResponse('ERP route outside purchasing tests')

urlpatterns=[path('cotizaciones/',include('cotizaciones.urls')),
 path('login/',stub,name='login'),path('logout/',stub,name='logout'),
 path('orden/<int:pk>/',stub,name='detalle_orden')]
# Resolve the existing base menu without importing unrelated billing/PDF routes.
for name in ['dashboard','crear_orden','lista_ordenes','lista_clientes','lista_cotizaciones','crear_cotizacion',
             'inventario_dashboard','inventario_catalogo','inventario_stock','inventario_movimientos','inventario_fisico','lista_usuarios']:
    urlpatterns.append(path('erp/'+name+'/',stub,name=name))
for namespace, names in [('accesos',['roles_lista']),('avaluos',['ordenes_pendientes']),
                         ('facturacion',['dashboard','nueva_factura_manual'])]:
    urlpatterns.append(path(namespace+'/',include(([path(n+'/',stub,name=n) for n in names],namespace))))
