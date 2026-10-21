"""Modelos de cotizaciones y torre de control de repuestos de MAO.

La autorizaciÃ³n por usuario, sucursal activa y permiso de cambio de sucursal
se aplica en las vistas. La sucursal de cada solicitud coincide con su OT.
"""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
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


# ==========================================
# 1. ESPECIALIDADES DE PROVEEDORES
# ==========================================
class ProveedorEspecialidad(models.Model):
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
        max_length=10, choices=TIPOS_PROVEEDOR, default="MENOR"
    )
    categoria = models.CharField(max_length=100, null=True, blank=True)
    marca = models.CharField(max_length=100, null=True, blank=True)
    prioridad = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["prioridad", "proveedor__empresa", "proveedor__nombre_contacto"]
        verbose_name = "Especialidad de proveedor"
        verbose_name_plural = "Especialidades de proveedores"
        indexes = [
            models.Index(fields=["activo", "tipo_proveedor"]),
            models.Index(fields=["categoria"]),
            models.Index(fields=["marca"]),
        ]

    def clean(self):
        super().clean()
        _normalizar_textos(self, ("categoria", "marca"), ("categoria", "marca"))
        if isinstance(self.prioridad, int) and self.prioridad <= 0:
            raise ValidationError({"prioridad": "La prioridad debe ser mayor que 0."})

    def save(self, *args, **kwargs):
        _normalizar_textos(self, ("categoria", "marca"), ("categoria", "marca"))
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        nombre = (
            self.proveedor.empresa
            or self.proveedor.nombre_contacto
            or f"Proveedor {self.proveedor_id}"
        )
        filtros = " | ".join(filter(None, [self.categoria, self.marca])) or "Sin filtro"
        return f"{nombre} - {self.get_tipo_proveedor_display()} - {filtros}"


# ==========================================
# 2. SOLICITUD DE COTIZACIÃ“N
# ==========================================
class SolicitudCotizacion(models.Model):
    TIPOS_TRABAJO = [
        ("SIN_CLASIFICAR", "Por clasificar"),
        ("MECANICA", "MecÃ¡nica"),
        ("MOTOR", "ReparaciÃ³n de motor"),
        ("ENDEREZADO_PINTURA", "Enderezada y pintura"),
    ]
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
        verbose_name="Ãrea de trabajo",
    )
    titulo = models.CharField(max_length=200)
    observacion = models.TextField(null=True, blank=True)
    urgente = models.BooleanField(default=False)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="BORRADOR")
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada_en"]
        verbose_name = "Solicitud de cotizaciÃ³n"
        verbose_name_plural = "Solicitudes de cotizaciÃ³n"
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
        _normalizar_textos(self, ("titulo", "observacion"))
        self._completar_sucursal()
        errores = {}
        if not self.orden_id:
            errores["orden"] = "La orden de trabajo es obligatoria."
        elif self.sucursal_id:
            try:
                if self.orden.sucursal_id != self.sucursal_id:
                    errores["sucursal"] = (
                        "La sucursal debe coincidir con la sucursal de la OT."
                    )
            except ObjectDoesNotExist:
                errores["orden"] = "La orden de trabajo no existe."
        if not self.titulo:
            errores["titulo"] = "El tÃ­tulo es obligatorio."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        _normalizar_textos(self, ("titulo", "observacion"))
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
        return CotizacionProveedor.objects.filter(item__solicitud_id=self.pk).count()

    def actualizar_estado(self):
        """Resume los estados actuales de los Ã­tems; respeta la cancelaciÃ³n."""
        if not self.pk:
            return
        using = self._state.db or "default"
        with transaction.atomic(using=using):
            actual = type(self).objects.using(using).select_for_update().get(pk=self.pk)
            if actual.estado == "CANCELADA":
                self.estado = actual.estado
                return
            estados = list(actual.items.values_list("estado_abastecimiento", flat=True))
            if estados and all(estado == "COMPRADO" for estado in estados):
                nuevo = "COMPRADA"
            elif estados and all(estado in {"SELECCIONADO", "COMPRADO"} for estado in estados):
                nuevo = "DECIDIDA"
            elif any(estado in {"COTIZADO", "SELECCIONADO", "COMPRADO"} for estado in estados):
                nuevo = "RESPONDIDA"
            elif CotizacionProveedor.objects.using(using).filter(
                item__solicitud_id=self.pk, estado="ENVIADA"
            ).exists():
                nuevo = "ENVIADA"
            else:
                nuevo = "BORRADOR"
            momento = timezone.now()
            type(self).objects.using(using).filter(pk=self.pk).update(
                estado=nuevo, actualizada_en=momento
            )
            self.estado = nuevo
            self.actualizada_en = momento

    def __str__(self):
        return f"{self.orden.numero_orden} - {self.titulo}"


# ==========================================
# 3. ÃTEM / REPUESTO A COTIZAR
# ==========================================
class ItemSolicitudCotizacion(models.Model):
    UNIDADES = [
        ("POR_DEFINIR", "Por definir"),
        ("UNIDAD", "Unidad"),
        ("PAR", "Par"),
        ("JUEGO", "Juego"),
        ("KIT", "Kit"),
    ]
    LADOS = [
        ("POR_DEFINIR", "Por definir"),
        ("NO_APLICA", "No aplica"),
        ("IZQUIERDO", "Izquierdo / LH"),
        ("DERECHO", "Derecho / RH"),
        ("AMBOS", "Ambos"),
    ]
    POSICIONES = [
        ("POR_DEFINIR", "Por definir"),
        ("NO_APLICA", "No aplica"),
        ("DELANTERA", "Delantera"),
        ("TRASERA", "Trasera"),
        ("SUPERIOR", "Superior"),
        ("INFERIOR", "Inferior"),
    ]
    ESTADOS_ABASTECIMIENTO = [
        ("POR_REVISAR", "Por revisar"),
        ("PENDIENTE", "Por cotizar"),
        ("COTIZADO", "Cotizado"),
        ("SELECCIONADO", "Oferta seleccionada"),
        ("COMPRADO", "Comprado"),
    ]

    solicitud = models.ForeignKey(
        SolicitudCotizacion, on_delete=models.CASCADE, related_name="items"
    )
    producto_rel = models.ForeignKey(
        "inventario.Producto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items_cotizacion",
    )
    codigo_producto_rel = models.ForeignKey(
        "inventario.CodigoProducto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items_cotizacion",
    )
    descripcion_solicitada = models.CharField(max_length=255)
    codigo_referencia = models.CharField(max_length=100, null=True, blank=True)
    codigo_barras = models.CharField(max_length=255, null=True, blank=True)
    marca_referencia = models.CharField(max_length=100, null=True, blank=True)
    categoria_referencia = models.CharField(max_length=100, null=True, blank=True)
    cantidad = models.PositiveIntegerField(default=1)
    unidad = models.CharField(max_length=15, choices=UNIDADES, default="POR_DEFINIR")
    medida_solicitada = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="EspecificaciÃ³n tÃ©cnica: STD, +10, +20, etc.",
    )
    lado = models.CharField(max_length=15, choices=LADOS, default="POR_DEFINIR")
    posicion = models.CharField(max_length=15, choices=POSICIONES, default="POR_DEFINIR")
    estado_abastecimiento = models.CharField(
        max_length=20,
        choices=ESTADOS_ABASTECIMIENTO,
        default="POR_REVISAR",
        db_index=True,
    )
    # Se conserva el dato existente. Es una referencia de stock, no una reserva.
    stock_actual_sucursal = models.PositiveIntegerField(default=0)
    requiere_compra = models.BooleanField(default=True)
    observacion = models.TextField(null=True, blank=True)
    orden_item = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Ãtem de solicitud"
        verbose_name_plural = "Ãtems de solicitud"
        indexes = [
            models.Index(fields=["codigo_referencia"]),
            models.Index(fields=["codigo_barras"]),
            models.Index(fields=["marca_referencia"]),
            models.Index(fields=["categoria_referencia"]),
        ]

    def _normalizar_textos(self):
        _normalizar_textos(
            self,
            (
                "descripcion_solicitada", "codigo_referencia", "codigo_barras",
                "marca_referencia", "categoria_referencia", "medida_solicitada",
                "observacion",
            ),
            ("codigo_referencia", "marca_referencia", "categoria_referencia", "medida_solicitada"),
        )
        self.descripcion_solicitada = self.descripcion_solicitada or ""
        self.medida_solicitada = self.medida_solicitada or ""

    def clean(self):
        super().clean()
        self._normalizar_textos()
        errores = {}
        if not self.descripcion_solicitada:
            errores["descripcion_solicitada"] = "La descripciÃ³n del repuesto es obligatoria."
        if self.cantidad is None:
            errores["cantidad"] = "La cantidad es obligatoria."
        elif isinstance(self.cantidad, int) and self.cantidad <= 0:
            errores["cantidad"] = "La cantidad debe ser mayor que 0."
        if self.stock_actual_sucursal is None:
            errores["stock_actual_sucursal"] = "El stock actual es obligatorio."
        elif isinstance(self.stock_actual_sucursal, int) and self.stock_actual_sucursal < 0:
            errores["stock_actual_sucursal"] = "El stock actual no puede ser negativo."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return
            kwargs["update_fields"] = update_fields
        self._normalizar_textos()
        self.full_clean()
        self.requiere_compra = self.faltante > 0
        if update_fields is not None and {"cantidad", "stock_actual_sucursal"} & update_fields:
            update_fields.add("requiere_compra")
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            anterior = (
                type(self).objects.using(using).filter(pk=self.pk).first()
                if self.pk else None
            )
            solicitud_id = anterior.solicitud_id if anterior else self.solicitud_id
            solicitud = SolicitudCotizacion.objects.using(using).select_for_update().get(
                pk=solicitud_id
            )
            if solicitud.estado == "CANCELADA" or solicitud.orden.estado == "ANULADA":
                raise ValidationError("La solicitud o su orden de trabajo estÃ¡ cancelada.")
            if anterior is not None:
                anterior = type(self).objects.using(using).select_for_update().get(pk=self.pk)
                if anterior.solicitud_id != self.solicitud_id:
                    raise ValidationError("El repuesto debe permanecer en su solicitud original.")
                if anterior.estado_abastecimiento == "COMPRADO":
                    permitidos = {"id", "observacion", "orden_item", "requiere_compra"}
                    for campo in self._meta.concrete_fields:
                        if campo.name not in permitidos and (
                            getattr(anterior, campo.attname) != getattr(self, campo.attname)
                        ):
                            raise ValidationError(
                                "El repuesto comprado solo permite editar observaciÃ³n y orden."
                            )
                modificados = {
                    campo.name for campo in self._meta.concrete_fields
                    if getattr(anterior, campo.attname) != getattr(self, campo.attname)
                    and (
                        update_fields is None
                        or campo.name in update_fields
                        or campo.attname in update_fields
                    )
                }
                requisitos = {
                    "cantidad", "unidad", "medida_solicitada", "lado", "posicion",
                    "descripcion_solicitada", "producto_rel", "codigo_producto_rel",
                    "codigo_referencia", "marca_referencia",
                }
                if modificados & requisitos:
                    CotizacionProveedor.objects.using(using).filter(
                        item_id=self.pk, estado="GANADORA"
                    ).update(estado="RESPONDIO")
                if "unidad" in modificados:
                    CotizacionProveedor.objects.using(using).filter(item_id=self.pk).update(
                        unidades_por_presentacion=None
                    )
            if self.estado_abastecimiento == "COMPRADO":
                ganadora = self.cotizacion_seleccionada
                if ganadora is None or not ganadora.es_comparable:
                    raise ValidationError("Selecciona una oferta completa antes de confirmar la compra.")
            resultado = super().save(*args, **kwargs)
            getattr(self, "_prefetched_objects_cache", {}).pop("cotizaciones_proveedor", None)
            self.actualizar_estado_abastecimiento()
            solicitud.actualizar_estado()
            return resultado

    @property
    def faltante(self):
        """Diferencia respecto al stock de referencia; no reserva existencias."""
        return max((self.cantidad or 0) - (self.stock_actual_sucursal or 0), 0)

    def _ofertas(self):
        if not self.pk:
            return []
        cache = getattr(self, "_prefetched_objects_cache", {})
        if "cotizaciones_proveedor" in cache:
            ofertas = list(cache["cotizaciones_proveedor"])
        else:
            ofertas = list(self.cotizaciones_proveedor.all())
        for oferta in ofertas:
            oferta.item = self
        return ofertas

    @property
    def cotizacion_seleccionada(self):
        return next((oferta for oferta in self._ofertas() if oferta.estado == "GANADORA"), None)

    @property
    def mejor_cotizacion(self):
        """Menor costo total comparable para la cantidad solicitada."""
        candidatas = []
        for oferta in self._ofertas():
            costo = oferta.costo_requerimiento
            if costo is not None:
                candidatas.append((costo, -oferta.calidad_referencial, oferta.pk, oferta))
        return min(candidatas, key=lambda fila: fila[:3])[3] if candidatas else None

    def actualizar_estado_abastecimiento(self):
        if not self.pk:
            return
        using = self._state.db or "default"
        actual = type(self).objects.using(using).get(pk=self.pk)
        if actual.estado_abastecimiento == "COMPRADO":
            self.estado_abastecimiento = "COMPRADO"
            return
        ofertas = actual.cotizaciones_proveedor.using(using)
        if ofertas.filter(estado="GANADORA").exists():
            nuevo = "SELECCIONADO"
        elif ofertas.filter(estado="RESPONDIO").exists():
            nuevo = "COTIZADO"
        elif ofertas.exists():
            nuevo = "PENDIENTE"
        else:
            nuevo = "PENDIENTE" if actual.estado_abastecimiento == "PENDIENTE" else "POR_REVISAR"
        type(self).objects.using(using).filter(pk=self.pk).update(estado_abastecimiento=nuevo)
        self.estado_abastecimiento = nuevo

    def marcar_comprado(self):
        """Registra la confirmaciÃ³n de compra de la oferta elegida."""
        if not self.pk:
            raise ValidationError("Primero debes guardar el repuesto.")
        using = self._state.db or "default"
        with transaction.atomic(using=using):
            solicitud = SolicitudCotizacion.objects.using(using).select_for_update().get(
                pk=self.solicitud_id
            )
            if solicitud.estado == "CANCELADA" or solicitud.orden.estado == "ANULADA":
                raise ValidationError("La solicitud o su orden de trabajo estÃ¡ cancelada.")
            actual = type(self).objects.using(using).select_for_update().get(pk=self.pk)
            ganadora = actual.cotizacion_seleccionada
            if ganadora is None or not ganadora.es_comparable:
                raise ValidationError("Selecciona una oferta disponible y completa antes de comprar.")
            type(self).objects.using(using).filter(pk=self.pk).update(
                estado_abastecimiento="COMPRADO"
            )
            self.estado_abastecimiento = "COMPRADO"
            solicitud.actualizar_estado()

    @property
    def clase_estado(self):
        return {
            "POR_REVISAR": "bg-secondary text-white",
            "PENDIENTE": "bg-warning text-dark",
            "COTIZADO": "bg-info text-dark",
            "SELECCIONADO": "bg-primary text-white",
            "COMPRADO": "bg-success text-white",
        }.get(self.estado_abastecimiento, "bg-secondary text-white")

    def __str__(self):
        return self.descripcion_solicitada or "Repuesto sin descripciÃ³n"


# ==========================================
# 4. FOTOS DEL ÃTEM
# ==========================================
class FotoItemCotizacion(models.Model):
    item = models.ForeignKey(
        ItemSolicitudCotizacion, on_delete=models.CASCADE, related_name="fotos"
    )
    imagen = models.ImageField(upload_to="cotizaciones/items/")
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_subida", "id"]
        verbose_name = "Foto de Ã­tem a cotizar"
        verbose_name_plural = "Fotos de Ã­tems a cotizar"

    def save(self, *args, **kwargs):
        _normalizar_textos(self, ("descripcion",))
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Foto item {self.item_id}"


# ==========================================
# 5. OFERTAS DE PROVEEDORES
# ==========================================
class CotizacionProveedor(models.Model):
    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("ENVIADA", "Enviada"),
        ("RESPONDIO", "RespondiÃ³"),
        ("DESCARTADA", "Descartada"),
        ("GANADORA", "Ganadora"),
    ]
    TRATAMIENTOS_IVA = [
        ("POR_DEFINIR", "Por confirmar"),
        ("INCLUIDO", "Incluido en el precio"),
        ("ADICIONAL", "Se suma al precio"),
        ("SIN_IVA", "Cotizado sin IVA aplicable"),
    ]

    item = models.ForeignKey(
        ItemSolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="cotizaciones_proveedor",
    )
    proveedor = models.ForeignKey(
        "compras.Proveedor",
        on_delete=models.PROTECT,
        related_name="cotizaciones_emitidas",
    )
    numero_opcion = models.PositiveIntegerField(default=1)
    tipo_proveedor = models.CharField(
        max_length=10, choices=ProveedorEspecialidad.TIPOS_PROVEEDOR, default="MENOR"
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Precio de UNA presentaciÃ³n ofrecida: unidad, par, juego o kit.",
    )
    marca_ofertada = models.CharField(max_length=100, blank=True, default="")
    medida_ofertada = models.CharField(max_length=100, blank=True, default="")
    presentacion = models.CharField(
        max_length=15,
        choices=ItemSolicitudCotizacion.UNIDADES,
        default="POR_DEFINIR",
    )
    unidades_por_presentacion = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text=(
            "Cantidad de la unidad SOLICITADA cubierta por una presentaciÃ³n. "
            "Ej.: solicitas unidades y ofrecen un par: 2; la misma unidad: 1."
        ),
    )
    contenido_presentacion = models.CharField(max_length=255, blank=True, default="")
    tratamiento_iva = models.CharField(
        max_length=15, choices=TRATAMIENTOS_IVA, default="POR_DEFINIR"
    )
    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        help_text="Porcentaje informado por el proveedor cuando el IVA es adicional.",
    )
    disponible = models.BooleanField(null=True, blank=True, default=None)
    tiempo_entrega = models.CharField(max_length=100, null=True, blank=True)
    calidad_referencial = models.PositiveSmallIntegerField(
        default=3, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    observacion = models.TextField(null=True, blank=True)
    whatsapp_destino = models.CharField(max_length=30, null=True, blank=True)
    mensaje_generado = models.TextField(null=True, blank=True)
    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="PENDIENTE")

    class Meta:
        ordering = ["item", "estado", "precio", "id"]
        verbose_name = "CotizaciÃ³n de proveedor"
        verbose_name_plural = "Cotizaciones de proveedores"
        constraints = [
            models.UniqueConstraint(
                fields=["item", "proveedor", "numero_opcion"],
                name="uq_cotizacion_item_proveedor_opcion",
            ),
            models.UniqueConstraint(
                fields=["item"],
                condition=models.Q(estado="GANADORA"),
                name="uq_cotizacion_ganadora_item",
            ),
        ]
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["proveedor", "estado"]),
            models.Index(fields=["precio"]),
        ]

    def _normalizar_textos(self):
        _normalizar_textos(
            self,
            (
                "marca_ofertada", "medida_ofertada", "contenido_presentacion",
                "tiempo_entrega", "observacion", "whatsapp_destino", "mensaje_generado",
            ),
            ("marca_ofertada", "medida_ofertada"),
        )
        self.marca_ofertada = self.marca_ofertada or ""
        self.medida_ofertada = self.medida_ofertada or ""
        self.contenido_presentacion = self.contenido_presentacion or ""

    def clean(self):
        super().clean()
        self._normalizar_textos()
        errores = {}
        if isinstance(self.numero_opcion, int) and self.numero_opcion <= 0:
            errores["numero_opcion"] = "El nÃºmero de opciÃ³n debe ser mayor que 0."
        if self.tratamiento_iva == "ADICIONAL" and self.porcentaje_iva is None:
            errores["porcentaje_iva"] = "Indica el porcentaje de IVA adicional."
        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).values("item_id").first()
            if anterior and anterior["item_id"] != self.item_id:
                errores["item"] = "La oferta debe permanecer en su repuesto original."
        if self.estado == "GANADORA":
            if not self.es_comparable:
                errores["estado"] = (
                    "Completa precio, disponibilidad, presentaciÃ³n, equivalencia, "
                    "IVA y medida compatible antes de seleccionar esta oferta."
                )
            if self.item_id and type(self).objects.filter(
                item_id=self.item_id, estado="GANADORA"
            ).exclude(pk=self.pk).exists():
                errores["estado"] = "Ya existe una oferta seleccionada para este repuesto."
        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return
            kwargs["update_fields"] = update_fields
        self._normalizar_textos()
        using = kwargs.get("using") or self._state.db or "default"
        with transaction.atomic(using=using):
            if self.item_id:
                try:
                    item = ItemSolicitudCotizacion.objects.using(using).get(pk=self.item_id)
                except ItemSolicitudCotizacion.DoesNotExist:
                    item = None
                if item is not None:
                    solicitud = SolicitudCotizacion.objects.using(using).select_for_update().get(
                        pk=item.solicitud_id
                    )
                    if solicitud.estado == "CANCELADA" or solicitud.orden.estado == "ANULADA":
                        raise ValidationError("La solicitud o su orden de trabajo estÃ¡ cancelada.")
                    item = ItemSolicitudCotizacion.objects.using(using).select_for_update().get(
                        pk=self.item_id
                    )
                    self.item = item
                    if item.estado_abastecimiento == "COMPRADO":
                        raise ValidationError("Las ofertas de un repuesto comprado quedan bloqueadas.")
            self.full_clean()
            resultado = super().save(*args, **kwargs)
            self.item.actualizar_estado_abastecimiento()
            self.item.solicitud.actualizar_estado()
            return resultado

    @property
    def _factor_iva(self):
        if self.tratamiento_iva in {"INCLUIDO", "SIN_IVA"}:
            return Decimal("1")
        if self.tratamiento_iva == "ADICIONAL" and self.porcentaje_iva is not None:
            porcentaje = self.porcentaje_iva
            if (
                isinstance(porcentaje, Decimal)
                and porcentaje.is_finite()
                and Decimal("0") <= porcentaje <= Decimal("100")
            ):
                return Decimal("1") + porcentaje / Decimal("100")
        return None

    @property
    def medida_compatible(self):
        if not self.item_id:
            return False
        try:
            solicitada = (self.item.medida_solicitada or "").strip().upper()
        except ObjectDoesNotExist:
            return False
        ofrecida = (self.medida_ofertada or "").strip().upper()
        return not solicitada or solicitada == ofrecida

    @property
    def es_comparable(self):
        if not self.item_id or self.estado not in {"RESPONDIO", "GANADORA"}:
            return False
        try:
            unidad_solicitada = self.item.unidad
            cantidad_solicitada = self.item.cantidad
        except ObjectDoesNotExist:
            return False
        return (
            self.disponible is True
            and isinstance(self.precio, Decimal)
            and self.precio.is_finite()
            and self.precio >= 0
            and isinstance(cantidad_solicitada, int)
            and cantidad_solicitada > 0
            and unidad_solicitada in {"UNIDAD", "PAR", "JUEGO", "KIT"}
            and self.presentacion in {"UNIDAD", "PAR", "JUEGO", "KIT"}
            and isinstance(self.unidades_por_presentacion, Decimal)
            and self.unidades_por_presentacion.is_finite()
            and self.unidades_por_presentacion > 0
            and self._factor_iva is not None
            and self.medida_compatible
        )

    @property
    def precio_con_iva(self):
        """Precio final de una presentaciÃ³n; el total se redondea por separado."""
        factor = self._factor_iva
        if (
            not isinstance(self.precio, Decimal)
            or not self.precio.is_finite()
            or self.precio < 0
            or factor is None
        ):
            return None
        return (self.precio * factor).quantize(CENTAVO, rounding=ROUND_HALF_UP)

    @property
    def presentaciones_necesarias(self):
        if not self.es_comparable:
            return None
        cantidad = Decimal(self.item.cantidad)
        return int((cantidad / self.unidades_por_presentacion).to_integral_value(
            rounding=ROUND_CEILING
        ))

    @property
    def costo_requerimiento(self):
        """Costo para toda la cantidad solicitada, comprando presentaciones completas.

        No descuenta stock general: consultar stock no reserva ese inventario.
        No incluye flete ni distribuye automÃ¡ticamente kits entre varios Ã­tems.
        """
        presentaciones = self.presentaciones_necesarias
        if presentaciones is None:
            return None
        total = self.precio * Decimal(presentaciones) * self._factor_iva
        return total.quantize(CENTAVO, rounding=ROUND_HALF_UP)

    @property
    def score_simple(self):
        costo = self.costo_requerimiento
        if costo is None:
            return Decimal("Infinity")
        return costo * Decimal("0.70") - Decimal(self.calidad_referencial) * Decimal("2.00")

    def marcar_enviada(self):
        self.estado = "ENVIADA"
        self.fecha_envio = timezone.now()
        self.save(update_fields=["estado", "fecha_envio"])

    def marcar_respondida(self):
        self.estado = "RESPONDIO"
        self.fecha_respuesta = timezone.now()
        self.save(update_fields=["estado", "fecha_respuesta"])

    def seleccionar(self):
        if not self.pk:
            raise ValidationError("Primero debes guardar la oferta.")
        using = self._state.db or "default"
        with transaction.atomic(using=using):
            solicitud = SolicitudCotizacion.objects.using(using).select_for_update().get(
                pk=self.item.solicitud_id
            )
            item = ItemSolicitudCotizacion.objects.using(using).select_for_update().get(
                pk=self.item_id
            )
            if solicitud.estado == "CANCELADA" or solicitud.orden.estado == "ANULADA":
                raise ValidationError("La solicitud o su orden de trabajo estÃ¡ cancelada.")
            if item.estado_abastecimiento == "COMPRADO":
                raise ValidationError("El repuesto ya estÃ¡ comprado.")
            actual = type(self).objects.using(using).get(pk=self.pk)
            actual.item = item
            if not actual.es_comparable:
                raise ValidationError("La oferta todavÃ­a no es comparable o no estÃ¡ disponible.")
            type(self).objects.using(using).filter(
                item_id=item.pk, estado="GANADORA"
            ).exclude(pk=self.pk).update(estado="RESPONDIO")
            actual.estado = "GANADORA"
            actual.save(using=using, update_fields=["estado"])
            self.estado = "GANADORA"

    def __str__(self):
        nombre = (
            self.proveedor.empresa
            or self.proveedor.nombre_contacto
            or f"Proveedor {self.proveedor_id}"
        )
        return f"{nombre} - {self.item.descripcion_solicitada} - OpciÃ³n {self.numero_opcion}"


# ==========================================
# 6. DECISIÃ“N GLOBAL EXISTENTE
# ==========================================
class DecisionCotizacion(models.Model):
    """Modelo existente, conservado por compatibilidad.

    La torre elige una CotizacionProveedor por cada repuesto mediante
    seleccionar(). Este modelo no determina esas elecciones individuales.
    """

    solicitud = models.OneToOneField(
        SolicitudCotizacion, on_delete=models.CASCADE, related_name="decision_final"
    )
    proveedor_seleccionado = models.ForeignKey(
        "compras.Proveedor", on_delete=models.PROTECT, related_name="decisiones_ganadas"
    )
    motivo = models.TextField(null=True, blank=True)
    precio_total = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    decidida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="decisiones_cotizacion_tomadas",
    )
    decidida_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decidida_en"]
        verbose_name = "DecisiÃ³n de cotizaciÃ³n"
        verbose_name_plural = "Decisiones de cotizaciÃ³n"

    def clean(self):
        super().clean()
        _normalizar_textos(self, ("motivo",))

    def save(self, *args, **kwargs):
        _normalizar_textos(self, ("motivo",))
        self.full_clean()
        # El estado de la torre se obtiene de los repuestos, no de un proveedor global.
        return super().save(*args, **kwargs)

    def __str__(self):
        nombre = (
            self.proveedor_seleccionado.empresa
            or self.proveedor_seleccionado.nombre_contacto
        )
        return f"{self.solicitud} -> {nombre}"