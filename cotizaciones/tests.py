import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from ordenes_de_trabajo.models import OrdenTrabajo, Sucursal
from compras.models import Proveedor
from .models import SolicitudCotizacion, ItemSolicitudCotizacion, CotizacionProveedor, RecepcionRepuesto
from .forms import OfertaForm, ItemForm, SolicitudForm
from . import services


class TorreControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.norte=Sucursal.objects.create(nombre='QA Norte',codigo='QA-N')
        cls.sur=Sucursal.objects.create(nombre='QA Sur',codigo='QA-S')
        cls.usuario=get_user_model().objects.create_superuser(username='control',password='test-only',sucursal=cls.norte)
        cls.orden=OrdenTrabajo.objects.create(numero_orden='QA-001',sucursal=cls.norte,placa='PAA1234',vehiculo='Vehículo de pruebas')
        cls.solicitud=SolicitudCotizacion.objects.create(orden=cls.orden,sucursal=cls.norte,creada_por=cls.usuario,titulo='Reparación de motor',tipo_trabajo='MOTOR')
        cls.proveedor=Proveedor.objects.create(nombre_contacto='Contacto QA',empresa='Proveedor QA')

    def setUp(self):
        self.client.force_login(self.usuario)
        self.item=ItemSolicitudCotizacion.objects.create(solicitud=self.solicitud,descripcion_solicitada='Amortiguadores',cantidad=2,unidad='UNIDAD')

    def cotizacion(self, **kwargs):
        data=dict(item=self.item,proveedor=self.proveedor,precio=Decimal('60'),disponible=True,
            presentacion='PAR',unidades_por_presentacion=2,tratamiento_iva='INCLUIDO')
        data.update(kwargs)
        return CotizacionProveedor.objects.create(**data)

    def pedido(self):
        q=self.cotizacion()
        services.elegir_oferta(q.pk,q.revision,self.usuario)
        self.item.refresh_from_db()
        services.registrar_pedido(self.item.pk,self.item.revision,self.usuario)
        self.item.refresh_from_db()
        return q

    def test_par_cubre_dos_piezas_sin_duplicar_costo(self):
        q=self.cotizacion()
        self.assertEqual(q.costo_requerimiento,Decimal('60.00'))
        self.item.cantidad=3;self.item.save();q.item=self.item
        self.assertEqual(q.costo_requerimiento,Decimal('120.00'))

    def test_iva_se_redondea_en_el_total_de_linea(self):
        q=self.cotizacion(precio=Decimal('.03'),presentacion='UNIDAD',unidades_por_presentacion=1,tratamiento_iva='ADICIONAL',porcentaje_iva=Decimal('15'))
        self.assertEqual(q.costo_requerimiento,Decimal('.07'))

    def test_condiciones_desconocidas_no_se_comparan(self):
        for changes in [{'disponible':None},{'tratamiento_iva':''},{'unidades_por_presentacion':None},{'disponible':False},{'presentacion':''}]:
            q=self.cotizacion(**changes)
            self.assertIsNone(q.costo_requerimiento)
            with self.assertRaises(ValidationError):services.elegir_oferta(q.pk,q.revision,self.usuario)
            q.delete()

    def test_medida_requerida_debe_coincidir_y_estar_confirmada(self):
        self.item.medida_solicitada='+20';self.item.medida_confirmada=True;self.item.save()
        q=self.cotizacion(medida_ofertada='STD')
        self.assertIsNone(q.costo_requerimiento)
        q.medida_ofertada='+20';q.save()
        self.assertEqual(q.costo_requerimiento,Decimal('60'))
        self.item.medida_confirmada=False;q.item=self.item
        self.assertIsNone(q.costo_requerimiento)

    def test_un_proveedor_puede_ofrecer_varias_marcas(self):
        self.cotizacion(marca_ofertada='Marca A')
        self.cotizacion(numero_opcion=2,marca_ofertada='Marca B',precio=Decimal('75'))
        self.assertEqual(self.item.cotizaciones_proveedor.count(),2)

    def test_cambiar_eleccion_deja_una_sola_ganadora(self):
        a=self.cotizacion();b=self.cotizacion(numero_opcion=2,precio=Decimal('72'))
        services.elegir_oferta(a.pk,a.revision,self.usuario)
        services.elegir_oferta(b.pk,b.revision,self.usuario)
        self.assertEqual(self.item.cotizaciones_proveedor.filter(estado='GANADORA').get().pk,b.pk)
        with self.assertRaises(IntegrityError),transaction.atomic():
            CotizacionProveedor.objects.filter(pk=a.pk).update(estado='GANADORA')

    def test_revision_antigua_no_cambia_la_seleccion(self):
        q=self.cotizacion();services.elegir_oferta(q.pk,q.revision,self.usuario)
        with self.assertRaises(ValidationError):services.elegir_oferta(q.pk,q.revision,self.usuario)

    def test_pedido_conserva_cantidad_y_costo_acordado(self):
        self.pedido()
        self.assertEqual(self.item.cantidad_pedida,2)
        self.assertEqual(self.item.costo_acordado,Decimal('60'))
        self.assertIsNotNone(self.item.pedido_en)

    def test_recepciones_parciales_y_reintento_no_duplican(self):
        self.pedido();datos={'cantidad':1,'clave_operacion':uuid.uuid4()}
        a=services.registrar_recepcion(self.item.pk,datos,self.usuario)
        b=services.registrar_recepcion(self.item.pk,datos,self.usuario)
        self.assertEqual(a.pk,b.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.total_recibido,1);self.assertEqual(self.item.pendiente_recepcion,1)
        self.assertEqual(self.item.estado_abastecimiento,'PARCIAL')
        services.registrar_recepcion(self.item.pk,{'cantidad':1,'clave_operacion':uuid.uuid4()},self.usuario)
        self.item.refresh_from_db();self.solicitud.refresh_from_db()
        self.assertEqual(self.item.estado_abastecimiento,'RECIBIDO')
        self.assertEqual(self.solicitud.estado,'RECIBIDA')
        self.assertEqual(self.item.costo_acordado,Decimal('60'))

    def test_no_recibe_mas_de_lo_pendiente(self):
        self.pedido()
        with self.assertRaises(ValidationError):
            services.registrar_recepcion(self.item.pk,{'cantidad':3,'clave_operacion':uuid.uuid4()},self.usuario)
        self.assertFalse(RecepcionRepuesto.objects.exists())

    def test_no_recibe_sin_pedido(self):
        with self.assertRaises(ValidationError):
            services.registrar_recepcion(self.item.pk,{'cantidad':1,'clave_operacion':uuid.uuid4()},self.usuario)

    def test_bodega_reduce_la_compra_sin_confundir_stock_general(self):
        self.item.cantidad=4;self.item.cantidad_bodega=2;self.item.stock_actual_sucursal=10;self.item.save()
        q=self.cotizacion()
        self.assertEqual(q.costo_requerimiento,Decimal('60'))
        self.assertEqual(self.item.pendiente_recepcion,2)

    def test_formulario_no_admite_costo_negativo(self):
        data={'proveedor':self.proveedor.pk,'precio':'-10','disponible':'true','presentacion':'UNIDAD','tratamiento_iva':'INCLUIDO'}
        form=OfertaForm(data,instance=CotizacionProveedor(item=self.item))
        self.assertFalse(form.is_valid());self.assertIn('precio',form.errors)

    def test_formulario_registra_opciones_y_normaliza_presentacion_igual(self):
        self.cotizacion()
        form=OfertaForm({'proveedor':self.proveedor.pk,'precio':'40','disponible':'true',
            'presentacion':'UNIDAD','tratamiento_iva':'INCLUIDO','marca_ofertada':'Otra marca'},instance=CotizacionProveedor(item=self.item))
        self.assertTrue(form.is_valid(),form.errors)
        q=services.guardar_oferta(form,self.item.pk,self.usuario)
        self.assertEqual(q.numero_opcion,2);self.assertEqual(q.unidades_por_presentacion,1)
        self.assertEqual(q.costo_requerimiento,Decimal('80'))

    def test_no_sobrescribe_costo_de_un_pedido(self):
        q=self.pedido();q.refresh_from_db()
        data={'proveedor':self.proveedor.pk,'precio':'90','disponible':'true','presentacion':'PAR',
            'unidades_por_presentacion':2,'tratamiento_iva':'INCLUIDO','revision_esperada':q.revision}
        form=OfertaForm(data,instance=q);self.assertTrue(form.is_valid(),form.errors)
        with self.assertRaises(ValidationError):services.guardar_oferta(form,self.item.pk,self.usuario)
        q.refresh_from_db();self.assertEqual(q.precio,Decimal('60'))

    def test_pagina_comparativo_y_formularios_renderizan(self):
        self.cotizacion()
        for url in [reverse('cotizaciones:lista'),reverse('cotizaciones:detalle',args=[self.solicitud.pk]),
            reverse('cotizaciones:nueva'),reverse('cotizaciones:item_nuevo',args=[self.solicitud.pk]),
            reverse('cotizaciones:item_editar',args=[self.item.pk]),reverse('cotizaciones:oferta_nueva',args=[self.item.pk]),
            reverse('cotizaciones:nuevo_proveedor')]:
            response=self.client.get(url);self.assertEqual(response.status_code,200,(url,response.content[:300]))
        response=self.client.get(reverse('cotizaciones:detalle',args=[self.solicitud.pk]))
        self.assertContains(response,'Menor total comparable');self.assertContains(response,'Proveedor elegido',count=0)

    def test_busqueda_de_ordenes_y_creacion_con_lista(self):
        search=self.client.get(reverse('cotizaciones:buscar_ordenes'),{'q':'PAA'})
        self.assertEqual(search.json()['results'][0]['id'],self.orden.pk)
        response=self.client.post(reverse('cotizaciones:nueva'),{'orden':self.orden.pk,'titulo':'Nueva compra',
            'tipo_trabajo':'MOTOR','repuestos':'Pistones; 1; JUEGO; STD\nBomba de agua; 1; UNIDAD'})
        self.assertEqual(response.status_code,302)
        s=SolicitudCotizacion.objects.get(titulo='Nueva compra')
        self.assertEqual(s.items.count(),2)
        self.assertEqual(s.items.get(descripcion_solicitada='Pistones').medida_solicitada,'STD')

    def test_celda_exportada_no_ejecuta_formulas_y_conserva_unicode(self):
        self.item.descripcion_solicitada='=HYPERLINK("x")';self.item.save();self.cotizacion()
        response=self.client.get(reverse('cotizaciones:exportar',args=[self.solicitud.pk]))
        self.assertEqual(response.status_code,200)
        self.assertIn("'=HYPERLINK",response.content.decode())
        self.assertIn('Opción',response.content.decode())

    def test_usuario_sin_permisos_no_puede_operar(self):
        user=get_user_model().objects.create_user(username='sin-permisos',password='test-only',sucursal=self.norte)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('cotizaciones:lista')).status_code,403)
        self.assertEqual(self.client.post(reverse('cotizaciones:nueva'),{}).status_code,403)

    def test_permiso_de_lectura_no_permite_elegir_ni_crear(self):
        user=get_user_model().objects.create_user(username='lector',password='test-only',sucursal=self.norte)
        user.user_permissions.add(Permission.objects.get(codename='view_solicitudcotizacion',content_type__app_label='cotizaciones'))
        self.client.force_login(user);q=self.cotizacion()
        self.assertEqual(self.client.get(reverse('cotizaciones:lista')).status_code,200)
        self.assertEqual(self.client.post(reverse('cotizaciones:elegir',args=[q.pk]),{'revision':q.revision}).status_code,403)

    def test_sucursal_restringe_consulta_y_operacion(self):
        otra=OrdenTrabajo.objects.create(numero_orden='QA-002',sucursal=self.sur,placa='PBB2345',vehiculo='Otro vehículo')
        s=SolicitudCotizacion.objects.create(orden=otra,sucursal=self.sur,creada_por=self.usuario,titulo='Sucursal sur')
        # An admin may read all branches, but must operate in the active one.
        self.assertEqual(self.client.get(reverse('cotizaciones:item_nuevo',args=[s.pk])).status_code,403)
        user=get_user_model().objects.create_user(username='lector-norte',password='test-only',sucursal=self.norte)
        user.user_permissions.add(Permission.objects.get(codename='view_solicitudcotizacion',content_type__app_label='cotizaciones'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('cotizaciones:detalle',args=[s.pk])).status_code,404)

    def test_acciones_exigen_post_y_csrf(self):
        q=self.cotizacion()
        self.assertEqual(self.client.get(reverse('cotizaciones:elegir',args=[q.pk])).status_code,405)
        client=Client(enforce_csrf_checks=True);client.force_login(self.usuario)
        self.assertEqual(client.post(reverse('cotizaciones:elegir',args=[q.pk]),{'revision':q.revision}).status_code,403)

    def test_orden_invalida_en_formulario_no_produce_error_500(self):
        response=self.client.post(reverse('cotizaciones:nueva'),{'orden':'texto','titulo':'Solicitud','tipo_trabajo':'MOTOR'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'errorlist')

    def test_edicion_con_revision_antigua_no_sobrescribe_datos(self):
        data={'descripcion_solicitada':'Cambio','cantidad':2,'unidad':'UNIDAD','cantidad_bodega':0,'revision_esperada':0}
        form=ItemForm(data,instance=self.item);self.assertTrue(form.is_valid(),form.errors)
        with self.assertRaises(ValidationError):services.guardar_item(form,self.solicitud,self.usuario)
        self.item.refresh_from_db();self.assertEqual(self.item.descripcion_solicitada,'Amortiguadores')

    def test_cambio_de_unidad_exige_reconfirmar_conversion(self):
        q=self.cotizacion();services.elegir_oferta(q.pk,q.revision,self.usuario)
        self.item.refresh_from_db()
        data={'descripcion_solicitada':self.item.descripcion_solicitada,'cantidad':1,'unidad':'PAR','cantidad_bodega':0,'revision_esperada':self.item.revision}
        form=ItemForm(data,instance=self.item);self.assertTrue(form.is_valid(),form.errors)
        services.guardar_item(form,self.solicitud,self.usuario)
        q.refresh_from_db();self.assertIsNone(q.unidades_por_presentacion)
        self.assertEqual(q.estado,'RESPONDIO')
        self.assertIsNone(q.costo_requerimiento)

    def test_la_solicitud_cancelada_no_admite_decisiones(self):
        q=self.cotizacion()
        SolicitudCotizacion.objects.filter(pk=self.solicitud.pk).update(estado='CANCELADA')
        with self.assertRaises(ValidationError):services.elegir_oferta(q.pk,q.revision,self.usuario)

    def test_lista_inicial_invalida_no_crea_solicitud_parcial(self):
        response=self.client.post(reverse('cotizaciones:nueva'),{'orden':self.orden.pk,'titulo':'No crear','tipo_trabajo':'MOTOR','repuestos':'Pieza; texto; UNIDAD'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(SolicitudCotizacion.objects.filter(titulo='No crear').exists())

    def test_anulacion_conserva_historial_y_reabre_pendiente(self):
        self.pedido()
        r=services.registrar_recepcion(self.item.pk,{'cantidad':2,'clave_operacion':uuid.uuid4()},self.usuario)
        services.anular_recepcion(r.pk,'Cantidad ingresada por error',self.usuario)
        self.item.refresh_from_db();r.refresh_from_db()
        self.assertIsNotNone(r.anulada_en);self.assertEqual(r.anulada_por_id,self.usuario.pk)
        self.assertEqual(self.item.pendiente_recepcion,2);self.assertEqual(self.item.estado_abastecimiento,'PEDIDO')
        self.assertTrue(self.solicitud.eventos.filter(accion='Recepción anulada').exists())

    def test_anulacion_exige_motivo(self):
        self.pedido();r=services.registrar_recepcion(self.item.pk,{'cantidad':1,'clave_operacion':uuid.uuid4()},self.usuario)
        with self.assertRaises(ValidationError):services.anular_recepcion(r.pk,'',self.usuario)
        self.assertIsNone(RecepcionRepuesto.objects.get(pk=r.pk).anulada_en)

    def test_costo_anterior_permanece_en_historial(self):
        q=self.cotizacion()
        form=OfertaForm({'proveedor':self.proveedor.pk,'precio':'75','disponible':'true','presentacion':'PAR',
            'unidades_por_presentacion':2,'tratamiento_iva':'INCLUIDO','revision_esperada':q.revision},instance=q)
        self.assertTrue(form.is_valid(),form.errors)
        services.guardar_oferta(form,self.item.pk,self.usuario)
        event=self.solicitud.eventos.get(accion='Cotización anterior conservada')
        self.assertEqual(event.datos['costo_anterior'],'60.00')
        self.assertContains(self.client.get(reverse('cotizaciones:detalle',args=[self.solicitud.pk])),'Costo anterior: $60.00')

    def test_exportacion_incluye_repuestos_sin_cotizar(self):
        response=self.client.get(reverse('cotizaciones:exportar',args=[self.solicitud.pk]))
        self.assertContains(response,'Amortiguadores')

    def test_catalogo_se_vincula_sin_duplicar_productos(self):
        from inventario.models import Producto, Categoria
        categoria=Categoria.objects.create(nombre='QA',prefijo_sku='QA')
        producto=Producto.objects.create(nombre_base='Pieza catálogo QA',categoria=categoria,sku_interno='QA-SKU')
        result=self.client.get(reverse('cotizaciones:buscar_productos'),{'q':'QA-SKU'}).json()['results']
        self.assertEqual(result[0]['producto'],producto.pk)
        data={'producto_rel':producto.pk,'descripcion_solicitada':'Pieza catálogo QA','cantidad':1,'unidad':'UNIDAD','cantidad_bodega':0}
        form=ItemForm(data,instance=ItemSolicitudCotizacion(solicitud=self.solicitud))
        self.assertTrue(form.is_valid(),form.errors)
        item=services.guardar_item(form,self.solicitud,self.usuario)
        self.assertEqual(item.producto_rel_id,producto.pk)
        self.assertEqual(Producto.objects.filter(pk=producto.pk).count(),1)


from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionTorreControlTests(TransactionTestCase):
    anterior=('cotizaciones','0002_alter_cotizacionproveedor_calidad_referencial_and_more')

    def preparar_anterior(self):
        executor=MigrationExecutor(connection)
        executor.migrate([self.anterior])
        apps=executor.loader.project_state([self.anterior]).apps
        branch=Sucursal.objects.create(nombre='QA Migración',codigo='QA-M')
        usuario=get_user_model().objects.create_superuser(username='migracion',password='test-only',sucursal=branch)
        orden=OrdenTrabajo.objects.create(numero_orden='QA-MIG',sucursal=branch,placa='PCC3456',vehiculo='QA')
        proveedor=Proveedor.objects.create(nombre_contacto='QA Migración')
        S=apps.get_model('cotizaciones','SolicitudCotizacion')
        I=apps.get_model('cotizaciones','ItemSolicitudCotizacion')
        C=apps.get_model('cotizaciones','CotizacionProveedor')
        s=S.objects.create(orden_id=orden.pk,sucursal_id=branch.pk,creada_por_id=usuario.pk,titulo='Solicitud histórica')
        i=I.objects.create(solicitud_id=s.pk,descripcion_solicitada='Pieza histórica',cantidad=2)
        q=C.objects.create(item_id=i.pk,proveedor_id=proveedor.pk,precio=Decimal('45.70'),estado='GANADORA')
        return apps,i.pk,q.pk

    def restaurar(self):
        executor=MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_migracion_conserva_solicitudes_precios_y_seleccion(self):
        try:
            apps,item_id,quote_id=self.preparar_anterior()
            self.restaurar()
            quote=CotizacionProveedor.objects.get(pk=quote_id)
            self.assertEqual(quote.precio,Decimal('45.70'))
            self.assertEqual(quote.estado,'GANADORA')
            self.assertEqual(quote.item.cantidad,2)
            self.assertEqual(quote.item.descripcion_solicitada,'Pieza histórica')
            self.assertEqual(quote.tratamiento_iva,'')
            self.assertIsNone(quote.costo_requerimiento)
        finally:
            self.restaurar()

    def test_migracion_detecta_dos_ganadoras_sin_elegir_por_el_usuario(self):
        extra_id=None;C=None
        try:
            apps,item_id,quote_id=self.preparar_anterior()
            C=apps.get_model('cotizaciones','CotizacionProveedor')
            proveedor=Proveedor.objects.create(nombre_contacto='Segundo QA')
            extra_id=C.objects.create(item_id=item_id,proveedor_id=proveedor.pk,precio=Decimal('44'),estado='GANADORA').pk
            with self.assertRaisesRegex(RuntimeError,'varias cotizaciones ganadoras'):
                self.restaurar()
            self.assertEqual(C.objects.filter(item_id=item_id,estado='GANADORA').count(),2)
        finally:
            if extra_id and C:
                C.objects.filter(pk=extra_id).delete()
            self.restaurar()
