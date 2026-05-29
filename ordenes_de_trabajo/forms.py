from django import forms
from .models import OrdenTrabajo

# forms.py
from django import forms
from .models import Cliente

# ==========================================
# 1. FORMULARIO DE CABECERA (RECEPCIÓN DEL VEHÍCULO)
# ==========================================
class OrdenTrabajoForm(forms.ModelForm):
    class Meta:
        model = OrdenTrabajo
        # Solo los campos que el asesor de servicio llena al recibir el auto
        fields = [
            'placa',
            'vehiculo',
            'color',
            'anio_vehiculo',
            'kilometraje',
            'nivel_combustible',
            'sintomas_cliente',
            'observaciones_recepcion',
            'observaciones_tecnicas'
        ]
        
        # Inyectamos tus clases CSS estilo Apple
        widgets = {
            'placa': forms.TextInput(attrs={'class': 'form-control-apple', 'placeholder': 'Ej. ABC-1234'}),
            'vehiculo': forms.TextInput(attrs={'class': 'form-control-apple', 'placeholder': 'Ej. VOLKSWAGEN GOLF'}),
            'color': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'anio_vehiculo': forms.NumberInput(attrs={'class': 'form-control-apple', 'min': '1900'}),
            'kilometraje': forms.NumberInput(attrs={'class': 'form-control-apple', 'min': '0'}),
            'nivel_combustible': forms.Select(attrs={'class': 'form-select-apple'}),
            'sintomas_cliente': forms.Textarea(attrs={'class': 'form-control-apple', 'rows': 2}),
            'observaciones_recepcion': forms.Textarea(attrs={'class': 'form-control-apple', 'rows': 2}),
            'observaciones_tecnicas': forms.Textarea(attrs={'class': 'form-control-apple', 'rows': 2}),
        }
from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    consultar_full = forms.BooleanField(
        label="Cargar datos completos (Full)",
        required=False,
        initial=True
    )

    class Meta:
        model = Cliente
        fields = [
            "tipo_documento",
            "identificacion",
            "nombre_completo",

            "telefono",
            "telefono_secundario",
            "telefono_trabajo",
            "email",
            "direccion",

            "genero",
            "sexo",
            "estado_civil",
            "conyuge",
            "nacionalidad",
            "fecha_nacimiento",
            "fecha_cedulacion",
            "lugar_nacimiento",
            "instruccion",
            "profesion",
            "tipo_sangre",

            "nombre_madre",
            "nombre_padre",

            "lugar_domicilio",
            "calle_domicilio",
            "numeracion_domicilio",
            "provincia",
            "canton",
            "parroquia",
            "otras_direcciones",

            "licencia_tipo",
            "licencia_fecha_desde",
            "licencia_fecha_hasta",
            "licencia_puntos",
            "licencia_restricciones",
            "licencia_todos",

            "carnet_conadis",
            "discapacidad",
            "porcentaje_discapacidad",

            "razon_social",
            "estado_contribuyente_ruc",
            "tipo_contribuyente",
            "regimen",
            "categoria",
            "obligado_llevar_contabilidad",
            "agente_retencion",
            "contribuyente_especial",
            "contribuyente_fantasma",
            "transacciones_inexistentes",
            "actividad_economica_principal",
            "representantes_legales",
            "establecimientos",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for nombre, field in self.fields.items():
            field.widget.attrs.update({
                "class": "form-control-apple"
            })

        if "identificacion" in self.fields:
            self.fields["identificacion"].widget.attrs.update({
                "placeholder": "Ej. 1712345678"
            })

        campos_textarea = [
            "direccion",
            "otras_direcciones",
            "licencia_restricciones",
            "licencia_todos",
            "representantes_legales",
            "establecimientos",
        ]

        for campo in campos_textarea:
            if campo in self.fields:
                self.fields[campo].widget = forms.Textarea(attrs={
                    "class": "form-control-apple",
                    "rows": 2
                })