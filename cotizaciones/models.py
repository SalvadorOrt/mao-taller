"""Modelos de cotizaciones y torre de control de repuestos."""

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError,
)
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone


CENTAVO = Decimal("0.01")


def _normalizar_textos(instancia, campos, mayusculas=()):
    for campo in campos:
        valor = getattr(instancia, campo)

        if valor is not None:
            valor = str(valor).strip()

            if campo in mayusculas:
                valor = valor.upper()

            setattr(instancia, campo, valor)


def _validar_solicitud_editable(solicitud):
    if (
        solicitud.estado == "CANCELADA"
        or solicitud.orden.estado == "ANULADA"
    ):
        raise ValidationError(
            "La solicitud o su orden de trabajo está cancelada."
        )


# =========================================================
# 1. ESPECIALIDADES EXISTENTES
# =========================================================

class ProveedorEspecialidad(models.Model):
    """
    Conserva los registros existentes de especialidades.

    La captura rápida utiliza directamente nombre_proveedor
    en CotizacionProveedor.
    """

    TIPOS_PROVEEDOR = [
        ("MENOR", "Menor / Repuestero"),
        ("MAYOR", "Mayorista"),
    ]

    proveedor = models.ForeignKey(
        "compras.Proveedor",
        on_delete=models.CASCADE,
        related_name="especialidades_cotizacion",
    )

    tipo_proveedor = models.CharField(
        max_length=10,
        choices=TIPOS_PROVEEDOR,
        default="MENOR",
    )

    categoria = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    marca = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    prioridad = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = [
            "prioridad",
            "proveedor__empresa",
            "proveedor__nombre_contacto",
        ]

        verbose_name = "Especialidad de proveedor"
        verbose_name_plural = "Especialidades de proveedores"

        indexes = [
            models.Index(fields=["activo", "tipo_proveedor"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["marca"]),
        ]

    def clean(self):
        super().clean()

        _normalizar_textos(
            self,
            ("categoria", "marca"),
            ("categoria", "marca"),
        )

        if isinstance(self.prioridad, int) and self.prioridad <= 0:
            raise ValidationError({
                "prioridad": "La prioridad debe ser mayor que 0.",
            })

    def save(self, *args, **kwargs):
        _normalizar_textos(
            self,
            ("categoria", "marca"),
            ("categoria", "marca"),
        )

        self.full_clean()

        return super().save(*args, **kwargs)

    def __str__(self):
        nombre = (
            self.proveedor.empresa
            or self.proveedor.nombre_contacto
            or f"Proveedor {self.proveedor_id}"
        )

        filtros = (
            " | ".join(
                filter(None, [self.categoria, self.marca])
            )
            or "Sin filtro"
        )

        return (
            f"{nombre} - "
            f"{self.get_tipo_proveedor_display()} - "
            f"{filtros}"
        )


# =========================================================
# 2. SOLICITUD / TORRE POR ORDEN DE TRABAJO
# =========================================================

class SolicitudCotizacion(models.Model):
    TIPOS_TRABAJO = [
        ("SIN_CLASIFICAR", "Por clasificar"),
        ("MECANICA", "Mecánica"),
        ("MOTOR", "Reparación de motor"),
        ("ENDEREZADO_PINTURA", "Enderezada y pintura"),
    ]

    # Se conservan los valores existentes.
    # La captura rápida calcula BORRADOR o RESPONDIDA.
    ESTADOS = [
        ("BORRADOR", "Borrador"),
        ("ENVIADA", "Enviada"),
        ("RESPONDIDA", "Con respuestas"),
        ("DECIDIDA", "Decidida"),
        ("COMPRADA", "Comprada"),
        ("CANCELADA", "Cancelada"),
    ]

    orden = models.ForeignKey(
        "ordenes_de_trabajo.OrdenTrabajo",
        on_delete=models.CASCADE,
        related_name="solicitudes_cotizacion",
    )

    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name="solicitudes_cotizacion",
    )

    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes_cotizacion_creadas",
    )

    tipo_trabajo = models.CharField(
        max_length=25,
        choices=TIPOS_TRABAJO,
        default="SIN_CLASIFICAR",
        db_index=True,
        verbose_name="Área de trabajo",
    )

    # La vista lo completa con la placa.
    titulo = models.CharField(max_length=200)

    observacion = models.TextField(
        null=True,
        blank=True,
    )

    urgente = models.BooleanField(default=False)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="BORRADOR",
    )

    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada_en"]

        verbose_name = "Solicitud de cotización"
        verbose_name_plural = "Solicitudes de cotización"

        indexes = [
            models.Index(fields=["estado", "creada_en"]),
            models.Index(fields=["sucursal", "estado"]),
        ]

    def _completar_sucursal(self):
        if self.orden_id and not self.sucursal_id:
            try:
                self.sucursal_id = self.orden.sucursal_id
            except ObjectDoesNotExist:
                pass

    def clean(self):
        super().clean()

        _normalizar_textos(
            self,
            ("titulo", "observacion"),
        )

        self._completar_sucursal()

        errores = {}

        if not self.orden_id:
            errores["orden"] = (
                "La orden de trabajo es obligatoria."
            )

        elif self.sucursal_id:
            try:
                if self.orden.sucursal_id != self.sucursal_id:
                    errores["sucursal"] = (
                        "La sucursal debe coincidir "
                        "con la sucursal de la OT."
                    )

            except ObjectDoesNotExist:
                errores["orden"] = (
                    "La orden de trabajo no existe."
                )

        if not self.titulo:
            errores["titulo"] = "El título es obligatorio."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        _normalizar_textos(
            self,
            ("titulo", "observacion"),
        )

        self._completar_sucursal()
        self.full_clean()

        return super().save(*args, **kwargs)

    @property
    def total_items(self):
        return self.items.count() if self.pk else 0

    @property
    def total_cotizaciones(self):
        if not self.pk:
            return 0

        return CotizacionProveedor.objects.filter(
            item__solicitud_id=self.pk,
        ).count()

    def actualizar_estado(self):
        """Resume si existen costos registrados."""

        if not self.pk:
            return

        using = self._state.db or "default"

        with transaction.atomic(using=using):
            actual = (
                type(self).objects
                .using(using)
                .select_for_update()
                .get(pk=self.pk)
            )

            if actual.estado == "CANCELADA":
                self.estado = actual.estado
                return

            tiene_costos = (
                CotizacionProveedor.objects
                .using(using)
                .filter(
                    item__solicitud_id=self.pk,
                    precio__isnull=False,
                )
                .exists()
            )

            nuevo = (
                "RESPONDIDA"
                if tiene_costos
                else "BORRADOR"
            )

            momento = timezone.now()

            type(self).objects.using(using).filter(
                pk=self.pk,
            ).update(
                estado=nuevo,
                actualizada_en=momento,
            )

            self.estado = nuevo
            self.actualizada_en = momento

    def __str__(self):
        return f"{self.orden.numero_orden} - {self.titulo}"


# =========================================================
# 3. REPUESTOS
# =========================================================

class ItemSolicitudCotizacion(models.Model):
    RESALTADOS = [
        ("NORMAL", "Normal"),
        ("ATENCION", "Atención"),
        ("URGENTE", "Urgente"),
    ]

    solicitud = models.ForeignKey(
        SolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="items",
    )

    descripcion_solicitada = models.CharField(
        "Repuesto",
        max_length=255,
    )

    cantidad = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
        ],
    )

    resaltado = models.CharField(
        max_length=10,
        choices=RESALTADOS,
        default="NORMAL",
    )

    orden_item = models.PositiveIntegerField(
        default=1,
        validators=[
            MinValueValidator(1),
        ],
    )

    # Conserva las observaciones que ya existan.
    observacion = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["orden_item", "id"]

        verbose_name = "Ítem de solicitud"
        verbose_name_plural = "Ítems de solicitud"

    def clean(self):
        super().clean()

        _normalizar_textos(
            self,
            ("descripcion_solicitada", "observacion"),
        )

        errores = {}

        if not self.descripcion_solicitada:
            errores["descripcion_solicitada"] = (
                "Escribe el repuesto."
            )

        if self.cantidad is None:
            errores["cantidad"] = (
                "La cantidad es obligatoria."
            )

        elif (
            isinstance(self.cantidad, int)
            and self.cantidad < 1
        ):
            errores["cantidad"] = (
                "La cantidad debe ser mayor que 0."
            )

        if self.pk:
            anterior = (
                type(self).objects
                .using(self._state.db or "default")
                .filter(pk=self.pk)
                .values("solicitud_id")
                .first()
            )

            if (
                anterior
                and anterior["solicitud_id"] != self.solicitud_id
            ):
                errores["solicitud"] = (
                    "El repuesto debe permanecer "
                    "en su solicitud original."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        using = (
            kwargs.get("using")
            or self._state.db
            or "default"
        )

        with transaction.atomic(using=using):
            self.full_clean()

            solicitud = (
                SolicitudCotizacion.objects
                .using(using)
                .select_for_update()
                .get(pk=self.solicitud_id)
            )

            _validar_solicitud_editable(solicitud)

            self.solicitud = solicitud

            resultado = super().save(*args, **kwargs)

            solicitud.actualizar_estado()

            return resultado

    @property
    def mejor_cotizacion(self):
        """
        Devuelve el menor costo registrado.

        Consultar esta propiedad no selecciona una compra.
        """

        if not self.pk:
            return None

        return (
            self.cotizaciones_proveedor
            .filter(precio__isnull=False)
            .order_by("precio", "id")
            .first()
        )

    def __str__(self):
        return (
            self.descripcion_solicitada
            or "Repuesto sin descripción"
        )


# =========================================================
# 4. FOTOS EXISTENTES
# =========================================================

class FotoItemCotizacion(models.Model):
    item = models.ForeignKey(
        ItemSolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="fotos",
    )

    imagen = models.ImageField(
        upload_to="cotizaciones/items/",
    )

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_subida", "id"]

        verbose_name = "Foto de ítem a cotizar"
        verbose_name_plural = "Fotos de ítems a cotizar"

    def save(self, *args, **kwargs):
        _normalizar_textos(
            self,
            ("descripcion",),
        )

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Foto item {self.item_id}"


# =========================================================
# 5. COSTOS DE PROVEEDORES
# =========================================================

class CotizacionProveedor(models.Model):
    item = models.ForeignKey(
        ItemSolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="cotizaciones_proveedor",
    )

    nombre_proveedor = models.CharField(
        "Proveedor",
        max_length=200,
    )

    marca_ofertada = models.CharField(
        "Marca",
        max_length=100,
        blank=True,
        default="",
    )

    precio = models.DecimalField(
        "Costo unitario final",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0")),
        ],
        help_text=(
            "Costo de una unidad solicitada, "
            "con IVA incluido."
        ),
    )

    # Conserva las observaciones que ya existan.
    observacion = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["item", "id"]

        verbose_name = "Cotización de proveedor"
        verbose_name_plural = "Cotizaciones de proveedores"

        indexes = [
            models.Index(
                fields=["item", "nombre_proveedor"],
            ),
            models.Index(fields=["precio"]),
        ]

    def clean(self):
        super().clean()

        _normalizar_textos(
            self,
            ("marca_ofertada", "observacion"),
            ("marca_ofertada",),
        )

        self.nombre_proveedor = " ".join(
            (self.nombre_proveedor or "").split()
        )

        self.marca_ofertada = (
            self.marca_ofertada or ""
        )

        errores = {}

        if not self.nombre_proveedor:
            errores["nombre_proveedor"] = (
                "Escribe el nombre del proveedor."
            )

        if self.pk:
            anterior = (
                type(self).objects
                .using(self._state.db or "default")
                .filter(pk=self.pk)
                .values("item_id")
                .first()
            )

            if (
                anterior
                and anterior["item_id"] != self.item_id
            ):
                errores["item"] = (
                    "La oferta debe permanecer "
                    "en su repuesto original."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        using = (
            kwargs.get("using")
            or self._state.db
            or "default"
        )

        with transaction.atomic(using=using):
            self.full_clean()

            item = (
                ItemSolicitudCotizacion.objects
                .using(using)
                .get(pk=self.item_id)
            )

            solicitud = (
                SolicitudCotizacion.objects
                .using(using)
                .select_for_update()
                .get(pk=item.solicitud_id)
            )

            _validar_solicitud_editable(solicitud)

            self.item = (
                ItemSolicitudCotizacion.objects
                .using(using)
                .select_for_update()
                .get(pk=self.item_id)
            )

            resultado = super().save(*args, **kwargs)

            solicitud.actualizar_estado()

            return resultado

    @property
    def costo_requerimiento(self):
        """Cantidad solicitada multiplicada por el costo unitario final."""

        if (
            not self.item_id
            or not isinstance(self.precio, Decimal)
            or not self.precio.is_finite()
            or self.precio < 0
        ):
            return None

        try:
            cantidad = self.item.cantidad

        except ObjectDoesNotExist:
            return None

        return (
            self.precio * Decimal(cantidad)
        ).quantize(
            CENTAVO,
            rounding=ROUND_HALF_UP,
        )

    def __str__(self):
        return (
            f"{self.nombre_proveedor} - "
            f"{self.item.descripcion_solicitada}"
        )


# =========================================================
# 6. DECISIÓN GLOBAL EXISTENTE
# =========================================================

class DecisionCotizacion(models.Model):
    """
    Conserva los registros existentes de decisiones globales.

    Este modelo no participa en la captura rápida de costos.
    """

    solicitud = models.OneToOneField(
        SolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="decision_final",
    )

    proveedor_seleccionado = models.ForeignKey(
        "compras.Proveedor",
        on_delete=models.PROTECT,
        related_name="decisiones_ganadas",
    )

    motivo = models.TextField(
        null=True,
        blank=True,
    )

    precio_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0")),
        ],
    )

    decidida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="decisiones_cotizacion_tomadas",
    )

    decidida_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decidida_en"]

        verbose_name = "Decisión de cotización"
        verbose_name_plural = "Decisiones de cotización"

    def clean(self):
        super().clean()

        _normalizar_textos(
            self,
            ("motivo",),
        )

    def save(self, *args, **kwargs):
        _normalizar_textos(
            self,
            ("motivo",),
        )

        self.full_clean()

        return super().save(*args, **kwargs)

    def __str__(self):
        nombre = (
            self.proveedor_seleccionado.empresa
            or self.proveedor_seleccionado.nombre_contacto
        )

        return f"{self.solicitud} -> {nombre}"