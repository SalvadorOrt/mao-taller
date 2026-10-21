from django.urls import path
from . import views
app_name='cotizaciones'
urlpatterns=[
 path('',views.lista,name='lista'), path('nueva/',views.nueva,name='nueva'),
 path('ordenes/buscar/',views.buscar_ordenes,name='buscar_ordenes'),
 path('productos/buscar/',views.buscar_productos,name='buscar_productos'),
 path('proveedores/nuevo/',views.nuevo_proveedor,name='nuevo_proveedor'),
 path('<int:pk>/',views.detalle,name='detalle'), path('<int:pk>/exportar/',views.exportar,name='exportar'),
 path('<int:solicitud_pk>/repuestos/nuevo/',views.editar_item,name='item_nuevo'),
 path('repuestos/<int:pk>/editar/',views.editar_item,name='item_editar'),
 path('repuestos/<int:item_pk>/cotizar/',views.oferta,name='oferta_nueva'),
 path('ofertas/<int:pk>/editar/',views.oferta,name='oferta_editar'),
 path('ofertas/<int:pk>/elegir/',views.elegir,name='elegir'),
 path('repuestos/<int:pk>/pedir/',views.pedir,name='pedir'),
 path('recepciones/<int:pk>/anular/',views.anular_recepcion,name='anular_recepcion'),
 path('repuestos/<int:pk>/recibir/',views.recibir,name='recibir'),
]
