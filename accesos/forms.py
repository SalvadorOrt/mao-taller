from django import forms
from django.db.models import Q

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

        # =================================================
        # PERMISOS DISPONIBLES
        # =================================================
        #
        # La lista se genera automáticamente desde los
        # permisos registrados por Django.
        #
        # Por lo tanto, si mañana agregamos una aplicación
        # nueva, sus permisos aparecerán automáticamente
        # después de ejecutar las migraciones.
        #
        # Se excluyen únicamente componentes internos de
        # Django que no deben formar parte de los roles
        # operativos de MAO.
        # =================================================

        permisos = (
            Permiso.objects
            .select_related("content_type")
            .exclude(
                content_type__app_label__in=[
                    "admin",
                    "auth",
                    "contenttypes",
                    "sessions",
                ]
            )
        )

        # =================================================
        # ACCESOS
        # =================================================
        #
        # En la aplicación "accesos" tenemos dos proxies:
        #
        #   Rol
        #   Permiso
        #
        # Los permisos sobre Rol SÍ son útiles:
        #
        #   view_rol
        #   add_rol
        #   change_rol
        #   delete_rol
        #
        # porque permiten decidir qué usuarios pueden
        # administrar roles desde la web.
        #
        # Los permisos automáticos del proxy "Permiso"
        # no necesitamos mostrarlos.
        # =================================================

        permisos = permisos.exclude(
            Q(
                content_type__app_label="accesos",
                content_type__model="permiso",
            )
        )

        self.fields["permissions"].queryset = (
            permisos.order_by(
                "content_type__app_label",
                "content_type__model",
                "codename",
            )
        )


    # =====================================================
    # VALIDACIÓN DEL NOMBRE
    # =====================================================

    def clean_name(self):

        nombre = (
            self.cleaned_data
            .get("name", "")
            .strip()
        )

        if not nombre:
            raise forms.ValidationError(
                "El nombre del rol es obligatorio."
            )

        # -------------------------------------------------
        # EVITAR NOMBRES DUPLICADOS
        # -------------------------------------------------

        roles_existentes = Rol.objects.filter(
            name__iexact=nombre
        )

        # -------------------------------------------------
        # SI ESTAMOS EDITANDO, EXCLUIR EL ROL ACTUAL
        # -------------------------------------------------

        if self.instance and self.instance.pk:

            roles_existentes = (
                roles_existentes.exclude(
                    pk=self.instance.pk
                )
            )

        if roles_existentes.exists():

            raise forms.ValidationError(
                "Ya existe un rol con ese nombre."
            )

        return nombre