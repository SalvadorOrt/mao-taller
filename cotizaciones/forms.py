import uuid
from django import forms
from django.core.exceptions import ValidationError
from ordenes_de_trabajo.models import OrdenTrabajo
from compras.models import Proveedor
from .models import SolicitudCotizacion, ItemSolicitudCotizacion, CotizacionProveedor


class EstiloForm:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif not field.widget.is_hidden:
                field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 3


class SolicitudForm(EstiloForm, forms.ModelForm):
    repuestos = forms.CharField(required=False, widget=forms.Textarea, label='Lista inicial de repuestos',
        help_text='Una línea por repuesto: descripción; cantidad; unidad; medida. Ejemplo: Bomba de agua; 1; UNIDAD. Revisa las cantidades antes de guardar.')

    class Meta:
        model = SolicitudCotizacion
        fields = ['orden', 'titulo', 'tipo_trabajo', 'urgente', 'observacion']
        widgets = {'orden': forms.HiddenInput()}
        labels = {'titulo':'Título del trabajo', 'observacion':'Observaciones'}

    def __init__(self, *args, sucursal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['orden'].queryset = OrdenTrabajo.objects.filter(sucursal=sucursal).exclude(estado='ANULADA') if sucursal else OrdenTrabajo.objects.none()

    def clean_repuestos(self):
        value = self.cleaned_data.get('repuestos', '')
        rows = []
        for n, line in enumerate(value.splitlines(), 1):
            if not line.strip():
                continue
            cells = [v.strip() for v in line.split(';')]
            if len(cells) > 4 or not cells[0]:
                raise ValidationError(f'Línea {n}: usa descripción; cantidad; unidad; medida.')
            try:
                quantity = int(cells[1]) if len(cells) > 1 and cells[1] else 1
            except ValueError:
                raise ValidationError(f'Línea {n}: cantidad inválida.')
            unit = cells[2].upper() if len(cells) > 2 else ''
            if quantity < 1 or unit not in dict(ItemSolicitudCotizacion._meta.get_field('unidad').choices):
                raise ValidationError(f'Línea {n}: revisa cantidad y unidad (UNIDAD, PAR, JUEGO o KIT).')
            if len(cells[0]) > 255 or (len(cells)>3 and len(cells[3])>100):
                raise ValidationError(f'Línea {n}: descripción o medida demasiado larga.')
            rows.append({'descripcion_solicitada':cells[0], 'cantidad':quantity, 'unidad':unit,
                         'medida_solicitada':cells[3] if len(cells)>3 else ''})
        if len(rows) > 200:
            raise ValidationError('Agrega hasta 200 repuestos a la vez.')
        return rows


class ItemForm(EstiloForm, forms.ModelForm):
    revision_esperada = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = ItemSolicitudCotizacion
        fields = ['producto_rel', 'codigo_producto_rel', 'descripcion_solicitada', 'codigo_referencia', 'cantidad', 'unidad',
                  'marca_referencia', 'categoria_referencia', 'medida_solicitada',
                  'medida_confirmada', 'cantidad_bodega', 'observacion']
        widgets = {'producto_rel':forms.HiddenInput(), 'codigo_producto_rel':forms.HiddenInput()}
        labels = {'cantidad_bodega':'Cantidad cubierta desde bodega', 'unidad':'Unidad requerida',
                  'medida_solicitada':'Medida / especificación exacta', 'medida_confirmada':'Medida confirmada por el técnico',
                  'categoria_referencia':'Sistema (motor, refrigeración, suspensión…)', 'observacion':'Observaciones'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revision_esperada'].initial = self.instance.revision

    def clean(self):
        data = super().clean()
        producto = data.get('producto_rel')
        codigo = data.get('codigo_producto_rel')
        if codigo and (not producto or codigo.producto_id != producto.pk):
            raise ValidationError('El código seleccionado no pertenece al producto del catálogo.')
        return data


class OfertaForm(EstiloForm, forms.ModelForm):
    revision_esperada = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = CotizacionProveedor
        fields = ['proveedor', 'marca_ofertada', 'medida_ofertada', 'precio', 'presentacion',
                  'unidades_por_presentacion', 'tratamiento_iva', 'porcentaje_iva', 'disponible',
                  'tiempo_entrega', 'contenido', 'observacion']
        labels = {'precio':'Costo por presentación (USD)', 'presentacion':'Presentación cotizada',
                  'unidades_por_presentacion':'Unidades requeridas que cubre cada presentación',
                  'tratamiento_iva':'IVA', 'contenido':'Piezas incluidas', 'observacion':'Observaciones / texto original',
                  'disponible':'Disponibilidad confirmada'}
        help_texts = {'unidades_por_presentacion':'Ejemplo: solicitas unidades y cotizan un par: escribe 2. Para juegos o kits confirma su contenido.',
                      'medida_ofertada':'Conserva STD, +20, 40 o la especificación exacta. No se convierten medidas automáticamente.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)
        if self.instance.pk:
            self.fields['proveedor'].queryset = Proveedor.objects.filter(pk=self.instance.proveedor_id)
            self.fields['proveedor'].disabled = True
        self.fields['revision_esperada'].initial = self.instance.revision
        self.fields['disponible'].widget = forms.Select(choices=[('','Por confirmar'),('true','Disponible'),('false','No disponible')], attrs={'class':'form-select'})
        self.fields['disponible'] = forms.TypedChoiceField(choices=[('','Por confirmar'),('true','Disponible'),('false','No disponible')],
            coerce=lambda v: {'true':True,'false':False}.get(str(v).lower()), empty_value=None, required=False,
            label='Disponibilidad confirmada', widget=self.fields['disponible'].widget)
        self.initial['disponible'] = '' if self.instance.disponible is None else str(self.instance.disponible).lower()


class RecepcionForm(EstiloForm, forms.Form):
    cantidad = forms.IntegerField(min_value=1, label='Cantidad recibida (en la unidad requerida)')
    comprobante = forms.CharField(max_length=100, required=False)
    observacion = forms.CharField(required=False, widget=forms.Textarea, max_length=5000)
    clave_operacion = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)


class ProveedorForm(EstiloForm, forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['empresa', 'nombre_contacto', 'ciudad', 'telefono', 'whatsapp', 'email', 'ruc']


class AnulacionRecepcionForm(EstiloForm, forms.Form):
    motivo = forms.CharField(label='Motivo de la anulación', max_length=2000, widget=forms.Textarea)
