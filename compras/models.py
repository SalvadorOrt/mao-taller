# compras/models.py

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Sum


# =========================================================
# CONSTANTES
# =========================================================

CERO = Decimal("0.00")
CIEN = Decimal("100.00")
DOS_DECIMALES = Decimal("0.01")


# =========================================================
# PROVEEDORES
# =========================================================

class Proveedor(models.Model):
    nombre_contacto = models.CharField(
        max_length=150,
    )

    empresa = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    razon_social = models.CharField(
        max_length=200,
        blank=True,
        null=True,
    )

    ciudad = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    telefono = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    whatsapp = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    tiene_whatsapp = models.BooleanField(
        default=True,
    )

    email = models.EmailField(
        blank=True,
        null=True,
    )

    ruc = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True,
    )

    obligado_contabilidad = models.BooleanField(
        default=False,
    )

    agente_retencion = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    activo = models.BooleanField(
        default=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "empresa",
            "razon_social",
            "nombre_contacto",
        ]

        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

        indexes = [
            models.Index(fields=["empresa"]),
            models.Index(fields=["razon_social"]),
            models.Index(fields=["nombre_contacto"]),
            models.Index(fields=["ruc"]),
            models.Index(fields=["activo"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["ruc"],
                condition=models.Q(ruc__isnull=False),
                name="compras_proveedor_ruc_unico_no_nulo",
            ),
        ]

    def clean(self):
        errores = {}

        if (
            not self.nombre_contacto
            or not self.nombre_contacto.strip()
        ):
            errores["nombre_contacto"] = (
                "El nombre de contacto es obligatorio."
            )

        if self.whatsapp:
            numero = (
                self.whatsapp
                .strip()
                .replace(" ", "")
            )

            if not numero.startswith("+"):
                errores["whatsapp"] = (
                    "Debe usar formato internacional. "
                    "Ejemplo: +593999999999."
                )

            elif not numero[1:].isdigit():
                errores["whatsapp"] = (
                    "Después del signo + solo se permiten números."
                )

        if self.ruc:
            ruc = self.ruc.strip()

            if not ruc.isdigit():
                errores["ruc"] = (
                    "El RUC solo puede contener números."
                )

            elif len(ruc) != 13:
                errores["ruc"] = (
                    "El RUC debe contener 13 dígitos."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.nombre_contacto:
            self.nombre_contacto = (
                self.nombre_contacto
                .strip()
                .upper()
            )

        if self.empresa:
            self.empresa = (
                self.empresa
                .strip()
                .upper()
            )

        if self.razon_social:
            self.razon_social = (
                self.razon_social
                .strip()
                .upper()
            )

        if self.ciudad:
            self.ciudad = (
                self.ciudad
                .strip()
                .upper()
            )

        if self.telefono:
            self.telefono = self.telefono.strip()

        if self.whatsapp:
            self.whatsapp = (
                self.whatsapp
                .strip()
                .replace(" ", "")
            )

        if self.email:
            self.email = (
                self.email
                .strip()
                .lower()
            )

        if self.ruc:
            self.ruc = self.ruc.strip()

        if self.agente_retencion:
            self.agente_retencion = (
                self.agente_retencion
                .strip()
                .upper()
            )

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def whatsapp_link(self):
        if not self.whatsapp:
            return None

        numero = self.whatsapp.replace("+", "")

        return f"https://wa.me/{numero}"

    @property
    def nombre_final(self):
        return (
            self.empresa
            or self.razon_social
            or self.nombre_contacto
        )

    def __str__(self):
        return self.nombre_final


# =========================================================
# FACTURA DE COMPRA
# =========================================================

class FacturaCompra(models.Model):
    FORMAS_PAGO = [
        ("CONTADO", "Contado"),
        ("CREDITO", "Crédito"),
    ]

    ESTADOS = [
        ("BORRADOR", "En proceso / Borrador"),
        ("PROCESADA", "Registrada en inventario"),
        ("ANULADA", "Anulada"),
    ]

    ORIGENES_INGRESO = [
        ("XML", "Subida de XML"),
        ("CLAVE", "Clave de acceso SRI"),
        ("MANUAL", "Digitación manual"),
    ]

    origen_ingreso = models.CharField(
        max_length=10,
        choices=ORIGENES_INGRESO,
        default="MANUAL",
        verbose_name="Origen de ingreso",
    )

    estado = models.CharField(
        max_length=15,
        choices=ESTADOS,
        default="BORRADOR",
    )

    tipo_comprobante = models.CharField(
        max_length=2,
        default="01",
        verbose_name="Tipo de comprobante",
    )

    sustento_tributario = models.CharField(
        max_length=2,
        default="01",
        verbose_name="Sustento tributario SRI",
    )

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

    configuracion_iva = models.ForeignKey(
        "ordenes_de_trabajo.ConfiguracionTributaria",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="facturas_compra",
    )

    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    clave_acceso_sri = models.CharField(
        "Clave de acceso SRI",
        max_length=49,
        blank=True,
        null=True,
        unique=True,
    )

    archivo_xml = models.FileField(
        upload_to="facturas/xml/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["xml"],
            )
        ],
    )

    archivo_pdf = models.FileField(
        upload_to="facturas/pdf/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["pdf"],
            )
        ],
    )

    imagen_factura = models.ImageField(
        upload_to="facturas/fotos/%Y/%m/",
        blank=True,
        null=True,
    )

    proveedor = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Nombre del proveedor",
    )

    ruc = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="R.U.C.",
    )

    numero_factura = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="N.º de factura",
    )

    clave_acceso = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Clave de acceso / autorización",
    )

    fecha_emision = models.DateField(
        blank=True,
        null=True,
        verbose_name="Fecha de emisión",
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    forma_pago = models.CharField(
        max_length=10,
        choices=FORMAS_PAGO,
        default="CONTADO",
    )

    dias_plazo = models.PositiveIntegerField(
        default=0,
    )

    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vence el",
    )

    saldo_pendiente = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    esta_pagada = models.BooleanField(
        default=False,
        verbose_name="¿Pagada?",
    )

    fecha_subida = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    procesado = models.BooleanField(
        default=False,
    )

    observaciones = models.TextField(
        blank=True,
        null=True,
    )

    class Meta:
        ordering = [
            "-fecha_subida",
        ]

        verbose_name = "Factura de compra"
        verbose_name_plural = "Facturas de compra"

        indexes = [
            models.Index(fields=["fecha_emision"]),
            models.Index(fields=["numero_factura"]),
            models.Index(fields=["clave_acceso_sri"]),
            models.Index(fields=["procesado"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["origen_ingreso"]),
            models.Index(fields=["sucursal_destino"]),
            models.Index(fields=["ruc"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["ruc", "numero_factura"],
                condition=(
                    models.Q(ruc__isnull=False)
                    & models.Q(numero_factura__isnull=False)
                ),
                name="compras_factura_ruc_numero_unicos",
            ),
        ]

    def obtener_configuracion_iva_activa(self):
        from ordenes_de_trabajo.models import (
            ConfiguracionTributaria,
        )

        return (
            ConfiguracionTributaria.objects
            .filter(activa=True)
            .order_by("-fecha_inicio", "-id")
            .first()
        )

    def _obtener_detalles_calculo(self):
        if self.origen_ingreso == "MANUAL":
            return self.detalles_manuales.all()

        return self.detalles_originales.all()

    def calcular_totales(self):
        if not self.pk:
            return

        if self.porcentaje_iva is None:
            configuracion = (
                self.obtener_configuracion_iva_activa()
            )

            if configuracion:
                self.configuracion_iva = configuracion
                self.porcentaje_iva = (
                    configuracion.porcentaje_iva
                )
            else:
                self.porcentaje_iva = CERO

        detalles = self._obtener_detalles_calculo()

        nuevo_subtotal = CERO
        base_con_iva = CERO

        for detalle in detalles:
            subtotal_detalle = (
                detalle.subtotal
            ).quantize(
                DOS_DECIMALES,
                rounding=ROUND_HALF_UP,
            )

            nuevo_subtotal += subtotal_detalle

            if detalle.aplica_iva:
                base_con_iva += subtotal_detalle

        nuevo_subtotal = nuevo_subtotal.quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

        porcentaje = (
            self.porcentaje_iva
            if self.porcentaje_iva is not None
            else CERO
        )

        nuevo_iva = (
            base_con_iva
            * porcentaje
            / CIEN
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

        nuevo_total = (
            nuevo_subtotal + nuevo_iva
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

        FacturaCompra.objects.filter(
            pk=self.pk,
        ).update(
            subtotal=nuevo_subtotal,
            iva=nuevo_iva,
            total=nuevo_total,
            porcentaje_iva=porcentaje,
            configuracion_iva=self.configuracion_iva,
        )

        self.subtotal = nuevo_subtotal
        self.iva = nuevo_iva
        self.total = nuevo_total

        self.recalcular_estado_pago(
            guardar=True,
        )

    def clean(self):
        errores = {}

        self.origen_ingreso = (
            self.origen_ingreso
            or "MANUAL"
        ).strip().upper()

        if self.clave_acceso_sri:
            self.clave_acceso_sri = (
                self.clave_acceso_sri.strip()
            )

        if self.origen_ingreso == "CLAVE":
            clave = (
                self.clave_acceso_sri
                or ""
            ).strip()

            if not clave:
                errores["clave_acceso_sri"] = (
                    "Para consultar al SRI debe ingresar "
                    "la clave de acceso."
                )

            elif len(clave) != 49 or not clave.isdigit():
                errores["clave_acceso_sri"] = (
                    "La clave debe contener exactamente "
                    "49 dígitos."
                )

        elif self.origen_ingreso == "XML":
            if not self.archivo_xml:
                errores["archivo_xml"] = (
                    "Debe adjuntar el archivo XML."
                )

        elif self.origen_ingreso == "MANUAL":
            if (
                not self.proveedor
                and not self.proveedor_rel
            ):
                errores["proveedor"] = (
                    "El proveedor es obligatorio."
                )

            if not self.numero_factura:
                errores["numero_factura"] = (
                    "El número de factura es obligatorio."
                )

            if not self.fecha_emision:
                errores["fecha_emision"] = (
                    "La fecha de emisión es obligatoria."
                )

        if self.ruc:
            ruc = self.ruc.strip()

            if not ruc.isdigit():
                errores["ruc"] = (
                    "El RUC solo puede contener números."
                )

            elif len(ruc) != 13:
                errores["ruc"] = (
                    "El RUC debe contener 13 dígitos."
                )

        if self.porcentaje_iva is not None:
            if self.porcentaje_iva < CERO:
                errores["porcentaje_iva"] = (
                    "El porcentaje de IVA no puede ser negativo."
                )

            elif self.porcentaje_iva > CIEN:
                errores["porcentaje_iva"] = (
                    "El porcentaje de IVA no puede superar 100%."
                )

        if self.subtotal < CERO:
            errores["subtotal"] = (
                "El subtotal no puede ser negativo."
            )

        if self.iva < CERO:
            errores["iva"] = (
                "El IVA no puede ser negativo."
            )

        if self.total < CERO:
            errores["total"] = (
                "El total no puede ser negativo."
            )

        if self.saldo_pendiente < CERO:
            errores["saldo_pendiente"] = (
                "El saldo pendiente no puede ser negativo."
            )

        if not self.sucursal_destino_id:
            errores["sucursal_destino"] = (
                "La sucursal destino es obligatoria."
            )

        if self.forma_pago == "CONTADO":
            self.dias_plazo = 0

        if (
            self.forma_pago == "CREDITO"
            and self.dias_plazo <= 0
        ):
            errores["dias_plazo"] = (
                "Una factura a crédito debe tener "
                "al menos un día de plazo."
            )

        if errores:
            raise ValidationError(errores)

    def recalcular_estado_pago(self, guardar=True):
        total_abonos = (
            self.abonos
            .aggregate(total=Sum("monto_pagado"))
            .get("total")
            or CERO
        )

        saldo = (
            self.total - total_abonos
        ).quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

        if saldo <= CERO:
            self.saldo_pendiente = CERO
            self.esta_pagada = (
                self.total > CERO
            )
        else:
            self.saldo_pendiente = saldo
            self.esta_pagada = False

        if guardar and self.pk:
            FacturaCompra.objects.filter(
                pk=self.pk,
            ).update(
                saldo_pendiente=self.saldo_pendiente,
                esta_pagada=self.esta_pagada,
            )

    def save(self, *args, **kwargs):
        if self.proveedor:
            self.proveedor = (
                self.proveedor
                .strip()
                .upper()
            )

        if self.ruc:
            self.ruc = self.ruc.strip()

        if self.numero_factura:
            self.numero_factura = (
                self.numero_factura
                .strip()
                .upper()
            )

        if self.clave_acceso:
            self.clave_acceso = (
                self.clave_acceso.strip()
            )

        if self.clave_acceso_sri:
            self.clave_acceso_sri = (
                self.clave_acceso_sri.strip()
            )

        if self.observaciones:
            self.observaciones = (
                self.observaciones.strip()
            )

        if self.fecha_emision:
            if (
                self.forma_pago == "CREDITO"
                and self.dias_plazo > 0
            ):
                self.fecha_vencimiento = (
                    self.fecha_emision
                    + timedelta(days=self.dias_plazo)
                )
            else:
                self.fecha_vencimiento = (
                    self.fecha_emision
                )
        else:
            self.fecha_vencimiento = None

        es_nueva = self.pk is None

        if es_nueva:
            self.saldo_pendiente = (
                self.total or CERO
            )

            self.esta_pagada = (
                self.total <= CERO
            )

        self.full_clean()
        super().save(*args, **kwargs)

        if not es_nueva:
            self.recalcular_estado_pago(
                guardar=True,
            )

    @property
    def numero_factura_formateado(self):
        return (
            self.numero_factura
            or "SIN NÚMERO"
        )

    @property
    def nombre_proveedor_final(self):
        if self.proveedor:
            return self.proveedor

        if self.proveedor_rel:
            return self.proveedor_rel.nombre_final

        return "SIN PROVEEDOR"

    def __str__(self):
        return (
            f"{self.nombre_proveedor_final} - "
            f"{self.numero_factura_formateado}"
        )


# =========================================================
# CUOTAS PROGRAMADAS
# =========================================================

class CuotaPago(models.Model):
    ESTADOS_CUOTA = [
        ("PENDIENTE", "Pendiente"),
        ("PAGADA", "Pagada"),
        ("VENCIDA", "Vencida"),
        ("ANULADA", "Anulada"),
    ]

    factura = models.ForeignKey(
        FacturaCompra,
        related_name="cuotas",
        on_delete=models.CASCADE,
    )

    numero_cuota = models.PositiveIntegerField(
        default=1,
    )

    fecha_vencimiento = models.DateField()

    valor_cuota = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS_CUOTA,
        default="PENDIENTE",
    )

    class Meta:
        ordering = [
            "factura",
            "numero_cuota",
        ]

        verbose_name = "Cuota programada"
        verbose_name_plural = "Cuotas programadas"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "factura",
                    "numero_cuota",
                ],
                name="compras_cuota_numero_unico_por_factura",
            ),
        ]

    def clean(self):
        errores = {}

        if (
            self.valor_cuota is None
            or self.valor_cuota <= CERO
        ):
            errores["valor_cuota"] = (
                "El valor de la cuota debe ser mayor que 0."
            )

        if (
            self.factura_id
            and self.factura.forma_pago != "CREDITO"
        ):
            errores["factura"] = (
                "Solo se pueden crear cuotas para "
                "facturas a crédito."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"Cuota {self.numero_cuota} "
            f"de {self.factura} - "
            f"${self.valor_cuota}"
        )


# =========================================================
# ABONOS A PROVEEDORES
# =========================================================

class PagoProveedor(models.Model):
    METODOS = [
        ("TRANSFERENCIA", "Transferencia bancaria"),
        ("EFECTIVO", "Efectivo"),
        ("CHEQUE", "Cheque"),
        ("TARJETA", "Tarjeta"),
        ("OTRO", "Otro"),
    ]

    factura = models.ForeignKey(
        FacturaCompra,
        related_name="abonos",
        on_delete=models.CASCADE,
    )

    fecha_pago = models.DateField(
        auto_now_add=True,
    )

    monto_pagado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    metodo = models.CharField(
        max_length=20,
        choices=METODOS,
    )

    comprobante_banco = models.CharField(
        max_length=100,
        blank=True,
    )

    observacion = models.TextField(
        blank=True,
        null=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-fecha_pago",
            "-id",
        ]

        verbose_name = "Abono a proveedor"
        verbose_name_plural = "Abonos a proveedores"

        indexes = [
            models.Index(fields=["fecha_pago"]),
            models.Index(fields=["metodo"]),
        ]

    def clean(self):
        errores = {}

        if (
            self.monto_pagado is None
            or self.monto_pagado <= CERO
        ):
            errores["monto_pagado"] = (
                "El monto pagado debe ser mayor que 0."
            )

        if self.factura_id:
            otros_abonos = (
                self.factura.abonos
                .exclude(pk=self.pk)
                .aggregate(total=Sum("monto_pagado"))
                .get("total")
                or CERO
            )

            total_con_nuevo_abono = (
                otros_abonos
                + (self.monto_pagado or CERO)
            )

            if total_con_nuevo_abono > self.factura.total:
                errores["monto_pagado"] = (
                    "El total de abonos no puede superar "
                    "el valor total de la factura."
                )

            if self.factura.estado == "ANULADA":
                errores["factura"] = (
                    "No se pueden registrar pagos "
                    "en una factura anulada."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.comprobante_banco:
            self.comprobante_banco = (
                self.comprobante_banco
                .strip()
                .upper()
            )

        if self.observacion:
            self.observacion = (
                self.observacion.strip()
            )

        self.full_clean()
        super().save(*args, **kwargs)

        self.factura.recalcular_estado_pago(
            guardar=True,
        )

    def delete(self, *args, **kwargs):
        factura = self.factura

        super().delete(*args, **kwargs)

        factura.recalcular_estado_pago(
            guardar=True,
        )

    def __str__(self):
        return (
            f"Abono ${self.monto_pagado} "
            f"a {self.factura}"
        )


# =========================================================
# DETALLE ORIGINAL DE FACTURA
# =========================================================

class DetalleFacturaOriginal(models.Model):
    factura = models.ForeignKey(
        FacturaCompra,
        on_delete=models.CASCADE,
        related_name="detalles_originales",
    )

    codigo_proveedor = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    descripcion_proveedor = models.CharField(
        max_length=255,
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=4,
    )

    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=6,
    )

    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    aplica_iva = models.BooleanField(
        default=True,
    )

    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=CERO,
    )

    valor_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    class Meta:
        ordering = [
            "id",
        ]

        verbose_name = "Detalle original del proveedor"
        verbose_name_plural = "Detalles originales del proveedor"

        indexes = [
            models.Index(fields=["codigo_proveedor"]),
            models.Index(fields=["factura"]),
        ]

    @property
    def importe_bruto(self):
        return (
            (self.cantidad or CERO)
            * (self.precio_unitario or CERO)
        )

    @property
    def subtotal(self):
        subtotal = (
            self.importe_bruto
            - (self.descuento or CERO)
        )

        return subtotal.quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    def clean(self):
        errores = {}

        if (
            not self.descripcion_proveedor
            or not self.descripcion_proveedor.strip()
        ):
            errores["descripcion_proveedor"] = (
                "La descripción del proveedor es obligatoria."
            )

        if (
            self.cantidad is None
            or self.cantidad <= CERO
        ):
            errores["cantidad"] = (
                "La cantidad debe ser mayor que 0."
            )

        if (
            self.precio_unitario is None
            or self.precio_unitario < CERO
        ):
            errores["precio_unitario"] = (
                "El precio unitario no puede ser negativo."
            )

        if (
            self.descuento is None
            or self.descuento < CERO
        ):
            errores["descuento"] = (
                "El descuento no puede ser negativo."
            )

        if (
            self.cantidad is not None
            and self.precio_unitario is not None
            and self.descuento is not None
            and self.descuento > self.importe_bruto
        ):
            errores["descuento"] = (
                "El descuento no puede superar "
                "el importe bruto del detalle."
            )

        if self.porcentaje_iva < CERO:
            errores["porcentaje_iva"] = (
                "El porcentaje de IVA no puede ser negativo."
            )

        if self.valor_iva < CERO:
            errores["valor_iva"] = (
                "El valor del IVA no puede ser negativo."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.codigo_proveedor:
            self.codigo_proveedor = (
                self.codigo_proveedor
                .strip()
                .upper()
            )

        if self.descripcion_proveedor:
            self.descripcion_proveedor = (
                self.descripcion_proveedor.strip()
            )

        self.full_clean()
        super().save(*args, **kwargs)

        if self.factura_id:
            self.factura.calcular_totales()

    def delete(self, *args, **kwargs):
        factura = self.factura

        super().delete(*args, **kwargs)

        factura.calcular_totales()

    def __str__(self):
        codigo = (
            self.codigo_proveedor
            or "SIN CÓDIGO"
        )

        return (
            f"{codigo} - "
            f"{self.descripcion_proveedor}"
        )


# =========================================================
# DETALLE NORMALIZADO
# =========================================================

class DetalleFacturaNormalizado(models.Model):
    DESTINO_CHOICES = [
        (
            "INVENTARIO",
            "Repuesto / Insumo (suma stock)",
        ),
        (
            "GASTO",
            "Gasto administrativo",
        ),
        (
            "SERVICIO",
            "Servicio externo",
        ),
    ]

    detalle_original = models.OneToOneField(
        DetalleFacturaOriginal,
        on_delete=models.CASCADE,
        related_name="detalle_normalizado",
        null=True,
        blank=True,
    )

    factura_manual = models.ForeignKey(
        FacturaCompra,
        on_delete=models.CASCADE,
        related_name="detalles_manuales",
        null=True,
        blank=True,
    )

    tipo_destino = models.CharField(
        max_length=20,
        choices=DESTINO_CHOICES,
        default="INVENTARIO",
    )

    aplica_iva = models.BooleanField(
        default=True,
        help_text="Indica si el detalle grava IVA.",
    )

    porcentaje_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=CERO,
    )

    orden_trabajo_rel = models.ForeignKey(
        "ordenes_de_trabajo.OrdenTrabajo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compras_relacionadas",
        help_text=(
            "Orden de trabajo para la cual "
            "se realizó esta compra."
        ),
    )

    placa_vehiculo = models.CharField(
        max_length=15,
        blank=True,
        null=True,
    )

    codigo_sistema = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    nombre_limpio = models.CharField(
        max_length=250,
        blank=True,
        null=True,
        verbose_name="Nombre normalizado",
    )

    marca_limpia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    categoria_limpia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    codigo_barras = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

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

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=4,
    )

    costo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=6,
    )

    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=CERO,
    )

    costo_anterior = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        null=True,
        blank=True,
    )

    nuevo_precio_venta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    actualizar_pvp_inventario = models.BooleanField(
        default=False,
    )

    ingresado_al_inventario = models.BooleanField(
        default=False,
    )

    observaciones = models.TextField(
        blank=True,
        null=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "id",
        ]

        verbose_name = "Detalle normalizado"
        verbose_name_plural = "Detalles normalizados"

        indexes = [
            models.Index(fields=["tipo_destino"]),
            models.Index(fields=["ingresado_al_inventario"]),
            models.Index(fields=["codigo_sistema"]),
            models.Index(fields=["codigo_barras"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(
                            detalle_original__isnull=False,
                        )
                        & models.Q(
                            factura_manual__isnull=True,
                        )
                    )
                    |
                    (
                        models.Q(
                            detalle_original__isnull=True,
                        )
                        & models.Q(
                            factura_manual__isnull=False,
                        )
                    )
                ),
                name="compras_detalle_normalizado_un_solo_origen",
            ),
        ]

    @property
    def factura(self):
        if self.detalle_original_id:
            return self.detalle_original.factura

        return self.factura_manual

    @property
    def descripcion_original(self):
        if self.detalle_original_id:
            return (
                self.detalle_original
                .descripcion_proveedor
            )

        return "INGRESO MANUAL"

    @property
    def codigo_original(self):
        if self.detalle_original_id:
            return (
                self.detalle_original
                .codigo_proveedor
            )

        return "MANUAL"

    @property
    def importe_bruto(self):
        return (
            (self.cantidad or CERO)
            * (self.costo_unitario or CERO)
        )

    @property
    def subtotal(self):
        subtotal = (
            self.importe_bruto
            - (self.descuento or CERO)
        )

        return subtotal.quantize(
            DOS_DECIMALES,
            rounding=ROUND_HALF_UP,
        )

    def clean(self):
        errores = {}

        tiene_original = bool(
            self.detalle_original_id
        )

        tiene_factura_manual = bool(
            self.factura_manual_id
        )

        if (
            tiene_original
            and tiene_factura_manual
        ):
            raise ValidationError(
                "El detalle no puede vincularse simultáneamente "
                "a un detalle XML y a una factura manual."
            )

        if (
            not tiene_original
            and not tiene_factura_manual
        ):
            raise ValidationError(
                "El detalle debe vincularse a un detalle original "
                "o a una factura manual."
            )

        if (
            tiene_original
            and self.detalle_original.factura.origen_ingreso
            == "MANUAL"
        ):
            errores["detalle_original"] = (
                "Una factura manual no debe usar "
                "DetalleFacturaOriginal."
            )

        if (
            tiene_factura_manual
            and self.factura_manual.origen_ingreso
            != "MANUAL"
        ):
            errores["factura_manual"] = (
                "factura_manual solo puede utilizarse "
                "con facturas de origen MANUAL."
            )

        if (
            self.cantidad is None
            or self.cantidad <= CERO
        ):
            errores["cantidad"] = (
                "La cantidad debe ser mayor que 0."
            )

        if (
            self.costo_unitario is None
            or self.costo_unitario < CERO
        ):
            errores["costo_unitario"] = (
                "El costo unitario no puede ser negativo."
            )

        if (
            self.descuento is None
            or self.descuento < CERO
        ):
            errores["descuento"] = (
                "El descuento no puede ser negativo."
            )

        if (
            self.cantidad is not None
            and self.costo_unitario is not None
            and self.descuento is not None
            and self.descuento > self.importe_bruto
        ):
            errores["descuento"] = (
                "El descuento no puede superar "
                "el importe bruto del detalle."
            )

        if (
            self.costo_anterior is not None
            and self.costo_anterior < CERO
        ):
            errores["costo_anterior"] = (
                "El costo anterior no puede ser negativo."
            )

        if (
            self.nuevo_precio_venta is not None
            and self.nuevo_precio_venta < CERO
        ):
            errores["nuevo_precio_venta"] = (
                "El nuevo precio de venta "
                "no puede ser negativo."
            )

        if (
            self.actualizar_pvp_inventario
            and self.nuevo_precio_venta is None
        ):
            errores["nuevo_precio_venta"] = (
                "Debe indicar el nuevo precio de venta."
            )

        if self.porcentaje_iva < CERO:
            errores["porcentaje_iva"] = (
                "El porcentaje de IVA no puede ser negativo."
            )

        if self.tipo_destino == "INVENTARIO":
            if (
                not self.nombre_limpio
                and not self.producto_rel_id
            ):
                errores["nombre_limpio"] = (
                    "Para inventario debe indicar un nombre "
                    "normalizado o seleccionar un producto."
                )

        if (
            self.tipo_destino in {
                "GASTO",
                "SERVICIO",
            }
            and (
                self.producto_rel_id
                or self.codigo_producto_rel_id
            )
        ):
            errores["tipo_destino"] = (
                "Un gasto o servicio no debe estar vinculado "
                "a un producto del inventario."
            )

        if (
            self.orden_trabajo_rel_id
            and self.placa_vehiculo
            and self.orden_trabajo_rel.placa
        ):
            placa_orden = (
                self.orden_trabajo_rel.placa
                .strip()
                .upper()
                .replace("-", "")
                .replace(" ", "")
            )

            placa_detalle = (
                self.placa_vehiculo
                .strip()
                .upper()
                .replace("-", "")
                .replace(" ", "")
            )

            if placa_orden != placa_detalle:
                errores["placa_vehiculo"] = (
                    "La placa no coincide con la orden de trabajo."
                )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        if self.codigo_sistema:
            self.codigo_sistema = (
                self.codigo_sistema
                .strip()
                .upper()
            )

        if self.nombre_limpio:
            self.nombre_limpio = (
                self.nombre_limpio.strip()
            )

        if self.marca_limpia:
            self.marca_limpia = (
                self.marca_limpia
                .strip()
                .upper()
            )

        if self.categoria_limpia:
            self.categoria_limpia = (
                self.categoria_limpia
                .strip()
                .upper()
            )

        if self.codigo_barras:
            self.codigo_barras = (
                self.codigo_barras.strip()
            )

        if self.placa_vehiculo:
            self.placa_vehiculo = (
                self.placa_vehiculo
                .strip()
                .upper()
                .replace("-", "")
                .replace(" ", "")
            )

        if self.observaciones:
            self.observaciones = (
                self.observaciones.strip()
            )

        if self.tipo_destino in {
            "GASTO",
            "SERVICIO",
        }:
            self.marca_limpia = None
            self.categoria_limpia = None
            self.producto_rel = None
            self.codigo_producto_rel = None
            self.ingresado_al_inventario = False
            self.actualizar_pvp_inventario = False
            self.nuevo_precio_venta = None

        self.full_clean()
        super().save(*args, **kwargs)

        factura = self.factura

        if factura:
            factura.calcular_totales()

    def delete(self, *args, **kwargs):
        factura = self.factura

        super().delete(*args, **kwargs)

        if factura:
            factura.calcular_totales()

    def __str__(self):
        codigo = (
            self.codigo_sistema
            or self.codigo_original
            or "SIN CÓDIGO"
        )

        nombre = (
            self.nombre_limpio
            or self.descripcion_original
        )

        return f"{codigo} - {nombre}"