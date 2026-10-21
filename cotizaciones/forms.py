"""Formularios de la torre de control de repuestos.

Las vistas deben exigir autenticación, filtrar los objetos por la sucursal
operativa y pasar usuario=request.user. El selector de sucursal utiliza
obtener_sucursal_operativa() con el ID guardado en la sesión del servidor.
"""

from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from compras.models import Proveedor
from inventario.models import CodigoProducto, Producto
from ordenes_de_trabajo.models import OrdenTrabajo, Sucursal

from .models import (
    CotizacionProveedor,
    FotoItemCotizacion,
    ItemSolicitudCotizacion,
    SolicitudCotizacion,
)


def obtener_sucursal_operativa(usuario, sucursal_activa_id=None):
    """Resuelve y valida la sucursal elegida sin modificar la del usuario."""
    if not usuario or not usuario.is_authenticated or not usuario.is_active:
        raise PermissionDenied("Debes iniciar sesión con un usuario activo.")
    if not usuario.sucursal_id:
        raise PermissionDenied("Tu usuario necesita una sucursal asignada.")

    if sucursal_activa_id in (None, ""):
        sucursal_id = usuario.sucursal_id
    else:
        try:
            sucursal_id = int(sucursal_activa_id)
        except (TypeError, ValueError):
            raise PermissionDenied("La sucursal seleccionada no es válida.") from None

    puede_cambiar = usuario.is_superuser or usuario.has_perm(
        "inventario.cambiar_sucursal_operativa"
    )
    if sucursal_id != usuario.sucursal_id and not puede_cambiar:
        raise PermissionDenied("No tienes permiso para cambiar de sucursal.")

    try:
        return Sucursal.objects.get(pk=sucursal_id, activa=True)
    except Sucursal.DoesNotExist:
        raise PermissionDenied("La sucursal seleccionada no existe o está inactiva.") from None


def _solicitud_en_sucursal(solicitud_id, sucursal):
    try:
        return SolicitudCotizacion.objects.select_related("orden", "sucursal").get(
            pk=solicitud_id,
            sucursal_id=sucursal.pk,
            orden__sucursal_id=sucursal.pk,
        )
    except SolicitudCotizacion.DoesNotExist:
        raise PermissionDenied("La solicitud no pertenece a tu sucursal operativa.") from None


def _validar_solicitud_abierta(solicitud):
    if solicitud.estado == "CANCELADA" or solicitud.orden.estado == "ANULADA":
        raise ValidationError("La solicitud o su orden de trabajo está cancelada.")


class FormularioTorreMixin:
    """Permisos de edición, estilos y errores de los campos internos del modelo."""

    def configurar_usuario(self, usuario, sucursal_activa_id):
        self.usuario = usuario
        self.sucursal_activa_id = sucursal_activa_id
        self.sucursal_operativa = obtener_sucursal_operativa(usuario, sucursal_activa_id)
        accion = "change" if self.instance.pk else "add"
        modelo = self._meta.model._meta
        permiso = f"{modelo.app_label}.{accion}_{modelo.model_name}"
        if not usuario.has_perm(permiso):
            raise PermissionDenied("No tienes permiso para realizar esta operación.")

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
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {clase}".strip()

    def add_error(self, field, error):
        # El modelo también valida campos que no se editan en el formulario.
        if isinstance(error, ValidationError) and hasattr(error, "error_dict"):
            errores = {}
            for nombre, mensajes in error.error_dict.items():
                destino = nombre if nombre in self.fields else NON_FIELD_ERRORS
                errores.setdefault(destino, []).extend(mensajes)
            error = ValidationError(errores)
        if field is not None and field not in self.fields:
            field = None
        return super().add_error(field, error)


# ==========================================
# 1. SOLICITUD DE COTIZACIÓN
# ==========================================
class SolicitudCotizacionForm(FormularioTorreMixin, forms.ModelForm):
    class Meta:
        model = SolicitudCotizacion
        fields = ["orden", "tipo_trabajo", "titulo", "urgente", "observacion"]
        labels = {"orden": "Orden de trabajo", "tipo_trabajo": "Área de trabajo"}
        widgets = {"observacion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, usuario, sucursal_activa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.configurar_usuario(usuario, sucursal_activa_id)
        self.fields["orden"].queryset = OrdenTrabajo.objects.filter(
            sucursal_id=self.sucursal_operativa.pk
        ).exclude(estado="ANULADA").order_by("-id")
        self.fields["tipo_trabajo"].choices = [("", "Selecciona el área")] + [
            opcion for opcion in SolicitudCotizacion.TIPOS_TRABAJO
            if opcion[0] != "SIN_CLASIFICAR"
        ]
        if self.instance.pk:
            _solicitud_en_sucursal(self.instance.pk, self.sucursal_operativa)
            self.fields["orden"].disabled = True
        else:
            self.instance.sucursal = self.sucursal_operativa
            self.instance.creada_por = usuario
            self.initial.setdefault("tipo_trabajo", "")
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        self.sucursal_operativa = obtener_sucursal_operativa(
            self.usuario, self.sucursal_activa_id
        )
        if self.instance.pk:
            actual = _solicitud_en_sucursal(self.instance.pk, self.sucursal_operativa)
            _validar_solicitud_abierta(actual)
        orden = datos.get("orden")
        if orden and orden.sucursal_id != self.sucursal_operativa.pk:
            self.add_error("orden", "La orden debe pertenecer a tu sucursal operativa.")
        self.instance.sucursal = self.sucursal_operativa
        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        if objeto.pk:
            _validar_solicitud_abierta(_solicitud_en_sucursal(objeto.pk, sucursal))
        else:
            objeto.creada_por = self.usuario
        objeto.sucursal = sucursal
        if commit:
            objeto.save()
            self.save_m2m()
        return objeto


# ==========================================
# 2. REPUESTO SOLICITADO
# ==========================================
class ItemSolicitudCotizacionForm(FormularioTorreMixin, forms.ModelForm):
    class Meta:
        model = ItemSolicitudCotizacion
        fields = [
            "producto_rel", "codigo_producto_rel", "descripcion_solicitada",
            "codigo_referencia", "codigo_barras", "marca_referencia",
            "categoria_referencia", "cantidad", "unidad", "medida_solicitada",
            "lado", "posicion", "observacion", "orden_item",
        ]
        labels = {
            "producto_rel": "Producto del catálogo (opcional)",
            "codigo_producto_rel": "Código del producto (opcional)",
            "descripcion_solicitada": "Repuesto solicitado",
            "marca_referencia": "Marca de referencia",
            "categoria_referencia": "Categoría de referencia",
            "orden_item": "Orden en la lista",
        }
        widgets = {"observacion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, solicitud, usuario, sucursal_activa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.configurar_usuario(usuario, sucursal_activa_id)
        self.solicitud = _solicitud_en_sucursal(solicitud.pk, self.sucursal_operativa)
        if self.instance.pk and self.instance.solicitud_id != self.solicitud.pk:
            raise PermissionDenied("El repuesto no pertenece a esta solicitud.")
        self.instance.solicitud = self.solicitud
        self.fields["producto_rel"].queryset = Producto.objects.all()
        self.fields["codigo_producto_rel"].queryset = CodigoProducto.objects.none()

        for nombre, opciones in [
            ("unidad", ItemSolicitudCotizacion.UNIDADES),
            ("lado", ItemSolicitudCotizacion.LADOS),
            ("posicion", ItemSolicitudCotizacion.POSICIONES),
        ]:
            self.fields[nombre].choices = [("", "Selecciona una opción")] + [
                opcion for opcion in opciones if opcion[0] != "POR_DEFINIR"
            ]
            if not self.instance.pk:
                self.initial.setdefault(nombre, "")

        if self.instance.estado_abastecimiento == "COMPRADO":
            producto_id = self.instance.producto_rel_id
        else:
            producto_id = (
                self.data.get(self.add_prefix("producto_rel")) if self.is_bound
                else self.initial.get("producto_rel", self.instance.producto_rel_id)
            )
        if hasattr(producto_id, "pk"):
            producto_id = producto_id.pk
        try:
            producto_id = int(producto_id)
        except (TypeError, ValueError):
            producto_id = None
        if producto_id:
            self.fields["codigo_producto_rel"].queryset = CodigoProducto.objects.filter(
                producto_id=producto_id
            )

        if self.instance.estado_abastecimiento == "COMPRADO":
            for nombre, campo in self.fields.items():
                if nombre not in {"observacion", "orden_item"}:
                    campo.disabled = True
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        _validar_solicitud_abierta(_solicitud_en_sucursal(self.solicitud.pk, sucursal))
        producto = datos.get("producto_rel")
        codigo = datos.get("codigo_producto_rel")
        if codigo and (not producto or codigo.producto_id != producto.pk):
            self.add_error("codigo_producto_rel", "El código debe pertenecer al producto elegido.")
        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        objeto.solicitud = _solicitud_en_sucursal(self.solicitud.pk, sucursal)
        _validar_solicitud_abierta(objeto.solicitud)
        if commit:
            objeto.save()
            self.save_m2m()
        return objeto


# ==========================================
# 3. OFERTA DEL PROVEEDOR
# ==========================================
class CotizacionProveedorForm(FormularioTorreMixin, forms.ModelForm):
    disponible = forms.TypedChoiceField(
        label="Disponibilidad",
        choices=[("", "Por confirmar"), ("SI", "Disponible"), ("NO", "No disponible")],
        coerce=lambda valor: {"SI": True, "NO": False}[valor],
        empty_value=None,
        required=False,
    )

    class Meta:
        model = CotizacionProveedor
        fields = [
            "proveedor", "tipo_proveedor", "precio", "marca_ofertada", "medida_ofertada",
            "presentacion", "unidades_por_presentacion", "contenido_presentacion",
            "tratamiento_iva", "porcentaje_iva", "disponible", "tiempo_entrega",
            "calidad_referencial", "observacion",
        ]
        labels = {
            "precio": "Costo por presentación",
            "unidades_por_presentacion": "Equivalencia con la unidad solicitada",
            "tratamiento_iva": "IVA del precio ofrecido",
            "calidad_referencial": "Calidad referencial (1 a 5)",
        }
        widgets = {"observacion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, item, usuario, sucursal_activa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.configurar_usuario(usuario, sucursal_activa_id)
        try:
            self.item = ItemSolicitudCotizacion.objects.select_related("solicitud").get(pk=item.pk)
        except ItemSolicitudCotizacion.DoesNotExist:
            raise PermissionDenied("El repuesto no existe.") from None
        _solicitud_en_sucursal(self.item.solicitud_id, self.sucursal_operativa)
        if self.instance.pk and self.instance.item_id != self.item.pk:
            raise PermissionDenied("La oferta no pertenece a este repuesto.")
        self.instance.item = self.item
        proveedores = Q(activo=True)
        if self.instance.pk:
            proveedores |= Q(pk=self.instance.proveedor_id)
            self.fields["proveedor"].disabled = True
            self.initial["disponible"] = {
                True: "SI", False: "NO", None: ""
            }[self.instance.disponible]
        self.fields["proveedor"].queryset = Proveedor.objects.filter(proveedores).order_by(
            "empresa", "nombre_contacto"
        )
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        solicitud = _solicitud_en_sucursal(self.item.solicitud_id, sucursal)
        _validar_solicitud_abierta(solicitud)
        actual = ItemSolicitudCotizacion.objects.get(pk=self.item.pk)
        if actual.estado_abastecimiento == "COMPRADO":
            raise ValidationError("Las ofertas de un repuesto comprado quedan bloqueadas.")

        hay_respuesta = (
            datos.get("precio") is not None
            or datos.get("disponible") is not None
            or bool(datos.get("marca_ofertada"))
            or bool(datos.get("medida_ofertada"))
            or bool(datos.get("tiempo_entrega"))
        )
        if hay_respuesta and self.instance.estado in {"PENDIENTE", "ENVIADA"}:
            self.instance.estado = "RESPONDIO"
            if self.instance.fecha_respuesta is None:
                self.instance.fecha_respuesta = timezone.now()
        return datos

    def save(self, commit=True):
        """Con commit=False, quien llama administra el guardado y la transacción."""
        objeto = super().save(commit=False)
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        with transaction.atomic():
            solicitud = SolicitudCotizacion.objects.select_for_update().get(
                pk=self.item.solicitud_id
            )
            _solicitud_en_sucursal(solicitud.pk, sucursal)
            _validar_solicitud_abierta(solicitud)
            objeto.item = ItemSolicitudCotizacion.objects.select_for_update().get(pk=self.item.pk)
            if objeto.item.estado_abastecimiento == "COMPRADO":
                raise ValidationError("Las ofertas de un repuesto comprado quedan bloqueadas.")
            if not objeto.pk:
                ultimo = CotizacionProveedor.objects.filter(
                    item_id=objeto.item_id, proveedor_id=objeto.proveedor_id
                ).aggregate(numero=Max("numero_opcion"))["numero"] or 0
                objeto.numero_opcion = ultimo + 1
            if commit:
                objeto.save()
                self.save_m2m()
        return objeto


# ==========================================
# 4. FOTO DEL REPUESTO
# ==========================================
class FotoItemCotizacionForm(FormularioTorreMixin, forms.ModelForm):
    class Meta:
        model = FotoItemCotizacion
        fields = ["imagen", "descripcion"]

    def __init__(self, *args, item, usuario, sucursal_activa_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.configurar_usuario(usuario, sucursal_activa_id)
        self.item = ItemSolicitudCotizacion.objects.select_related("solicitud").get(pk=item.pk)
        _solicitud_en_sucursal(self.item.solicitud_id, self.sucursal_operativa)
        if self.instance.pk and self.instance.item_id != self.item.pk:
            raise PermissionDenied("La foto no pertenece a este repuesto.")
        self.instance.item = self.item
        self.aplicar_estilos()

    def clean(self):
        datos = super().clean()
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        _validar_solicitud_abierta(_solicitud_en_sucursal(self.item.solicitud_id, sucursal))
        return datos

    def save(self, commit=True):
        objeto = super().save(commit=False)
        sucursal = obtener_sucursal_operativa(self.usuario, self.sucursal_activa_id)
        _validar_solicitud_abierta(_solicitud_en_sucursal(self.item.solicitud_id, sucursal))
        objeto.item = self.item
        if commit:
            objeto.save()
            self.save_m2m()
        return objeto


# ==========================================
# 5. FILTROS DEL LISTADO
# ==========================================
class FiltroTorreControlForm(forms.Form):
    q = forms.CharField(required=False, max_length=200, label="Buscar")
    tipo_trabajo = forms.ChoiceField(
        required=False,
        label="Área de trabajo",
        choices=[("", "Todas las áreas")] + SolicitudCotizacion.TIPOS_TRABAJO,
    )
    estado = forms.ChoiceField(
        required=False,
        label="Estado de la solicitud",
        choices=[("", "Todos los estados")] + SolicitudCotizacion.ESTADOS,
    )