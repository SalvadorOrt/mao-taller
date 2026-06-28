from django import forms
from .models import Usuario

class UsuarioForm(forms.ModelForm):
    # Campo extra para la contraseña (no es obligatorio al editar, pero sí al crear)
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control-apple', 'placeholder': 'Contraseña secreta'}),
        required=False, 
        label="Contraseña"
    )

    class Meta:
        model = Usuario
        fields = [
            'username', 'first_name', 'last_name', 'email', 
            'cedula', 'rol', 'sucursal', 'puede_cambiar_sucursal'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'email': forms.EmailInput(attrs={'class': 'form-control-apple'}),
            'cedula': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'rol': forms.Select(attrs={'class': 'form-control-apple'}),
            'sucursal': forms.Select(attrs={'class': 'form-control-apple'}),
            'puede_cambiar_sucursal': forms.CheckboxInput(),
        }

    def save(self, commit=True):
        # Obtenemos el usuario sin guardarlo en la BD todavía
        user = super().save(commit=False)
        
        # Si el administrador escribió una contraseña, la encriptamos de forma segura
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
            
        if commit:
            user.save() # ¡Aquí se disparará la magia de tu def save() en el modelo!
            
        return user
    

    from django import forms
from django.forms import modelformset_factory

from .models import Producto, CodigoProducto


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "categoria",
            "nombre_base",
            "descripcion",
            "activo",
            "datos_incompletos",
            "descontinuado",
        ]

        widgets = {
            "categoria": forms.Select(attrs={
                "class": "form-control-apple select2",
                "required": True,
            }),
            "nombre_base": forms.TextInput(attrs={
                "class": "form-control-apple",
                "placeholder": "Ej. Filtro de aceite Toyota Hilux",
                "style": "text-transform:uppercase;",
                "required": True,
            }),
            "descripcion": forms.Textarea(attrs={
                "class": "form-control-apple",
                "placeholder": "Descripción opcional...",
                "style": "min-height:80px;",
            }),
            "activo": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
            "datos_incompletos": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
            "descontinuado": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

        labels = {
            "categoria": "Categoría",
            "nombre_base": "Nombre base del repuesto",
            "descripcion": "Descripción",
            "activo": "Producto activo",
            "datos_incompletos": "Datos incompletos",
            "descontinuado": "Descontinuado",
        }

    def clean_nombre_base(self):
        nombre = self.cleaned_data.get("nombre_base", "")
        return nombre.strip().upper()


class CodigoProductoForm(forms.ModelForm):
    class Meta:
        model = CodigoProducto
        fields = [
            "marca",
            "tipo_codigo",
            "codigo",
            "codigo_barras",
            "nombre_comercial",
            "presentacion_cantidad",
            "presentacion_unidad",
            "precio_compra",
            "precio_venta",
            "margen_ganancia_porcentaje",
            "porcentaje_iva_costo",
            "activo",
        ]

        widgets = {
            "marca": forms.Select(attrs={
                "class": "form-control-apple select2 codigo-marca",
                "required": True,
            }),
            "tipo_codigo": forms.Select(attrs={
                "class": "form-control-apple",
            }),
            "codigo": forms.TextInput(attrs={
                "class": "form-control-apple codigo-input",
                
                "style": "text-transform:uppercase; font-weight:bold;",
                "required": True,
            }),
            "codigo_barras": forms.TextInput(attrs={
                "class": "form-control-apple",
                
            }),
            "nombre_comercial": forms.TextInput(attrs={
                "class": "form-control-apple",
                
            }),
            "presentacion_cantidad": forms.NumberInput(attrs={
                "class": "form-control-apple",
                "step": "0.01",
                "min": "0",
                
            }),
            "presentacion_unidad": forms.TextInput(attrs={
                "class": "form-control-apple",
                
                "style": "text-transform:uppercase;",
            }),
            "precio_compra": forms.NumberInput(attrs={
                "class": "form-control-apple",
                "step": "0.01",
                "min": "0",
                
            }),
            "precio_venta": forms.NumberInput(attrs={
                "class": "form-control-apple",
                "step": "0.01",
                "min": "0",
                
            }),
            "margen_ganancia_porcentaje": forms.NumberInput(attrs={
                "class": "form-control-apple",
                "step": "0.01",
                "min": "0",
                "value": "100.00",
            }),
            "porcentaje_iva_costo": forms.NumberInput(attrs={
                "class": "form-control-apple",
                "step": "0.01",
                "min": "0",
                "value": "0.00",
            }),
            "activo": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

        labels = {
            "marca": "Marca",
            "tipo_codigo": "Tipo de código",
            "codigo": "Código del repuesto",
            "codigo_barras": "Código de barras",
            "nombre_comercial": "Nombre comercial",
            "presentacion_cantidad": "Cantidad presentación",
            "presentacion_unidad": "Unidad",
            "precio_compra": "Precio compra",
            "precio_venta": "Precio venta",
            "margen_ganancia_porcentaje": "Margen %",
            "porcentaje_iva_costo": "IVA costo %",
            "activo": "Código activo para la venta",
        }

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "")
        return codigo.strip().upper()

    def clean_codigo_barras(self):
        codigo_barras = self.cleaned_data.get("codigo_barras", "")
        return codigo_barras.strip() if codigo_barras else None

    def clean_nombre_comercial(self):
        nombre = self.cleaned_data.get("nombre_comercial", "")
        return nombre.strip() if nombre else None

    def clean_presentacion_unidad(self):
        unidad = self.cleaned_data.get("presentacion_unidad", "")
        return unidad.strip().upper() if unidad else None


CodigoProductoFormSet = modelformset_factory(
    CodigoProducto,
    form=CodigoProductoForm,
    extra=1,
    can_delete=True,
)