from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import uuid


# ==========================================
# 1. PROVEEDOR ESPECIALIDAD / REGLAS DE COTIZACIÓN
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

    prioridad = models.PositiveIntegerField(
        default=1,
    
    )

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
        if self.categoria:
            self.categoria = self.categoria.strip().upper()

        if self.marca:
            self.marca = self.marca.strip().upper()

        if self.prioridad <= 0:
            raise ValidationError("La prioridad debe ser mayor que 0.")

    def save(self, *args, **kwargs):
        if self.categoria:
            self.categoria = self.categoria.strip().upper()

        if self.marca:
            self.marca = self.marca.strip().upper()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        base = self.proveedor.empresa or self.proveedor.nombre_contacto or f"Proveedor {self.proveedor_id}"
        extras = []
        if self.categoria:
            extras.append(self.categoria)
        if self.marca:
            extras.append(self.marca)

        extra_txt = " | ".join(extras) if extras else "Sin filtro"
        return f"{base} - {self.get_tipo_proveedor_display()} - {extra_txt}"


# ==========================================
# 2. SOLICITUD DE COTIZACIÓN (CABECERA)
# ==========================================
class SolicitudCotizacion(models.Model):
    ESTADOS = [
        ("BORRADOR", "Borrador"),
        ("ENVIADA", "Enviada"),
        ("RESPONDIDA", "Con respuestas"),
        ("DECIDIDA", "Decidida"),
        ("COMPRADA", "Comprada / pedida"),
        ("PARCIAL", "Recibida parcialmente"),
        ("RECIBIDA", "Recibida"),
        ("CANCELADA", "Cancelada"),
    ]

    tipo_trabajo = models.CharField(max_length=20, default="MECANICA", choices=[
        ("MECANICA", "Mecánica"), ("MOTOR", "Reparación de motor"),
        ("CARROCERIA", "Carrocería / pintura"), ("OTRO", "Otro"),
    ])

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

    titulo = models.CharField(
        max_length=200,
  
    )

    observacion = models.TextField(null=True, blank=True)
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

    def clean(self):
        if self.titulo:
            self.titulo = self.titulo.strip()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if not self.orden_id:
            raise ValidationError({"orden": "La orden de trabajo es obligatoria."})

        if not self.sucursal_id and self.orden_id:
            self.sucursal = self.orden.sucursal

        if self.orden_id and self.sucursal_id and self.orden.sucursal_id != self.sucursal_id:
            raise ValidationError("La sucursal de la solicitud debe coincidir con la sucursal de la OT.")

    def save(self, *args, **kwargs):
        if self.titulo:
            self.titulo = self.titulo.strip()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if not self.sucursal_id and self.orden_id:
            self.sucursal = self.orden.sucursal

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def total_items(self):
        return self.items.count()

    @property
    def total_cotizaciones(self):
        return CotizacionProveedor.objects.filter(item__solicitud=self).count()

    def __str__(self):
        return f"{self.orden.numero_orden} - {self.titulo}"


# ==========================================
# 3. ÍTEM / REPUESTO A COTIZAR
# ==========================================
class ItemSolicitudCotizacion(models.Model):
    solicitud = models.ForeignKey(
        SolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="items",
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

    codigo_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        
    )

    codigo_barras = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    marca_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    categoria_referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    cantidad = models.PositiveIntegerField(default=1)
    unidad = models.CharField(max_length=15, blank=True, default="", choices=[
        ("", "Por confirmar"), ("UNIDAD", "Unidad"), ("PAR", "Par"),
        ("JUEGO", "Juego"), ("KIT", "Kit"),
    ])
    medida_solicitada = models.CharField(max_length=100, blank=True, default="")
    medida_confirmada = models.BooleanField(default=False)
    cantidad_bodega = models.PositiveIntegerField(default=0)
    estado_abastecimiento = models.CharField(max_length=20, default="PENDIENTE", choices=[
        ("PENDIENTE", "Pendiente"), ("SELECCIONADO", "Proveedor elegido"),
        ("PEDIDO", "Pedido"), ("PARCIAL", "Recibido parcialmente"),
        ("RECIBIDO", "Recibido"),
    ])
    cantidad_pedida = models.PositiveIntegerField(null=True, blank=True)
    costo_acordado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pedido_en = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveIntegerField(default=1)

    stock_actual_sucursal = models.PositiveIntegerField(default=0)

    requiere_compra = models.BooleanField(default=True)

    observacion = models.TextField(null=True, blank=True)

    orden_item = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden_item", "id"]
        verbose_name = "Ítem de solicitud"
        verbose_name_plural = "Ítems de solicitud"
        indexes = [
            models.Index(fields=["codigo_referencia"]),
            models.Index(fields=["codigo_barras"]),
            models.Index(fields=["marca_referencia"]),
            models.Index(fields=["categoria_referencia"]),
        ]

    def clean(self):
        if self.descripcion_solicitada:
            self.descripcion_solicitada = self.descripcion_solicitada.strip()

        if self.codigo_referencia:
            self.codigo_referencia = self.codigo_referencia.strip().upper()

        if self.codigo_barras:
            self.codigo_barras = self.codigo_barras.strip()

        if self.marca_referencia:
            self.marca_referencia = self.marca_referencia.strip().upper()

        if self.categoria_referencia:
            self.categoria_referencia = self.categoria_referencia.strip().upper()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if not self.descripcion_solicitada:
            raise ValidationError({"descripcion_solicitada": "La descripción del repuesto es obligatoria."})

        if self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor que 0."})

        if self.cantidad_bodega > self.cantidad:
            raise ValidationError({"cantidad_bodega": "La cantidad de bodega supera la requerida."})
        if self.pk and self.cantidad < self.cantidad_bodega + self.total_recibido:
            raise ValidationError({"cantidad": "No puede ser menor que lo abastecido y recibido."})

        if self.stock_actual_sucursal < 0:
            raise ValidationError({"stock_actual_sucursal": "El stock actual no puede ser negativo."})

    def save(self, *args, **kwargs):
        if self.descripcion_solicitada:
            self.descripcion_solicitada = self.descripcion_solicitada.strip()

        if self.codigo_referencia:
            self.codigo_referencia = self.codigo_referencia.strip().upper()

        if self.codigo_barras:
            self.codigo_barras = self.codigo_barras.strip()

        if self.marca_referencia:
            self.marca_referencia = self.marca_referencia.strip().upper()

        if self.categoria_referencia:
            self.categoria_referencia = self.categoria_referencia.strip().upper()

        if self.observacion:
            self.observacion = self.observacion.strip()

        self.requiere_compra = self.cantidad > self.stock_actual_sucursal

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def faltante(self):
        faltante = self.cantidad - self.stock_actual_sucursal
        return faltante if faltante > 0 else 0

    @property
    def total_recibido(self):
        if "recepciones" in getattr(self, "_prefetched_objects_cache", {}):
            return sum(r.cantidad for r in self.recepciones.all() if not r.anulada_en)
        return self.recepciones.filter(anulada_en__isnull=True).aggregate(total=models.Sum("cantidad"))["total"] or 0

    @property
    def pendiente_recepcion(self):
        return max(self.cantidad - self.cantidad_bodega - self.total_recibido, 0)

    @property
    def cotizacion_elegida(self):
        return self.cotizaciones_proveedor.filter(estado="GANADORA").first()

    @property
    def mejor_cotizacion(self):
        opciones = [q for q in self.cotizaciones_proveedor.all() if q.costo_requerimiento is not None]
        return min(opciones, key=lambda q: q.costo_requerimiento, default=None)

    def __str__(self):
        return self.descripcion_solicitada


# ==========================================
# 4. FOTOS DEL ÍTEM A COTIZAR
# ==========================================
class FotoItemCotizacion(models.Model):
    item = models.ForeignKey(
        ItemSolicitudCotizacion,
        on_delete=models.CASCADE,
        related_name="fotos",
    )

    imagen = models.ImageField(upload_to="cotizaciones/items/")
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_subida", "id"]
        verbose_name = "Foto de ítem a cotizar"
        verbose_name_plural = "Fotos de ítems a cotizar"

    def save(self, *args, **kwargs):
        if self.descripcion:
            self.descripcion = self.descripcion.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Foto item {self.item_id}"


# ==========================================
# 5. COTIZACIÓN POR PROVEEDOR
# ==========================================
class CotizacionProveedor(models.Model):
    ESTADOS = [
        ("PENDIENTE", "Pendiente"),
        ("ENVIADA", "Enviada"),
        ("RESPONDIO", "Respondió"),
        ("DESCARTADA", "Descartada"),
        ("GANADORA", "Ganadora"),
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

    tipo_proveedor = models.CharField(
        max_length=10,
        choices=ProveedorEspecialidad.TIPOS_PROVEEDOR,
        default="MENOR",
    )

    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    disponible = models.BooleanField(null=True, blank=True, default=None)
    numero_opcion = models.PositiveSmallIntegerField(default=1)
    marca_ofertada = models.CharField(max_length=100, blank=True, default="")
    medida_ofertada = models.CharField(max_length=100, blank=True, default="")
    presentacion = models.CharField(max_length=15, blank=True, default="", choices=ItemSolicitudCotizacion._meta.get_field("unidad").choices)
    unidades_por_presentacion = models.PositiveIntegerField(null=True, blank=True,
        help_text="Cuántas unidades de la solicitud cubre una presentación cotizada.")
    tratamiento_iva = models.CharField(max_length=15, blank=True, default="", choices=[
        ("", "Por confirmar"), ("INCLUIDO", "Incluido en el costo"), ("ADICIONAL", "Se suma al costo"),
    ])
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    contenido = models.CharField(max_length=255, blank=True, default="",
        help_text="Piezas incluidas, por ejemplo pistones con rines.")
    revision = models.PositiveIntegerField(default=1)

    tiempo_entrega = models.CharField(
        max_length=100,
        null=True,
        blank=True,
       
    )

    calidad_referencial = models.PositiveSmallIntegerField(
        default=3,
    
    )

    observacion = models.TextField(null=True, blank=True)

    whatsapp_destino = models.CharField(max_length=30, null=True, blank=True)
    mensaje_generado = models.TextField(null=True, blank=True)

    fecha_envio = models.DateTimeField(null=True, blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="PENDIENTE",
    )

    class Meta:
        ordering = ["item", "estado", "precio", "id"]
        verbose_name = "Cotización de proveedor"
        verbose_name_plural = "Cotizaciones de proveedores"
        constraints = [
            models.UniqueConstraint(
                fields=["item", "proveedor", "numero_opcion"],
                name="uq_cotizacion_item_prov_opcion",
            ),
            models.UniqueConstraint(fields=["item"], condition=models.Q(estado="GANADORA"),
                name="uq_cotizacion_ganadora_item"),
            models.CheckConstraint(condition=models.Q(precio__isnull=True) | models.Q(precio__gte=0),
                name="cotizacion_precio_no_negativo"),

        ]
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["proveedor", "estado"]),
            models.Index(fields=["precio"]),
        ]

    def clean(self):
        if self.tratamiento_iva == "ADICIONAL" and self.porcentaje_iva is None:
            raise ValidationError({"porcentaje_iva": "Confirma el porcentaje de IVA."})
        if self.porcentaje_iva is not None and not Decimal("0") <= self.porcentaje_iva <= Decimal("100"):
            raise ValidationError({"porcentaje_iva": "El porcentaje debe estar entre 0 y 100."})
        if self.unidades_por_presentacion is not None and self.unidades_por_presentacion < 1:
            raise ValidationError({"unidades_por_presentacion": "Debe ser mayor que cero."})
        if self.numero_opcion < 1:
            raise ValidationError({"numero_opcion": "Debe ser mayor que cero."})
        if self.whatsapp_destino:
            self.whatsapp_destino = self.whatsapp_destino.strip()

        if self.mensaje_generado:
            self.mensaje_generado = self.mensaje_generado.strip()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if self.tiempo_entrega:
            self.tiempo_entrega = self.tiempo_entrega.strip()

        if self.precio is not None and self.precio < 0:
            raise ValidationError({"precio": "El precio no puede ser negativo."})

        if self.calidad_referencial < 1 or self.calidad_referencial > 5:
            raise ValidationError({"calidad_referencial": "La calidad debe estar entre 1 y 5."})

        if self.estado == "GANADORA":
            existe_ganadora = CotizacionProveedor.objects.filter(
                item=self.item,
                estado="GANADORA",
            ).exclude(pk=self.pk).exists()

            if existe_ganadora:
                raise ValidationError("Ya existe una cotización ganadora para este ítem.")

    def save(self, *args, **kwargs):
        if self.whatsapp_destino:
            self.whatsapp_destino = self.whatsapp_destino.strip()

        if self.mensaje_generado:
            self.mensaje_generado = self.mensaje_generado.strip()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if self.tiempo_entrega:
            self.tiempo_entrega = self.tiempo_entrega.strip()

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def costo_requerimiento(self):
        """Total with tax for whole quoted packs; unknown conditions stay unknown."""
        item = self.item
        cantidad = max(item.cantidad - item.cantidad_bodega, 0)
        if (self.disponible is not True or self.precio is None or not item.unidad
                or not self.presentacion or not self.unidades_por_presentacion
                or not self.tratamiento_iva or self.estado == "DESCARTADA"):
            return None
        if item.medida_solicitada and (not item.medida_confirmada
                or item.medida_solicitada.strip().upper() != self.medida_ofertada.strip().upper()):
            return None
        if item.marca_referencia and item.marca_referencia.strip().upper() != self.marca_ofertada.strip().upper():
            return None
        if self.tratamiento_iva == "ADICIONAL" and self.porcentaje_iva is None:
            return None
        paquetes = (Decimal(cantidad) / self.unidades_por_presentacion).to_integral_value(rounding=ROUND_CEILING)
        subtotal = (self.precio * paquetes).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
        iva = (subtotal * self.porcentaje_iva / 100).quantize(Decimal(".01"), rounding=ROUND_HALF_UP) if self.tratamiento_iva == "ADICIONAL" else Decimal("0")
        return subtotal + iva

    @property
    def score_simple(self):
        """
        Score básico:
        - precio bajo ayuda
        - calidad alta ayuda
        No reemplaza criterio humano; solo orienta.
        """
        precio = self.precio if self.precio is not None else Decimal("999999.99")
        calidad = Decimal(str(self.calidad_referencial))
        return (precio * Decimal("0.70")) - (calidad * Decimal("2.00"))

    def marcar_enviada(self):
        self.estado = "ENVIADA"
        self.fecha_envio = timezone.now()
        self.save(update_fields=["estado", "fecha_envio"])

    def marcar_respondida(self):
        self.estado = "RESPONDIO"
        self.fecha_respuesta = timezone.now()
        self.save(update_fields=["estado", "fecha_respuesta"])

    def __str__(self):
        base = self.proveedor.empresa or self.proveedor.nombre_contacto or f"Proveedor {self.proveedor_id}"
        return f"{base} - {self.item.descripcion_solicitada}"


# ==========================================
# 6. DECISIÓN FINAL DE LA SOLICITUD
# ==========================================
class DecisionCotizacion(models.Model):
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
        if self.motivo:
            self.motivo = self.motivo.strip()

        if self.precio_total is not None and self.precio_total < 0:
            raise ValidationError({"precio_total": "El precio total no puede ser negativo."})

    def save(self, *args, **kwargs):
        if self.motivo:
            self.motivo = self.motivo.strip()

        self.full_clean()
        super().save(*args, **kwargs)

        solicitud = self.solicitud
        if solicitud.estado != "DECIDIDA":
            solicitud.estado = "DECIDIDA"
            solicitud.save(update_fields=["estado", "actualizada_en"])

    def __str__(self):
        base = self.proveedor_seleccionado.empresa or self.proveedor_seleccionado.nombre_contacto
        return f"{self.solicitud} -> {base}"

class RecepcionRepuesto(models.Model):
    item = models.ForeignKey(ItemSolicitudCotizacion, on_delete=models.PROTECT, related_name="recepciones")
    cotizacion = models.ForeignKey(CotizacionProveedor, on_delete=models.PROTECT, related_name="recepciones")
    cantidad = models.PositiveIntegerField()
    recibida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recibida_en = models.DateTimeField(default=timezone.now)
    anulada_en = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="recepciones_anuladas")
    motivo_anulacion = models.TextField(blank=True, default="")
    comprobante = models.CharField(max_length=100, blank=True, default="")
    observacion = models.TextField(blank=True, default="")
    clave_operacion = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ["-recibida_en", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="recepcion_cantidad_positiva")]

    def clean(self):
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({"cantidad": "Debe ser mayor que cero."})
        if self.cotizacion_id and self.item_id and self.cotizacion.item_id != self.item_id:
            raise ValidationError("La cotización pertenece a otro repuesto.")


class EventoAbastecimiento(models.Model):
    solicitud = models.ForeignKey(SolicitudCotizacion, on_delete=models.PROTECT, related_name="eventos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    accion = models.CharField(max_length=100)
    datos = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
