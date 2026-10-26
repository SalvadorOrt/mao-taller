import json

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms import BaseModelFormSet, modelformset_factory
from django.utils.crypto import constant_time_compare, salted_hmac

from .forms import ItemSolicitudCotizacionForm
from .models import ItemSolicitudCotizacion


# =========================================================
# REVISIÓN DEL REPUESTO
# =========================================================

def revision_item(item):
    datos = {
        campo.attname: getattr(item, campo.attname)
        for campo in item._meta.concrete_fields
    }

    return salted_hmac(
        "torre.fila",
        json.dumps(
            datos,
            sort_keys=True,
            default=str,
        ),
    ).hexdigest()


# =========================================================
# FORMULARIO DE UNA FILA
# =========================================================

class FilaRepuestoForm(ItemSolicitudCotizacionForm):
    revision = forms.CharField(
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta(ItemSolicitudCotizacionForm.Meta):
        fields = [
            *ItemSolicitudCotizacionForm.Meta.fields,
            "resaltado",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.revision_actual = (
            revision_item(self.instance)
            if self.instance.pk
            else ""
        )

        self.initial["revision"] = self.revision_actual

        conservar = {
            "descripcion_solicitada",
            "codigo_referencia",
            "marca_referencia",
            "cantidad",
            "unidad",
            "medida_solicitada",
            "lado",
            "posicion",
            "observacion",
            "orden_item",
            "resaltado",
            "revision",
        }

        for nombre in list(self.fields):
            if nombre not in conservar:
                del self.fields[nombre]

        self.fields["observacion"].widget = forms.Textarea(
            attrs={
                "rows": 2,
            }
        )

        # El resaltado es una marca visual editable incluso
        # cuando el repuesto ya está comprado.
        if self.instance.estado_abastecimiento == "COMPRADO":
            self.fields["resaltado"].disabled = False

        self.aplicar_estilos()

        self.fields["cantidad"].widget.attrs.update(
            min=1,
            step=1,
        )

        self.fields["orden_item"].widget.attrs.update(
            min=1,
            step=1,
        )

        # Permite mostrar los valores pendientes de los
        # registros existentes sin cambiar sus datos.
        for nombre in ("unidad", "lado", "posicion"):
            campo = self.fields[nombre]

            if (
                self.instance.pk
                and getattr(self.instance, nombre) == "POR_DEFINIR"
            ):
                campo.choices = [
                    ("POR_DEFINIR", "Por definir"),
                    *list(campo.choices),
                ]


# =========================================================
# VALIDACIÓN DEL CONJUNTO DE FILAS
# =========================================================

class BaseFilasRepuestos(BaseModelFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)

        form.fields["id"].queryset = self.queryset

    def clean(self):
        super().clean()

        ids = set()

        for form in self.forms:
            item = form.instance

            datos = getattr(
                form,
                "cleaned_data",
                {},
            )

            identificador = datos.get("id")

            if (
                identificador
                and identificador.pk != item.pk
            ):
                raise ValidationError(
                    "Un repuesto no pertenece a estas filas."
                )

            if item.pk:
                if item.pk in ids:
                    raise ValidationError(
                        "Hay un repuesto repetido en el formulario."
                    )

                ids.add(item.pk)

                recibido = form.data.get(
                    form.add_prefix("revision"),
                    "",
                )

                if not constant_time_compare(
                    str(recibido),
                    form.revision_actual,
                ):
                    raise ValidationError(
                        "Otro usuario modificó un repuesto. "
                        "Recarga la pantalla antes de guardar."
                    )

            if datos.get("DELETE") and item.pk:
                if not form.usuario.has_perm(
                    "cotizaciones.delete_itemsolicitudcotizacion"
                ):
                    raise PermissionDenied(
                        "No tienes permiso para eliminar repuestos."
                    )

                if item.estado_abastecimiento == "COMPRADO":
                    raise ValidationError(
                        "No puedes eliminar un repuesto comprado."
                    )

                if (
                    item.cotizaciones_proveedor.exists()
                    or item.fotos.exists()
                ):
                    raise ValidationError(
                        "No puedes eliminar un repuesto que ya "
                        "tiene ofertas o fotografías."
                    )


# =========================================================
# CONJUNTO DE FORMULARIOS
# =========================================================

FilasRepuestos = modelformset_factory(
    ItemSolicitudCotizacion,
    form=FilaRepuestoForm,
    formset=BaseFilasRepuestos,
    extra=0,
    can_delete=True,
    max_num=30,
    validate_max=True,
    absolute_max=40,
)