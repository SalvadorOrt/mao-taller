import csv
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_GET
from ordenes_de_trabajo.models import OrdenTrabajo
from inventario.models import Producto, CodigoProducto
from .access import sucursal_activa, solicitudes_visibles, comprobar_operacion
from .models import SolicitudCotizacion, ItemSolicitudCotizacion, CotizacionProveedor, RecepcionRepuesto
from .forms import SolicitudForm, ItemForm, OfertaForm, RecepcionForm, ProveedorForm, AnulacionRecepcionForm
from . import services


def error_form(form, error):
    form.add_error(None, '; '.join(error.messages))


def obtener_item(request, pk):
    return get_object_or_404(ItemSolicitudCotizacion.objects.select_related('solicitud', 'solicitud__orden'),
                            pk=pk, solicitud__in=solicitudes_visibles(request))


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_GET
def lista(request):
    qs = solicitudes_visibles(request).annotate(numero_items=Count('items', distinct=True))
    q = request.GET.get('q','').strip()[:200]
    if q:
        qs = qs.filter(Q(orden__placa__icontains=q)|Q(orden__numero_orden__icontains=q)|Q(orden__vehiculo__icontains=q)|Q(titulo__icontains=q)|Q(items__descripcion_solicitada__icontains=q)).distinct()
    tipo = request.GET.get('tipo','')
    if tipo:
        qs = qs.filter(tipo_trabajo=tipo)
    estado = request.GET.get('estado','')
    if estado:
        qs = qs.filter(estado=estado)
    qs = qs.order_by('-creada_en', '-pk')
    return render(request,'cotizaciones/lista.html',{'pagina':Paginator(qs,25).get_page(request.GET.get('page')),
        'q':q,'tipo':tipo,'estado':estado,'tipos':SolicitudCotizacion._meta.get_field('tipo_trabajo').choices,
        'estados':SolicitudCotizacion.ESTADOS})


@login_required
@permission_required('cotizaciones.add_solicitudcotizacion', raise_exception=True)
def nueva(request):
    branch = sucursal_activa(request)
    form = SolicitudForm(request.POST or None, sucursal=branch, initial={'orden':request.GET.get('orden')})
    order_id = request.POST.get('orden') or request.GET.get('orden') or ''
    order = OrdenTrabajo.objects.filter(pk=int(order_id), sucursal=branch).first() if branch and str(order_id).isdigit() else None
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            obj=form.save(commit=False)
            obj.creada_por=request.user
            obj.sucursal=branch
            obj.save()
            for n, row in enumerate(form.cleaned_data['repuestos'],1):
                ItemSolicitudCotizacion.objects.create(solicitud=obj, orden_item=n, **row)
            services.registrar_evento(obj,request.user,'Solicitud creada',{'titulo':obj.titulo})
        messages.success(request,'Solicitud creada. Agrega los costos de tus proveedores.')
        return redirect('cotizaciones:detalle',pk=obj.pk)
    return render(request,'cotizaciones/form.html',{'form':form,'titulo':'Nueva solicitud de repuestos',
        'es_solicitud':True,'orden_elegida':order,'sucursal_activa':branch,'volver':'cotizaciones:lista'})


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_GET
def buscar_ordenes(request):
    term=request.GET.get('q','').strip()[:100]
    branch=sucursal_activa(request)
    if len(term)<2 or not branch:
        return JsonResponse({'results':[]})
    qs=OrdenTrabajo.objects.filter(sucursal=branch).exclude(estado='ANULADA').filter(
        Q(numero_orden__icontains=term)|Q(placa__icontains=term)|Q(vehiculo__icontains=term)).order_by('-id')[:15]
    return JsonResponse({'results':[{'id':o.pk,'label':f'{o.numero_orden} · {o.placa or "Sin placa"} · {o.vehiculo or ""}'} for o in qs]})


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_GET
def buscar_productos(request):
    term = request.GET.get('q','').strip()[:100]
    if len(term)<2:
        return JsonResponse({'results':[]})
    productos = Producto.objects.filter(activo=True).filter(Q(nombre_base__icontains=term)|Q(sku_interno__icontains=term)).order_by('nombre_base')[:12]
    codigos = CodigoProducto.objects.filter(activo=True,producto__activo=True).select_related('producto','marca').filter(Q(codigo__icontains=term)|Q(codigo_barras__icontains=term)).order_by('codigo')[:12]
    results=[{'producto':p.pk,'codigo':None,'label':f'{p.sku_interno} · {p.nombre_base}',
              'nombre':p.nombre_base,'referencia':''} for p in productos]
    results += [{'producto':c.producto_id,'codigo':c.pk,'label':f'{c.codigo} · {c.marca.nombre} · {c.producto.nombre_base}',
                 'nombre':c.producto.nombre_base,'referencia':c.codigo} for c in codigos]
    return JsonResponse({'results':results})


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_GET
def detalle(request, pk):
    obj=get_object_or_404(solicitudes_visibles(request),pk=pk)
    items=list(obj.items.prefetch_related(Prefetch('cotizaciones_proveedor',
        queryset=CotizacionProveedor.objects.select_related('proveedor').order_by('proveedor__empresa','numero_opcion')), 'recepciones'))
    providers={}
    for item in items:
        for oferta in item.cotizaciones_proveedor.all():
            providers[oferta.proveedor_id]=oferta.proveedor
    providers=sorted(providers.values(),key=lambda p:p.nombre_final)
    rows=[]; total=Decimal('0'); total_pedidos=Decimal('0'); pendientes=0
    for item in items:
        ofertas=list(item.cotizaciones_proveedor.all())
        for oferta in ofertas:
            oferta.item=item
        comparables=[o for o in ofertas if o.costo_requerimiento is not None]
        mejor=min(comparables,key=lambda o:o.costo_requerimiento,default=None)
        elegida=next((o for o in ofertas if o.estado=='GANADORA'),None)
        if elegida and elegida.costo_requerimiento is not None:
            total+=elegida.costo_requerimiento
        total_pedidos+=item.costo_acordado or 0
        pendientes+=item.pendiente_recepcion
        rows.append({'item':item,'elegida':elegida,'mejor':mejor,'recibido':item.total_recibido,
            'pendiente':item.pendiente_recepcion,'celdas':[{'proveedor':p,'ofertas':[o for o in ofertas if o.proveedor_id==p.pk]} for p in providers]})
    return render(request,'cotizaciones/detalle.html',{'solicitud':obj,'filas':rows,'proveedores':providers,
        'total':total,'total_pedidos':total_pedidos,'pendientes':pendientes,
        'eventos':obj.eventos.select_related('usuario')[:40]})


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
def editar_item(request, solicitud_pk=None, pk=None):
    item=obtener_item(request,pk) if pk else None
    solicitud=item.solicitud if item else get_object_or_404(solicitudes_visibles(request),pk=solicitud_pk)
    comprobar_operacion(request,solicitud)
    permiso='cotizaciones.change_itemsolicitudcotizacion' if item else 'cotizaciones.add_itemsolicitudcotizacion'
    if not request.user.has_perm(permiso):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    form=ItemForm(request.POST or None,instance=item or ItemSolicitudCotizacion(solicitud=solicitud))
    if request.method=='POST' and form.is_valid():
        try:
            services.guardar_item(form,solicitud,request.user)
        except ValidationError as exc:
            error_form(form,exc)
        else:
            messages.success(request,'Repuesto guardado.')
            return redirect('cotizaciones:detalle',pk=solicitud.pk)
    return render(request,'cotizaciones/form.html',{'form':form,'titulo':'Editar repuesto' if item else 'Agregar repuesto','solicitud':solicitud,'es_item':True,'item_catalogo':item})


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
def oferta(request, item_pk=None, pk=None):
    obj=get_object_or_404(CotizacionProveedor,pk=pk,item__solicitud__in=solicitudes_visibles(request)) if pk else None
    item=obtener_item(request,obj.item_id if obj else item_pk)
    comprobar_operacion(request,item.solicitud)
    permiso='cotizaciones.change_cotizacionproveedor' if obj else 'cotizaciones.add_cotizacionproveedor'
    if not request.user.has_perm(permiso):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    form=OfertaForm(request.POST or None,instance=obj or CotizacionProveedor(item=item),
        initial={'proveedor':request.GET.get('proveedor')})
    if request.method=='POST' and form.is_valid():
        try:
            services.guardar_oferta(form,item.pk,request.user)
        except ValidationError as exc:
            error_form(form,exc)
        else:
            messages.success(request,'Cotización guardada.')
            return redirect('cotizaciones:detalle',pk=item.solicitud_id)
    return render(request,'cotizaciones/form.html',{'form':form,'titulo':'Registrar costo de proveedor' if not obj else 'Editar cotización',
        'solicitud':item.solicitud,'item':item,'es_oferta':True})


@login_required
@permission_required('cotizaciones.change_cotizacionproveedor', raise_exception=True)
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_POST
def elegir(request, pk):
    obj=get_object_or_404(CotizacionProveedor,pk=pk,item__solicitud__in=solicitudes_visibles(request))
    comprobar_operacion(request,obj.item.solicitud)
    try:
        services.elegir_oferta(obj.pk,int(request.POST.get('revision','0')),request.user)
    except (ValidationError,ValueError) as exc:
        messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Revisión inválida.')
    else:
        messages.success(request,'Proveedor elegido para este repuesto.')
    return redirect('cotizaciones:detalle',pk=obj.item.solicitud_id)


@login_required
@permission_required('cotizaciones.change_itemsolicitudcotizacion', raise_exception=True)
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_POST
def pedir(request, pk):
    item=obtener_item(request,pk)
    comprobar_operacion(request,item.solicitud)
    try:
        services.registrar_pedido(item.pk,int(request.POST.get('revision','0')),request.user)
    except (ValidationError,ValueError) as exc:
        messages.error(request,'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Revisión inválida.')
    else:
        messages.success(request,'Pedido registrado para seguimiento.')
    return redirect('cotizaciones:detalle',pk=item.solicitud_id)


@login_required
@permission_required('cotizaciones.add_recepcionrepuesto', raise_exception=True)
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
def recibir(request, pk):
    item=obtener_item(request,pk)
    comprobar_operacion(request,item.solicitud)
    form=RecepcionForm(request.POST or None,initial={'cantidad':item.pendiente_recepcion})
    if request.method=='POST' and form.is_valid():
        try:
            services.registrar_recepcion(item.pk,form.cleaned_data,request.user)
        except ValidationError as exc:
            error_form(form,exc)
        else:
            messages.success(request,'Recepción guardada y pendiente actualizado.')
            return redirect('cotizaciones:detalle',pk=item.solicitud_id)
    return render(request,'cotizaciones/form.html',{'form':form,'titulo':'Registrar recepción del repuesto',
        'solicitud':item.solicitud,'item':item,'es_recepcion':True})


@login_required
@permission_required('compras.add_proveedor', raise_exception=True)
def nuevo_proveedor(request):
    form=ProveedorForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        form.save()
        messages.success(request,'Proveedor registrado; ya puedes seleccionarlo al cotizar.')
        return redirect('cotizaciones:lista')
    return render(request,'cotizaciones/form.html',{'form':form,'titulo':'Nuevo proveedor','volver':'cotizaciones:lista'})


def celda_csv(value):
    text=str(value if value is not None else '')
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text


@login_required
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
@require_GET
def exportar(request, pk):
    obj=get_object_or_404(solicitudes_visibles(request),pk=pk)
    response=HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition']=f'attachment; filename="cotizaciones-{obj.pk}.csv"'
    response.write('\ufeff')
    writer=csv.writer(response)
    writer.writerow(['OT','Placa','Repuesto','Cantidad requerida','Unidad','Medida','Proveedor','Opción','Marca','Medida ofertada',
        'Costo cotizado USD','Presentación','Unidades cubiertas','IVA','IVA %','Disponible','Entrega','Elegida','Total con IVA USD',
        'Recibido','Pendiente','Observación'])
    for item in obj.items.prefetch_related('cotizaciones_proveedor__proveedor','recepciones'):
        for q in list(item.cotizaciones_proveedor.all()) or [None]:
            if q:
                q.item=item
            writer.writerow([celda_csv(v) for v in [obj.orden.numero_orden,obj.orden.placa,item.descripcion_solicitada,item.cantidad,item.unidad,item.medida_solicitada,
                q.proveedor.nombre_final if q else '',q.numero_opcion if q else '',q.marca_ofertada if q else '',q.medida_ofertada if q else '',q.precio if q else '',q.presentacion if q else '',q.unidades_por_presentacion if q else '',
                q.tratamiento_iva if q else '',q.porcentaje_iva if q else '',('Por confirmar' if q.disponible is None else 'Sí' if q.disponible else 'No') if q else '',q.tiempo_entrega if q else '',
                q.estado=='GANADORA' if q else False,q.costo_requerimiento if q else '',item.total_recibido,item.pendiente_recepcion,q.observacion if q else '']])
    return response


@login_required
@permission_required('cotizaciones.change_recepcionrepuesto', raise_exception=True)
@permission_required('cotizaciones.view_solicitudcotizacion', raise_exception=True)
def anular_recepcion(request, pk):
    obj = get_object_or_404(RecepcionRepuesto, pk=pk, item__solicitud__in=solicitudes_visibles(request))
    comprobar_operacion(request, obj.item.solicitud)
    form = AnulacionRecepcionForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        try:
            services.anular_recepcion(obj.pk, form.cleaned_data['motivo'], request.user)
        except ValidationError as exc:
            error_form(form, exc)
        else:
            messages.success(request, 'Recepción anulada; el registro original se conserva y la cantidad vuelve a pendiente.')
            return redirect('cotizaciones:detalle', pk=obj.item.solicitud_id)
    return render(request, 'cotizaciones/form.html', {'form':form, 'titulo':'Anular recepción',
        'solicitud':obj.item.solicitud, 'item':obj.item})
