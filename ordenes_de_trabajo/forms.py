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
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'identificacion', 
            'tipo_documento', 
            'nombre_completo',
            'telefono', 
            'telefono_secundario', 
            'telefono_trabajo',
            'email', 
            'direccion', 
            'lugar_domicilio', 
            'provincia', 
            'canton'
        ]
        
        widgets = {
            'identificacion': forms.TextInput(attrs={
                'class': 'form-control-apple', 
                'placeholder': 'Ej. 1712345678'
            }),
            'nombre_completo': forms.TextInput(attrs={
                'class': 'form-control-apple', 
                'placeholder': 'Nombres y Apellidos / Empresa'
            }),
            'telefono': forms.TextInput(attrs={
                'class': 'form-control-apple', 
                'placeholder': 'Ej. 0991234567'
            }),
            'telefono_secundario': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'telefono_trabajo': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'email': forms.EmailInput(attrs={
                'class': 'form-control-apple', 
                'placeholder': 'ejemplo@correo.com'
            }),
            'direccion': forms.Textarea(attrs={
                'class': 'form-control-apple', 
                'rows': 3, 
                'placeholder': 'Dirección detallada'
            }),
            'lugar_domicilio': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'provincia': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'canton': forms.TextInput(attrs={'class': 'form-control-apple'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-control-apple'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Estilo para campos solo lectura (estética Apple)
        estilo_bloqueado = 'background-color: #f5f5f7; cursor: not-allowed; color: #86868b; border: 1px solid #d2d2d7;'
        
        # Si estamos EDITANDO un cliente que ya existe...
        if self.instance and self.instance.pk:
            # Lista de campos que no deben ser editados manualmente
            campos_bloqueados = [
                'identificacion', 
                'tipo_documento', 
                'nombre_completo'
            ]
            
            for campo in campos_bloqueados:
                if campo in self.fields:
                    # Usamos readonly en lugar de disabled para permitir el envío del dato
                    self.fields[campo].widget.attrs['readonly'] = 'readonly'
                    self.fields[campo].widget.attrs['style'] = estilo_bloqueado
                    
            # Si el tipo_documento es select, también lo bloqueamos visualmente
            if 'tipo_documento' in self.fields:
                self.fields['tipo_documento'].widget.attrs['disabled'] = 'disabled'

    def clean_identificacion(self):
        # Impedimos que el valor sea alterado si el campo es readonly
        return self.instance.identificacion if self.instance.pk else self.cleaned_data.get('identificacion')

    def clean_nombre_completo(self):
        return self.instance.nombre_completo if self.instance.pk else self.cleaned_data.get('nombre_completo')