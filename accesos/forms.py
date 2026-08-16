from django import forms

from .models import Permiso, Rol


# =========================================================
# FORMULARIO DE ROLES
# =========================================================

class RolForm(forms.ModelForm):

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permiso.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permisos",
    )

    class Meta:
        model = Rol

        fields = [
            "name",
            "permissions",
        ]

        labels = {
            "name": "Nombre del rol",
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": (
                        "Ej. Bodega, Caja, Supervisor, "
                        "Contabilidad..."
                    ),
                    "autocomplete": "off",
                }
            ),
        }

    # =====================================================
    # INICIALIZACIÓN
    # =====================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # -------------------------------------------------
        # Permisos disponibles para asignar al rol
        # -------------------------------------------------
        #
        # Excluimos permisos internos de Django que no
        # deberían aparecer en la gestión normal de MAO.
        #
        # También excluimos "accesos" porque Rol y Permiso
        # son modelos proxy y no necesitamos mostrar sus
        # permisos automáticos dentro de esta pantalla.
        # -------------------------------------------------

        self.fields["permissions"].queryset = (
            Permiso.objects
            .select_related("content_type")
            .exclude(
                content_type__app_label__in=[
                    "admin",
                    "auth",
                    "contenttypes",
                    "sessions",
                    "accesos",
                ]
            )
            .order_by(
                "content_type__app_label",
                "content_type__model",
                "codename",
            )
        )

    # =====================================================
    # VALIDACIÓN DEL NOMBRE
    # =====================================================

    def clean_name(self):
        nombre = self.cleaned_data.get("name", "")

        nombre = nombre.strip()

        if not nombre:
            raise forms.ValidationError(
                "El nombre del rol es obligatorio."
            )

        # Evitar roles duplicados ignorando mayúsculas.
        roles_existentes = Rol.objects.filter(
            name__iexact=nombre
        )

        # Cuando estamos editando, no comparar contra
        # el mismo registro.
        if self.instance and self.instance.pk:
            roles_existentes = roles_existentes.exclude(
                pk=self.instance.pk
            )

        if roles_existentes.exists():
            raise forms.ValidationError(
                "Ya existe un rol con ese nombre."
            )

        return nombre