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