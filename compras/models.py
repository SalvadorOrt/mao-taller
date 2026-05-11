from decimal import Decimal
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Sum


# =========================================================
# PROVEEDORES
# =========================================================
class Proveedor(models.Model):
    nombre_contacto = models.CharField(max_length=150)
    empresa = models.CharField(max_length=150, blank=True, null=True)
    ciudad = models.CharField(max_length=100, blank=True, null=True)

    telefono = models.CharField(max_length=30, blank=True, null=True)
    
    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Número en formato internacional. Ej: +593999999999",
    )

    tiene_whatsapp = models.BooleanField(default=True)

    email = models.EmailField(blank=True, null=True)
    ruc = models.CharField(max_length=20, blank=True, null=True)

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["empresa", "nombre_contacto"]
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        indexes = [
            models.Index(fields=["empresa"]),
            models.Index(fields=["nombre_contacto"]),
            models.Index(fields=["ruc"]),
        ]

    def clean(self):
        if not self.nombre_contacto or not self.nombre_contacto.strip():
            raise ValidationError("El nombre de contacto es obligatorio.")

        # 🔥 VALIDACIÓN CLAVE PARA WHATSAPP
        if self.whatsapp:
            numero = self.whatsapp.strip()

            if not numero.startswith("+"):
                raise ValidationError({
                    "whatsapp": "Debe estar en formato internacional. Ej: +593999999999"
                })

            if not numero[1:].isdigit():
                raise ValidationError({
                    "whatsapp": "El número solo debe contener dígitos después del +"
                })

    def save(self, *args, **kwargs):
        if self.nombre_contacto:
            self.nombre_contacto = self.nombre_contacto.strip()

        if self.empresa:
            self.empresa = self.empresa.strip()

        if self.ciudad:
            self.ciudad = self.ciudad.strip()

        if self.telefono:
            self.telefono = self.telefono.strip()

        if self.whatsapp:
            self.whatsapp = self.whatsapp.strip().replace(" ", "")

        if self.email:
            self.email = self.email.strip().lower()

        if self.ruc:
            self.ruc = self.ruc.strip()

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def whatsapp_link(self):
        """
        Link directo para abrir WhatsApp Web/API
        """
        if not self.whatsapp:
            return None

        numero = self.whatsapp.replace("+", "")
        return f"https://wa.me/{numero}"

    def __str__(self):
        return self.empresa if self.empresa else self.nombre_contacto


# =========================================================
# FACTURA DE COMPRA (CABECERA + ARCHIVOS)
# =========================================================
class FacturaCompra(models.Model):
    FORMAS_PAGO = [
        ("CONTADO", "Contado"),
        ("CREDITO", "Crédito"),
    ]

    proveedor_rel = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facturas_compra",
        verbose_name="Proveedor relacionado",
    )

    sucursal_destino = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name="facturas_compra",
        verbose_name="Sucursal destino",
    )

    clave_acceso_sri = models.CharField("Clave de Acceso SRI", max_length=49, blank=True, null=True)

    archivo_xml = models.FileField(
        upload_to="facturas/xml/%Y/%m/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["xml"])],
    )
    archivo_pdf = models.FileField(
        upload_to="facturas/pdf/%Y/%m/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )
    imagen_factura = models.ImageField(
        upload_to="facturas/fotos/%Y/%m/",
        blank=True,
        null=True,
    )

    proveedor = models.CharField(max_length=200, blank=True, null=True, verbose_name="Nombre del proveedor")
    ruc = models.CharField(max_length=20, blank=True, null=True, verbose_name="R.U.C.")
    numero_factura = models.CharField(max_length=50, blank=True, null=True, verbose_name="Nº de factura")
    clave_acceso = models.CharField(max_length=100, blank=True, null=True, verbose_name="Clave de acceso / autorización")
    fecha_emision = models.DateField(blank=True, null=True, verbose_name="Fecha emisión")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    forma_pago = models.CharField(max_length=10, choices=FORMAS_PAGO, default="CONTADO")
    dias_plazo = models.PositiveIntegerField(default=0, help_text="Ej: 15, 30 días")
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name="Vence el")

    saldo_pendiente = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    esta_pagada = models.BooleanField(default=False, verbose_name="¿Pagada?")

    fecha_subida = models.DateTimeField(auto_now_add=True)
    procesado = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-fecha_subida"]
        verbose_name = "Factura de compra"
        verbose_name_plural = "Facturas de compra"
        indexes = [
            models.Index(fields=["fecha_emision"]),
            models.Index(fields=["numero_factura"]),
            models.Index(fields=["clave_acceso_sri"]),
            models.Index(fields=["procesado"]),
            models.Index(fields=["sucursal_destino"]),
        ]

    def clean(self):
        if self.subtotal < 0:
            raise ValidationError("El subtotal no puede ser negativo.")
        if self.iva < 0:
            raise ValidationError("El IVA no puede ser negativo.")
        if self.total < 0:
            raise ValidationError("El total no puede ser negativo.")
        if self.saldo_pendiente < 0:
            raise ValidationError("El saldo pendiente no puede ser negativo.")
        if not self.sucursal_destino_id:
            raise ValidationError({"sucursal_destino": "La sucursal destino es obligatoria."})

    def recalcular_estado_pago(self, guardar=True):
        total_abonos = self.abonos.aggregate(total=Sum("monto_pagado"))["total"] or Decimal("0.00")
        saldo = self.total - total_abonos

        if saldo <= Decimal("0.00"):
            self.saldo_pendiente = Decimal("0.00")
            self.esta_pagada = self.total > Decimal("0.00")
        else:
            self.saldo_pendiente = saldo
            self.esta_pagada = False

        if guardar and self.pk:
            FacturaCompra.objects.filter(pk=self.pk).update(
                saldo_pendiente=self.saldo_pendiente,
                esta_pagada=self.esta_pagada,
            )

    def save(self, *args, **kwargs):
        if self.proveedor:
            self.proveedor = self.proveedor.strip()
        if self.ruc:
            self.ruc = self.ruc.strip()
        if self.numero_factura:
            self.numero_factura = self.numero_factura.strip()
        if self.clave_acceso:
            self.clave_acceso = self.clave_acceso.strip()
        if self.clave_acceso_sri:
            self.clave_acceso_sri = self.clave_acceso_sri.strip()
        if self.observaciones:
            self.observaciones = self.observaciones.strip()

        if self.fecha_emision:
            if self.forma_pago == "CREDITO" and self.dias_plazo > 0:
                self.fecha_vencimiento = self.fecha_emision + timedelta(days=self.dias_plazo)
            else:
                self.fecha_vencimiento = self.fecha_emision
        else:
            self.fecha_vencimiento = None

        es_nueva = self.pk is None

        if es_nueva:
            self.saldo_pendiente = self.total
            self.esta_pagada = self.total <= Decimal("0.00")

        self.full_clean()
        super().save(*args, **kwargs)

        if not es_nueva:
            self.recalcular_estado_pago()

    def __str__(self):
        proveedor_txt = self.proveedor or (self.proveedor_rel.empresa if self.proveedor_rel else "SIN PROVEEDOR")
        return f"{proveedor_txt} - {self.numero_factura or 'SIN NÚMERO'}"


# =========================================================
# CONTROL DE ABONOS A PROVEEDORES
# =========================================================
class PagoProveedor(models.Model):
    METODOS = [
        ("TRANSFERENCIA", "Transferencia bancaria"),
        ("EFECTIVO", "Efectivo"),
        ("CHEQUE", "Cheque"),
    ]

    factura = models.ForeignKey(FacturaCompra, related_name="abonos", on_delete=models.CASCADE)
    fecha_pago = models.DateField(auto_now_add=True)
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODOS)
    comprobante_banco = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-fecha_pago", "-id"]
        verbose_name = "Abono a proveedor"
        verbose_name_plural = "Abonos a proveedores"

    def clean(self):
        if self.monto_pagado is None or self.monto_pagado <= 0:
            raise ValidationError("El monto pagado debe ser mayor que 0.")

    def save(self, *args, **kwargs):
        if self.comprobante_banco:
            self.comprobante_banco = self.comprobante_banco.strip()

        self.full_clean()
        super().save(*args, **kwargs)
        self.factura.recalcular_estado_pago()

    def delete(self, *args, **kwargs):
        factura = self.factura
        super().delete(*args, **kwargs)
        factura.recalcular_estado_pago()

    def __str__(self):
        return f"Abono ${self.monto_pagado} a {self.factura}"


# =========================================================
# DETALLE ORIGINAL DEL PROVEEDOR (INTOCABLE)
# =========================================================
class DetalleFacturaOriginal(models.Model):
    factura = models.ForeignKey(
        FacturaCompra,
        on_delete=models.CASCADE,
        related_name="detalles_originales",
    )
    codigo_proveedor = models.CharField(max_length=100, blank=True, null=True)
    descripcion_proveedor = models.CharField(max_length=255)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["id"]
        verbose_name = "Detalle original proveedor"
        verbose_name_plural = "Detalles originales proveedor"

    @property
    def subtotal(self):
        return (self.cantidad or Decimal("0.00")) * (self.precio_unitario or Decimal("0.00"))

    def clean(self):
        if not self.descripcion_proveedor or not self.descripcion_proveedor.strip():
            raise ValidationError("La descripción del proveedor es obligatoria.")
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que 0.")
        if self.precio_unitario < 0:
            raise ValidationError("El precio unitario no puede ser negativo.")

    def save(self, *args, **kwargs):
        if self.codigo_proveedor:
            self.codigo_proveedor = self.codigo_proveedor.strip()
        if self.descripcion_proveedor:
            self.descripcion_proveedor = self.descripcion_proveedor.strip()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        codigo = self.codigo_proveedor or "SIN CÓDIGO"
        return f"{codigo} - {self.descripcion_proveedor}"


# =========================================================
# DETALLE NORMALIZADO POR EL SISTEMA / USUARIO / IA
# =========================================================
class DetalleFacturaNormalizado(models.Model):
    detalle_original = models.OneToOneField(
        DetalleFacturaOriginal,
        on_delete=models.CASCADE,
        related_name="detalle_normalizado",
    )

    codigo_sistema = models.CharField(max_length=100, blank=True, null=True)
    nombre_limpio = models.CharField(max_length=250, blank=True, null=True, verbose_name="Nombre normalizado")
    marca_limpia = models.CharField(max_length=100, blank=True, null=True)
    categoria_limpia = models.CharField(max_length=100, blank=True, null=True)
    codigo_barras = models.CharField(max_length=255, blank=True, null=True)

    producto_rel = models.ForeignKey(
        "inventario.Producto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detalles_normalizados_compra",
    )
    codigo_producto_rel = models.ForeignKey(
        "inventario.CodigoProducto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="detalles_normalizados_compra",
    )

    cantidad = models.PositiveIntegerField()
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    costo_anterior = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    ingresado_al_inventario = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Detalle normalizado"
        verbose_name_plural = "Detalles normalizados"

    @property
    def factura(self):
        return self.detalle_original.factura

    @property
    def descripcion_original(self):
        return self.detalle_original.descripcion_proveedor

    @property
    def codigo_original(self):
        return self.detalle_original.codigo_proveedor

    @property
    def subtotal(self):
        return Decimal(self.cantidad or 0) * (self.costo_unitario or Decimal("0.00"))

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que 0.")
        if self.costo_unitario < 0:
            raise ValidationError("El costo unitario no puede ser negativo.")
        if self.costo_anterior is not None and self.costo_anterior < 0:
            raise ValidationError("El costo anterior no puede ser negativo.")

    def save(self, *args, **kwargs):
        if self.codigo_sistema:
            self.codigo_sistema = self.codigo_sistema.strip().upper()
        if self.nombre_limpio:
            self.nombre_limpio = self.nombre_limpio.strip()
        if self.marca_limpia:
            self.marca_limpia = self.marca_limpia.strip()
        if self.categoria_limpia:
            self.categoria_limpia = self.categoria_limpia.strip()
        if self.codigo_barras:
            self.codigo_barras = self.codigo_barras.strip()
        if self.observaciones:
            self.observaciones = self.observaciones.strip()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        codigo = self.codigo_sistema or self.codigo_original or "SIN CÓDIGO"
        nombre = self.nombre_limpio or self.descripcion_original
        return f"{codigo} - {nombre}"