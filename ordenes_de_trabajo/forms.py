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
        # Puedes usar '__all__' para traer todos, o especificar los que quieres que el usuario llene.
        # En este caso, dejaremos fuera campos de control interno o JSON complejos.
        fields = [
            'identificacion', 'tipo_documento', 'nombre_completo',
            'telefono', 'telefono_secundario', 'telefono_trabajo',
            'email', 'direccion', 'lugar_domicilio', 'provincia', 'canton'
        ]
        
        # Opcional: Personalizar cómo se ven los campos
        widgets = {
            'identificacion': forms.TextInput(attrs={'class': 'form-control-apple', 'placeholder': 'Ej. 1712345678'}),
            'nombre_completo': forms.TextInput(attrs={'class': 'form-control-apple', 'placeholder': 'Nombres y Apellidos / Empresa'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control-apple', 'placeholder': 'Ej. 0991234567'}),
            'email': forms.EmailInput(attrs={'class': 'form-control-apple', 'placeholder': 'ejemplo@correo.com'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control-apple', 'rows': 3, 'placeholder': 'Dirección detallada'}),
            'tipo_documento': forms.Select(attrs={'class': 'form-control-apple'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si estamos EDITANDO un cliente que ya existe...
        if self.instance and self.instance.pk:
            
            # 1. Campos que NUNCA se editan
            campos_bloqueados = ['identificacion', 'tipo_documento']
            
            # 2. Campos del SRI que solo se actualizan vía API (si los incluyes en tu form)
            campos_sri = [
                'razon_social', 'estado_contribuyente_ruc', 'tipo_contribuyente', 
                'regimen', 'obligado_llevar_contabilidad'
            ]
            
            # Unimos las listas de campos a bloquear
            todos_bloqueados = campos_bloqueados + campos_sri
            
            estilo_bloqueado = 'background-color: #f5f5f7; cursor: not-allowed; color: #86868b;'
            
            # Aplicamos el bloqueo dinámicamente a los campos que existan en el formulario
            for campo in todos_bloqueados:
                if campo in self.fields:
                    self.fields[campo].disabled = True
                    self.fields[campo].widget.attrs['style'] = estilo_bloqueado