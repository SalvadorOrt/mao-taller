from django import forms
from django.db.models import Q

from .models import Permiso, Rol


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


    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        # Django genera automáticamente los permisos
        # de cada modelo. Por eso una aplicación nueva
        # aparecerá en el editor después de sus migraciones.

        permisos = (
            Permiso.objects
            .select_related(
                "content_type"
            )
            .exclude(
                content_type__app_label__in=[
                    "admin",
                    "auth",
                    "contenttypes",
                    "sessions",
                ]
            )
        )

        # El proxy Permiso no necesita aparecer.
        permisos = permisos.exclude(
            Q(
                content_type__app_label=
                    "accesos",
                content_type__model=
                    "permiso",
            )
        )

        self.fields[
            "permissions"
        ].queryset = (
            permisos
            .order_by(
                "content_type__app_label",
                "content_type__model",
                "codename",
            )
        )


    def clean_name(self):

        nombre = (
            self.cleaned_data
            .get(
                "name",
                "",
            )
            .strip()
        )

        if not nombre:
            raise forms.ValidationError(
                "El nombre del rol es obligatorio."
            )

        existentes = (
            Rol.objects
            .filter(
                name__iexact=nombre
            )
        )

        if (
            self.instance
            and self.instance.pk
        ):
            existentes = (
                existentes.exclude(
                    pk=self.instance.pk
                )
            )

        if existentes.exists():
            raise forms.ValidationError(
                "Ya existe un rol con ese nombre."
            )

        return nombre
