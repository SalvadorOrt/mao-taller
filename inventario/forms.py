from django import forms
from django.forms import modelformset_factory
from accesos.models import Rol
from .models import (
    Atributo,
    Categoria,
    CodigoProducto,
    ImagenProducto,
    MarcaRepuesto,
    Producto,
    Usuario,
    ValorAtributoProducto,
)


# =========================================================
# USUARIOS
# =========================================================

class UsuarioForm(forms.ModelForm):

    password = forms.CharField(
        required=False,
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control-apple",
                "placeholder": "Contraseña secreta",
            }
        ),
    )

    groups = forms.ModelMultipleChoiceField(
        queryset=Rol.objects.none(),
        required=False,
        label="Roles",
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = Usuario

        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "cedula",
            "sucursal",
            "groups",
        ]

        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control-apple",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control-apple",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control-apple",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control-apple",
                }
            ),
            "cedula": forms.TextInput(
                attrs={
                    "class": "form-control-apple",
                }
            ),
            "sucursal": forms.Select(
                attrs={
                    "class": "form-control-apple",
                }
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.fields["groups"].queryset = (
            Rol.objects
            .all()
            .order_by("name")
        )

    def save(
        self,
        commit=True,
    ):
        user = super().save(
            commit=False
        )

        password = self.cleaned_data.get(
            "password"
        )

        if password:
            user.set_password(
                password
            )

        if commit:
            user.save()
            self.save_m2m()

        return user
# =========================================================
# PRODUCTO
# =========================================================

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
                "class": "form-control-apple select2 searchable-select",
            }),
            "nombre_base": forms.TextInput(attrs={
                "class": "form-control-apple",
                "style": "text-transform:uppercase;",
            }),
            "descripcion": forms.Textarea(attrs={
                "class": "form-control-apple",
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
            "nombre_base": "Nombre base",
            "descripcion": "Descripción",
            "activo": "Activo",
            "datos_incompletos": "Datos incompletos",
            "descontinuado": "Descontinuado",
        }

    def clean_nombre_base(self):
        nombre = self.cleaned_data.get("nombre_base", "")
        return nombre.strip().upper()

    def clean_descripcion(self):
        descripcion = self.cleaned_data.get("descripcion")

        if descripcion:
            return descripcion.strip()

        return None


# =========================================================
# CÓDIGO / REFERENCIA COMERCIAL
# =========================================================

class CodigoProductoForm(forms.ModelForm):

    precio_secreto = forms.CharField(
        required=False,
        disabled=True,
        label="Precio secreto",
        widget=forms.TextInput(attrs={
            "class": "form-control-apple precio-secreto-input",
            "readonly": "readonly",
        }),
    )

    margen_ganancia_porcentaje = forms.DecimalField(
        initial="100.00",
        required=False,
        max_digits=6,
        decimal_places=2,
        label="Margen %",
        widget=forms.NumberInput(attrs={
            "class": "form-control-apple",
            "step": "0.01",
            "min": "0",
        }),
    )

    porcentaje_iva_costo = forms.DecimalField(
        initial="0.00",
        required=False,
        max_digits=5,
        decimal_places=2,
        label="IVA costo %",
        widget=forms.NumberInput(attrs={
            "class": "form-control-apple",
            "step": "0.01",
            "min": "0",
        }),
    )

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
            "precio_secreto",
            "margen_ganancia_porcentaje",
            "porcentaje_iva_costo",
            "activo",
        ]

        widgets = {
            "marca": forms.Select(attrs={
                "class": "form-control-apple select2 codigo-marca",
            }),
            "tipo_codigo": forms.Select(attrs={
                "class": "form-control-apple",
            }),
            "codigo": forms.TextInput(attrs={
                "class": "form-control-apple codigo-input",
                "style": "text-transform:uppercase; font-weight:bold;",
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
                "class": "form-control-apple precio-venta-input",
                "step": "0.01",
                "min": "0",
            }),
            "activo": forms.CheckboxInput(attrs={
                "class": "form-check-input",
            }),
        }

        labels = {
            "marca": "Marca",
            "tipo_codigo": "Tipo",
            "codigo": "Código",
            "codigo_barras": "Barras",
            "nombre_comercial": "Nombre comercial",
            "presentacion_cantidad": "Cantidad",
            "presentacion_unidad": "Unidad",
            "precio_compra": "Compra",
            "precio_venta": "Venta",
            "activo": "Activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["precio_secreto"].initial = "---"

        if self.instance and self.instance.pk:
            self.fields["precio_secreto"].initial = (
                self.instance.precio_secreto
            )

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo", "")
        return codigo.strip().upper()

    def clean_codigo_barras(self):
        codigo = self.cleaned_data.get("codigo_barras", "")
        return codigo.strip() if codigo else None

    def clean_nombre_comercial(self):
        nombre = self.cleaned_data.get("nombre_comercial", "")
        return nombre.strip() if nombre else None

    def clean_presentacion_unidad(self):
        unidad = self.cleaned_data.get("presentacion_unidad", "")
        return unidad.strip().upper() if unidad else None


# =========================================================
# ATRIBUTOS TÉCNICOS
# =========================================================

class ValorAtributoProductoForm(forms.ModelForm):

    # El valor es opcional dentro del formulario.
    #
    # Esto permite que el motor sugiera:
    #
    # ROSCA
    # ALTURA
    # DIÁMETRO
    #
    # y el usuario complete solamente los que conozca.
    #
    # La vista únicamente guardará las filas que tengan:
    #
    # atributo + valor
    #
    valor = forms.CharField(
        required=False,
        label="Valor",
        widget=forms.TextInput(attrs={
            "class": "form-control-apple",
        }),
    )

    class Meta:
        model = ValorAtributoProducto

        fields = [
            "atributo",
            "valor",
        ]

        widgets = {
            "atributo": forms.Select(attrs={
                "class": "form-control-apple select2 atributo-select",
            }),
        }

        labels = {
            "atributo": "Atributo",
            "valor": "Valor",
        }

    def clean_valor(self):
        valor = self.cleaned_data.get("valor", "")
        return valor.strip() if valor else ""


# =========================================================
# CATEGORÍAS
# =========================================================

class CategoriaForm(forms.ModelForm):

    class Meta:
        model = Categoria

        fields = [
            "nombre",
            "prefijo_sku",
        ]

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control-apple",
            }),
            "prefijo_sku": forms.TextInput(attrs={
                "class": "form-control-apple",
                "style": "text-transform:uppercase;",
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip().upper()

        existe = (
            Categoria.objects
            .filter(nombre__iexact=nombre)
            .exclude(pk=self.instance.pk)
            .exists()
        )

        if existe:
            raise forms.ValidationError(
                "Ya existe una categoría con ese nombre."
            )

        return nombre

    def clean_prefijo_sku(self):
        prefijo = self.cleaned_data.get("prefijo_sku", "")
        return prefijo.strip().upper()


# =========================================================
# MARCAS
# =========================================================

class MarcaRepuestoForm(forms.ModelForm):

    class Meta:
        model = MarcaRepuesto

        fields = [
            "nombre",
        ]

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control-apple",
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip().upper()

        existe = (
            MarcaRepuesto.objects
            .filter(nombre__iexact=nombre)
            .exclude(pk=self.instance.pk)
            .exists()
        )

        if existe:
            raise forms.ValidationError(
                "La marca ya existe."
            )

        return nombre


# =========================================================
# ATRIBUTOS MAESTROS
# =========================================================

class AtributoForm(forms.ModelForm):

    class Meta:
        model = Atributo

        fields = [
            "nombre",
            "unidad",
        ]

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": "form-control-apple",
            }),
            "unidad": forms.TextInput(attrs={
                "class": "form-control-apple",
                "style": "text-transform:uppercase;",
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get("nombre", "")
        return nombre.strip().upper()

    def clean_unidad(self):
        unidad = self.cleaned_data.get("unidad")

        if unidad:
            return unidad.strip().upper()

        return None


# =========================================================
# IMÁGENES
# =========================================================

class ImagenProductoForm(forms.ModelForm):

    class Meta:
        model = ImagenProducto

        fields = [
            "imagen",
            "descripcion",
        ]

        widgets = {
            "imagen": forms.ClearableFileInput(attrs={
                "class": "form-control-apple",
                "accept": "image/*",
            }),
            "descripcion": forms.TextInput(attrs={
                "class": "form-control-apple",
            }),
        }

        labels = {
            "imagen": "Imagen",
            "descripcion": "Descripción",
        }

    def clean_descripcion(self):
        descripcion = self.cleaned_data.get("descripcion", "")

        if descripcion:
            return descripcion.strip()

        return None


# =========================================================
# FORMSETS
# =========================================================

CodigoProductoFormSet = modelformset_factory(
    CodigoProducto,
    form=CodigoProductoForm,
    extra=1,
    can_delete=True,
)


ValorAtributoProductoFormSet = modelformset_factory(
    ValorAtributoProducto,
    form=ValorAtributoProductoForm,
    extra=1,
    can_delete=True,
)