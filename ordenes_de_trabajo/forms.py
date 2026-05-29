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
    # Checkbox para forzar la consulta completa
    consultar_full = forms.BooleanField(
        label="Cargar datos completos (Full)", 
        required=False, 
        initial=True
    )

    class Meta:
        model = Cliente
        fields = [
            'tipo_documento', 'identificacion', 'nombre_completo', 
            'telefono', 'email', 'direccion'
        ]
        widgets = {
            'tipo_documento': forms.Select(attrs={'class': 'form-control-apple'}),
            'identificacion': forms.TextInput(attrs={'class': 'form-control-apple', 'placeholder': 'Ej. 1712345678'}),
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'email': forms.EmailInput(attrs={'class': 'form-control-apple'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control-apple', 'rows': 2}),
        }