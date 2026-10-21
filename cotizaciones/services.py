"""All purchasing decisions serialize on the request and item, with audit events."""
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, F
from django.utils import timezone
from .models import (SolicitudCotizacion, ItemSolicitudCotizacion, CotizacionProveedor,
                     RecepcionRepuesto, EventoAbastecimiento)


def registrar_evento(solicitud, usuario, accion, datos=None):
    EventoAbastecimiento.objects.create(solicitud=solicitud, usuario=usuario, accion=accion,
        datos={k:str(v) for k,v in (datos or {}).items()})


def bloquear_item(item_id):
    solicitud_id = ItemSolicitudCotizacion.objects.values_list('solicitud_id', flat=True).get(pk=item_id)
    SolicitudCotizacion.objects.select_for_update().get(pk=solicitud_id)
    item = ItemSolicitudCotizacion.objects.select_for_update().select_related('solicitud', 'solicitud__orden').get(pk=item_id)
    if item.solicitud.estado == 'CANCELADA' or item.solicitud.orden.estado == 'ANULADA':
        raise ValidationError('Esta solicitud u orden está cancelada.')
    return item


def validar_revision(obj, esperada):
    if obj.revision != esperada:
        raise ValidationError('El registro cambió en otra ventana. Recarga y revisa antes de guardar.')


def actualizar_solicitud(solicitud):
    items = list(solicitud.items.prefetch_related('recepciones', 'cotizaciones_proveedor'))
    if items and all(i.pendiente_recepcion == 0 for i in items):
        estado = 'RECIBIDA'
    elif any(i.total_recibido for i in items):
        estado = 'PARCIAL'
    elif items and all(i.pedido_en or i.cantidad_bodega == i.cantidad for i in items):
        estado = 'COMPRADA'
    elif items and all(i.cotizacion_elegida or i.cantidad_bodega == i.cantidad for i in items):
        estado = 'DECIDIDA'
    elif CotizacionProveedor.objects.filter(item__solicitud=solicitud).exists():
        estado = 'RESPONDIDA'
    else:
        estado = 'BORRADOR'
    SolicitudCotizacion.objects.filter(pk=solicitud.pk).update(estado=estado, actualizada_en=timezone.now())


@transaction.atomic
def guardar_item(form, solicitud, usuario):
    SolicitudCotizacion.objects.select_for_update().get(pk=solicitud.pk)
    es_nuevo = not form.instance.pk
    if form.instance.pk:
        obj = bloquear_item(form.instance.pk)
        validar_revision(obj, form.cleaned_data['revision_esperada'])
        fields = form._meta.fields
        changed = [k for k in fields if getattr(obj, k) != form.cleaned_data.get(k)]
        if obj.pedido_en and set(changed)-{'observacion'}:
            raise ValidationError('El repuesto ya tiene un pedido. Conserva sus datos y registra otro requerimiento para cambios de compra.')
        if {'cantidad','unidad','medida_solicitada','marca_referencia','cantidad_bodega','medida_confirmada'} & set(changed):
            obj.cotizaciones_proveedor.filter(estado='GANADORA').update(estado='RESPONDIO', revision=F('revision')+1)
            form.instance.estado_abastecimiento = 'PENDIENTE'
        if 'unidad' in changed:
            obj.cotizaciones_proveedor.update(unidades_por_presentacion=None, revision=F('revision')+1)
        form.instance.revision = obj.revision+1
    else:
        form.instance.solicitud = solicitud
        form.instance.orden_item = (solicitud.items.aggregate(n=Max('orden_item'))['n'] or 0)+1
    item = form.save()
    if item.pendiente_recepcion == 0:
        item.estado_abastecimiento = 'RECIBIDO'
        item.save(update_fields=['estado_abastecimiento'])
    registrar_evento(solicitud, usuario, 'Repuesto agregado' if es_nuevo else 'Repuesto actualizado',
                     {'repuesto':item.descripcion_solicitada, 'cantidad':item.cantidad, 'medida':item.medida_solicitada})
    actualizar_solicitud(solicitud)
    return item


@transaction.atomic
def guardar_oferta(form, item_id, usuario):
    item = bloquear_item(item_id)
    oferta = form.instance
    if oferta.pk:
        anterior = CotizacionProveedor.objects.select_for_update().get(pk=oferta.pk, item=item)
        validar_revision(anterior, form.cleaned_data['revision_esperada'])
        if anterior.estado == 'GANADORA' and item.pedido_en:
            raise ValidationError('La opción forma parte de un pedido; conserva el costo acordado y registra una nueva opción.')
        registrar_evento(item.solicitud, usuario, 'Cotización anterior conservada', {
            'repuesto':item.descripcion_solicitada,'proveedor':anterior.proveedor.nombre_final,
            'costo_anterior':anterior.precio,'marca_anterior':anterior.marca_ofertada,
            'medida_anterior':anterior.medida_ofertada,'iva_anterior':anterior.get_tratamiento_iva_display()})
        oferta.revision = anterior.revision+1
    else:
        oferta.numero_opcion = (item.cotizaciones_proveedor.filter(proveedor=oferta.proveedor).aggregate(n=Max('numero_opcion'))['n'] or 0)+1
    oferta.item = item
    if oferta.presentacion and oferta.presentacion == item.unidad:
        oferta.unidades_por_presentacion = 1
    if oferta.estado != 'GANADORA':
        oferta.estado = 'RESPONDIO' if oferta.precio is not None or oferta.disponible is not None else 'PENDIENTE'
    elif oferta.costo_requerimiento is None:
        raise ValidationError('Completa las condiciones de la opción elegida o elige otra antes de modificarla.')
    oferta.fecha_respuesta = timezone.now()
    oferta.save()
    registrar_evento(item.solicitud, usuario, 'Cotización guardada',
        {'repuesto':item.descripcion_solicitada, 'proveedor':oferta.proveedor.nombre_final, 'opcion':oferta.numero_opcion, 'costo':oferta.precio})
    actualizar_solicitud(item.solicitud)
    return oferta


@transaction.atomic
def elegir_oferta(oferta_id, revision, usuario):
    original = CotizacionProveedor.objects.get(pk=oferta_id)
    item = bloquear_item(original.item_id)
    oferta = CotizacionProveedor.objects.select_for_update().select_related('item').get(pk=oferta_id)
    validar_revision(oferta, revision)
    if item.pedido_en:
        raise ValidationError('El repuesto ya tiene un pedido registrado.')
    if oferta.costo_requerimiento is None:
        raise ValidationError('Confirma cantidad, unidad, medida, disponibilidad e IVA antes de elegir esta opción.')
    item.cotizaciones_proveedor.filter(estado='GANADORA').exclude(pk=oferta.pk).update(estado='RESPONDIO', revision=F('revision')+1)
    oferta.estado = 'GANADORA'
    oferta.revision += 1
    oferta.save()
    item.estado_abastecimiento = 'SELECCIONADO'
    item.revision += 1
    item.save()
    registrar_evento(item.solicitud, usuario, 'Proveedor elegido', {'repuesto':item.descripcion_solicitada, 'proveedor':oferta.proveedor.nombre_final})
    actualizar_solicitud(item.solicitud)
    return item


@transaction.atomic
def registrar_pedido(item_id, revision, usuario):
    item = bloquear_item(item_id)
    validar_revision(item, revision)
    if item.pedido_en:
        raise ValidationError('El pedido ya está registrado.')
    oferta = item.cotizacion_elegida
    if not oferta or oferta.costo_requerimiento is None or not item.pendiente_recepcion:
        raise ValidationError('Elige una opción con condiciones confirmadas y cantidad pendiente.')
    item.costo_acordado = oferta.costo_requerimiento
    item.cantidad_pedida = item.cantidad-item.cantidad_bodega
    item.pedido_en = timezone.now()
    item.estado_abastecimiento = 'PEDIDO'
    item.revision += 1
    item.save()
    registrar_evento(item.solicitud, usuario, 'Pedido registrado', {'repuesto':item.descripcion_solicitada, 'cantidad':item.cantidad_pedida, 'costo':item.costo_acordado})
    actualizar_solicitud(item.solicitud)
    return item


@transaction.atomic
def registrar_recepcion(item_id, datos, usuario):
    item = bloquear_item(item_id)
    anterior = RecepcionRepuesto.objects.filter(clave_operacion=datos['clave_operacion']).first()
    if anterior:
        if anterior.item_id != item.pk:
            raise ValidationError('Esta operación pertenece a otro repuesto.')
        return anterior
    oferta = item.cotizacion_elegida
    if not item.pedido_en or not oferta:
        raise ValidationError('Registra primero el pedido del repuesto.')
    cantidad = datos['cantidad']
    if cantidad <= 0 or cantidad > item.pendiente_recepcion:
        raise ValidationError(f'La cantidad debe estar entre 1 y {item.pendiente_recepcion}.')
    recepcion = RecepcionRepuesto(item=item, cotizacion=oferta, recibida_por=usuario,
        cantidad=cantidad, comprobante=datos.get('comprobante',''), observacion=datos.get('observacion',''),
        clave_operacion=datos['clave_operacion'])
    recepcion.full_clean()
    recepcion.save()
    item.estado_abastecimiento = 'RECIBIDO' if item.pendiente_recepcion == 0 else 'PARCIAL'
    item.revision += 1
    item.save()
    registrar_evento(item.solicitud, usuario, 'Recepción registrada', {'repuesto':item.descripcion_solicitada, 'cantidad':cantidad, 'pendiente':item.pendiente_recepcion})
    actualizar_solicitud(item.solicitud)
    return recepcion


@transaction.atomic
def anular_recepcion(recepcion_id, motivo, usuario):
    original = RecepcionRepuesto.objects.get(pk=recepcion_id)
    item = bloquear_item(original.item_id)
    recepcion = RecepcionRepuesto.objects.select_for_update().get(pk=recepcion_id)
    if recepcion.anulada_en:
        return recepcion
    if not motivo.strip():
        raise ValidationError('Indica el motivo de la anulación.')
    recepcion.anulada_en = timezone.now()
    recepcion.anulada_por = usuario
    recepcion.motivo_anulacion = motivo.strip()
    recepcion.save(update_fields=['anulada_en','anulada_por','motivo_anulacion'])
    item.estado_abastecimiento = 'PARCIAL' if item.total_recibido else 'PEDIDO'
    item.revision += 1
    item.save()
    registrar_evento(item.solicitud, usuario, 'Recepción anulada',
        {'repuesto':item.descripcion_solicitada,'cantidad':recepcion.cantidad,'motivo':motivo.strip()})
    actualizar_solicitud(item.solicitud)
    return recepcion
