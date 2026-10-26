"""Formularios simplificados de la torre de control de repuestos."""

from django import forms
from django.core.exceptions import (
    NON_FIELD_ERRORS,
    PermissionDenied,
    ValidationError,
)
from django.db import transaction

from ordenes_de_trabajo.models import OrdenTrabajo, Sucursal

from .models import (
    CotizacionProveedor,
    FotoItemCotizacion,
    ItemSolicitudCotizacion,
    SolicitudCotizacion,
)


# =========================================================
# SUCURSAL OPERATIVA
# =========================================================

def obtener_sucursal_operativa(usuario, sucursal_activa_id=None):
    """
    Recupera la sucursal elegida desde el dashboard.

    Los usuarios normales operan en su sucursal.
    El superusuario y los usuarios con permiso especial
    pueden utilizar otra sucursal activa.
    """

    if (
        not usuario
        or not usuario.is_authenticated
        or not usuario.is_active
    ):
        raise PermissionDenied(
            "Debes iniciar sesión con un usuario activo."
        )

    puede_cambiar = (
        usuario.is_superuser
        or usuario.has_perm(
            "inventario.cambiar_sucursal_operativa"
        )
    )

    sucursal_personal_id = usuario.sucursal_id

    if not puede_cambiar and not sucursal_personal_id:
        raise PermissionDenied(
            "Tu usuario necesita una sucursal asignada."
        )

    if sucursal_activa_id in (None, ""):
        sucursal_id = sucursal_personal_id

    else:
        try:
            sucursal_id = int(sucursal_activa_id)

        except (TypeError, ValueError):
            raise PermissionDenied(
                "La sucursal seleccionada no es válida."
            ) from None

    if not sucursal_id:
        raise PermissionDenied(
            "Selecciona una sucursal desde el dashboard."
        )

    if (
        not puede_cambiar
        and sucursal_id != sucursal_personal_id
    ):
        raise PermissionDenied(
            "No tienes permiso para cambiar de sucursal."
        )

    try:
        return Sucursal.objects.get(
            pk=sucursal_id,
            activa=True,
        )

    except Sucursal.DoesNotExist:
        raise PermissionDenied(
            "La sucursal seleccionada no existe o está inactiva."
        ) from None


def _solicitud_en_sucursal(solicitud_id, sucursal):
    try:
        return (
            SolicitudCotizacion.objects
            .select_related("orden", "sucursal")
            .get(
                pk=solicitud_id,
                sucursal_id=sucursal.pk,
                orden__sucursal_id=sucursal.pk,
            )
        )

    except SolicitudCotizacion.DoesNotExist:
        raise PermissionDenied(
            "La solicitud no pertenece a tu sucursal operativa."
        ) from None


def _validar_solicitud_abierta(solicitud):
    if (
        solicitud.estado == "CANCELADA"
        or solicitud.orden.estado == "ANULADA"
    ):
        raise ValidationError(
            "La solicitud o su orden de trabajo está cancelada."
        )


def _item_en_sucursal(item_id, sucursal):
    try:
        return (
            ItemSolicitudCotizacion.objects
            .select_related(
                "solicitud__orden",
                "solicitud__sucursal",
            )
            .get(
                pk=item_id,
                solicitud__sucursal_id=sucursal.pk,
                solicitud__orden__sucursal_id=sucursal.pk,
            )
        )

    except ItemSolicitudCotizacion.DoesNotExist:
        raise PermissionDenied(
            "El repuesto no pertenece a tu sucursal operativa."
        ) from None


def _titulo_de_orden(orden):
    return str(
        orden.placa or orden.numero_orden
    ).strip()


# =========================================================
# CONFIGURACIÓN COMÚN
# =========================================================

class FormularioTorreMixin:
    def configurar_usuario(self, usuario, sucursal_activa_id):
        self.usuario = usuario
        self.sucursal_activa_id = sucursal_activa_id

        self.sucursal_operativa = obtener_sucursal_operativa(
            usuario,
            sucursal_activa_id,
        )

        accion = "change" if self.instance.pk else "add"
        modelo = self._meta.model._meta

        permiso = (
            f"{modelo.app_label}."
            f"{accion}_{modelo.model_name}"
        )

        if not usuario.has_perm(permiso):
            raise PermissionDenied(
                "No tienes permiso para realizar esta operación."
            )

    def aplicar_estilos(self):
        for campo in self.fields.values():
            widget = campo.widget

            if isinstance(widget, forms.HiddenInput):
                continue

            if isinstance(widget, forms.CheckboxInput):
                clase = "form-check-input"

            elif isinstance(widget, forms.Select):
                clase = "form-select"

            else:
                clase = "form-control"

            widget.attrs["class"] = (
                f"{widget.attrs.get('class', '')} {clase}"
            ).strip()

    def add_error(self, field, error):
        if (
            isinstance(error, ValidationError)
            and hasattr(error, "error_dict")
        ):
            errores = {}

            for nombre, mensajes in error.error_dict.items():
                destino = (
                    nombre
                    if nombre in self.fields
                    else NON_FIELD_ERRORS
                )

                errores.setdefault(
                    destino,
                    [],
                ).extend(mensajes)

            error = ValidationError(errores)

        if field is not None and field not in self.fields:
            field = None

        return super().add_error(field, error)


# =========================================================
# SOLICITUD
# =========================================================

class SolicitudCotizacionForm(
    FormularioTorreMixin,
    forms.ModelForm,
):
    class Meta:
        model = SolicitudCotizacion

        fields = [
            "orden",
            "tipo_trabajo",
        ]

        labels = {
            "orden": "Orden de trabajo",
            "tipo_trabajo": "Área de trabajo",
        }

    def __init__(
        self,
        *args,
        usuario,
        sucursal_activa_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.configurar_usuario(
            usuario,
            sucursal_activa_id,
        )

        self.fields["orden"].queryset = (
            OrdenTrabajo.objects
            .filter(
                sucursal_id=self.sucursal_operativa.pk,
            )
            .exclude(estado="ANULADA")
            .order_by("-id")
        )

        self.fields["tipo_trabajo"].choices = [
            ("", "Selecciona el área"),
        ] + [
            opcion
            for opcion in SolicitudCotizacion.TIPOS_TRABAJO
            if opcion[0] != "SIN_CLASIFICAR"
        ]

        if self.instance.pk:
            _solicitud_en_sucursal(
                self.instance.pk,
                self.sucursal_operativa,
            )

            self.fields["orden"].disabled = True

        else:
            self.fields["orden"].queryset = (
                self.fields["orden"].queryset.filter(
                    estado="ABIERTA",
                )
            )

            self.instance.sucursal = self.sucursal_operativa
            self.instance.creada_por = usuario

            self.initial.setdefault(
                "tipo_trabajo",
                "",
            )

        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()

        self.sucursal_operativa = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        if self.instance.pk:
            actual = _solicitud_en_sucursal(
                self.instance.pk,
                self.sucursal_operativa,
            )

            _validar_solicitud_abierta(actual)

        orden = datos.get("orden")

        if (
            orden
            and orden.sucursal_id != self.sucursal_operativa.pk
        ):
            self.add_error(
                "orden",
                "La orden debe pertenecer a tu sucursal operativa.",
            )

        if orden:
            self.instance.titulo = _titulo_de_orden(orden)

        self.instance.sucursal = self.sucursal_operativa

        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        if objeto.pk:
            _validar_solicitud_abierta(
                _solicitud_en_sucursal(
                    objeto.pk,
                    sucursal,
                )
            )

        else:
            objeto.creada_por = self.usuario

        objeto.sucursal = sucursal
        objeto.titulo = _titulo_de_orden(objeto.orden)

        if commit:
            objeto.save()
            self.save_m2m()

        return objeto


# =========================================================
# REPUESTO
# =========================================================

class ItemSolicitudCotizacionForm(
    FormularioTorreMixin,
    forms.ModelForm,
):
    class Meta:
        model = ItemSolicitudCotizacion

        fields = [
            "descripcion_solicitada",
            "cantidad",
            "resaltado",
            "orden_item",
        ]

        labels = {
            "descripcion_solicitada": "Repuesto",
            "cantidad": "Cantidad",
        }

        widgets = {
            "descripcion_solicitada": forms.TextInput(
                attrs={
                    "placeholder": "Escribe el repuesto",
                }
            ),

            "cantidad": forms.NumberInput(
                attrs={
                    "min": 1,
                    "step": 1,
                }
            ),

            "resaltado": forms.HiddenInput(),
            "orden_item": forms.HiddenInput(),
        }

    def __init__(
        self,
        *args,
        solicitud,
        usuario,
        sucursal_activa_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.configurar_usuario(
            usuario,
            sucursal_activa_id,
        )

        self.solicitud = _solicitud_en_sucursal(
            solicitud.pk,
            self.sucursal_operativa,
        )

        if (
            self.instance.pk
            and self.instance.solicitud_id != self.solicitud.pk
        ):
            raise PermissionDenied(
                "El repuesto no pertenece a esta solicitud."
            )

        self.instance.solicitud = self.solicitud

        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        self.solicitud = _solicitud_en_sucursal(
            self.solicitud.pk,
            sucursal,
        )

        _validar_solicitud_abierta(self.solicitud)

        self.instance.solicitud = self.solicitud

        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        objeto.solicitud = _solicitud_en_sucursal(
            self.solicitud.pk,
            sucursal,
        )

        _validar_solicitud_abierta(objeto.solicitud)

        if commit:
            objeto.save()
            self.save_m2m()

        return objeto


# =========================================================
# COSTO DEL PROVEEDOR
# =========================================================

class CotizacionProveedorForm(
    FormularioTorreMixin,
    forms.ModelForm,
):
    class Meta:
        model = CotizacionProveedor

        fields = [
            "nombre_proveedor",
            "marca_ofertada",
            "precio",
        ]

        labels = {
            "nombre_proveedor": "Proveedor",
            "marca_ofertada": "Marca (opcional)",
            "precio": "Costo unitario final",
        }

        widgets = {
            "nombre_proveedor": forms.TextInput(
                attrs={
                    "placeholder": "Escribe el proveedor",
                    "autocomplete": "off",
                }
            ),

            "marca_ofertada": forms.TextInput(
                attrs={
                    "placeholder": "Marca (opcional)",
                }
            ),

            "precio": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.01",
                    "placeholder": "0.00",
                }
            ),
        }

    def __init__(
        self,
        *args,
        item,
        usuario,
        sucursal_activa_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.configurar_usuario(
            usuario,
            sucursal_activa_id,
        )

        self.item = _item_en_sucursal(
            item.pk,
            self.sucursal_operativa,
        )

        if (
            self.instance.pk
            and self.instance.item_id != self.item.pk
        ):
            raise PermissionDenied(
                "La oferta no pertenece a este repuesto."
            )

        self.instance.item = self.item

        self.aplicar_estilos()

    def clean_nombre_proveedor(self):
        return " ".join(
            self.cleaned_data["nombre_proveedor"].split()
        )

    def clean(self):
        datos = super().clean()

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        self.item = _item_en_sucursal(
            self.item.pk,
            sucursal,
        )

        _validar_solicitud_abierta(
            self.item.solicitud,
        )

        self.instance.item = self.item

        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        with transaction.atomic():
            item = _item_en_sucursal(
                self.item.pk,
                sucursal,
            )

            solicitud = (
                SolicitudCotizacion.objects
                .select_for_update()
                .get(pk=item.solicitud_id)
            )

            _validar_solicitud_abierta(solicitud)

            objeto.item = (
                ItemSolicitudCotizacion.objects
                .select_for_update()
                .get(
                    pk=item.pk,
                    solicitud_id=solicitud.pk,
                )
            )

            if commit:
                objeto.save()
                self.save_m2m()

        return objeto


# =========================================================
# FOTO DEL REPUESTO
# =========================================================

class FotoItemCotizacionForm(
    FormularioTorreMixin,
    forms.ModelForm,
):
    class Meta:
        model = FotoItemCotizacion

        fields = [
            "imagen",
            "descripcion",
        ]

    def __init__(
        self,
        *args,
        item,
        usuario,
        sucursal_activa_id=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.configurar_usuario(
            usuario,
            sucursal_activa_id,
        )

        self.item = _item_en_sucursal(
            item.pk,
            self.sucursal_operativa,
        )

        if (
            self.instance.pk
            and self.instance.item_id != self.item.pk
        ):
            raise PermissionDenied(
                "La foto no pertenece a este repuesto."
            )

        self.instance.item = self.item

        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        self.item = _item_en_sucursal(
            self.item.pk,
            sucursal,
        )

        _validar_solicitud_abierta(
            self.item.solicitud,
        )

        self.instance.item = self.item

        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)

        sucursal = obtener_sucursal_operativa(
            self.usuario,
            self.sucursal_activa_id,
        )

        objeto.item = _item_en_sucursal(
            self.item.pk,
            sucursal,
        )

        _validar_solicitud_abierta(
            objeto.item.solicitud,
        )

        if commit:
            objeto.save()
            self.save_m2m()

        return objeto


# =========================================================
# FILTROS DEL LISTADO
# =========================================================

class FiltroTorreControlForm(forms.Form):
    q = forms.CharField(
        required=False,
        max_length=200,
        label="Buscar",
    )

    tipo_trabajo = forms.ChoiceField(
        required=False,
        label="Área de trabajo",
        choices=(
            [("", "Todas las áreas")]
            + SolicitudCotizacion.TIPOS_TRABAJO
        ),
    )

    estado = forms.ChoiceField(
        required=False,
        label="Estado de la solicitud",
        choices=(
            [("", "Todos los estados")]
            + SolicitudCotizacion.ESTADOS
        ),
    )