from django import forms
from django.contrib.auth.models import Group, Permission


class RolForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permisos",
    )

    class Meta:
        model = Group
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
                    "placeholder": "Ej. Bodega, Caja, Supervisor...",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # No mostrar permisos internos de Django.
        self.fields["permissions"].queryset = (
            Permission.objects
            .select_related("content_type")
            .exclude(
                content_type__app_label__in=[
                    "admin",
                    "auth",
                    "contenttypes",
                    "sessions",
                ]
            )
            .order_by(
                "content_type__app_label",
                "content_type__model",
                "codename",
            )
        )