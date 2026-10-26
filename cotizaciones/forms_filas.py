"""Filas de repuestos adaptadas al modelo simplificado."""

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
            "descripcion_solicitada",
            "cantidad",
            "resaltado",
            "orden_item",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.revision_actual = (
            revision_item(self.instance)
            if self.instance.pk
            else ""
        )

        self.initial["revision"] = self.revision_actual


# =========================================================
# VALIDACIÓN DEL CONJUNTO DE FILAS
# =========================================================

class BaseFilasRepuestos(BaseModelFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)

        # Solo admite identificadores de las filas mostradas
        # que pertenecen a esta solicitud.
        form.fields["id"].queryset = (
            self.get_queryset().filter(
                solicitud_id=form.solicitud.pk,
            )
        )

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

            recibido_id = form.data.get(
                form.add_prefix("id")
            )

            if (
                recibido_id not in (None, "")
                and identificador is None
            ):
                raise ValidationError(
                    "Un repuesto no pertenece a estas filas."
                )

            if (
                identificador
                and identificador.pk != item.pk
            ):
                raise ValidationError(
                    "Un repuesto no pertenece a estas filas."
                )

            if not item.pk:
                continue

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

            if datos.get("DELETE"):
                if not form.usuario.has_perm(
                    "cotizaciones.delete_itemsolicitudcotizacion"
                ):
                    raise PermissionDenied(
                        "No tienes permiso para eliminar repuestos."
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