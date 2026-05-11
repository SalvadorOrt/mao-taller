from decimal import Decimal
import random

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Sum
from django.utils import timezone


# =========================================================
# VALIDADORES ESPECÍFICOS DE FACTURACIÓN
# =========================================================

solo_3_digitos = RegexValidator(
    regex=r"^\d{3}$",
    message="Debe contener exactamente 3 dígitos.",
)

solo_9_digitos = RegexValidator(
    regex=r"^\d{9}$",
    message="Debe contener exactamente 9 dígitos.",
)


# =========================================================
# FACTURA DE VENTA
# =========================================================

class FacturaVenta(models.Model):
    ESTADOS_SRI = [
        ("BORRADOR", "Borrador"),
        ("GENERADO", "XML Generado"),
        ("FIRMADO", "XML Firmado"),
        ("RECIBIDO", "Recibido por SRI"),
        ("AUTORIZADO", "Autorizado"),
        ("RECHAZADO", "Rechazado/Error"),
    ]

    AMBIENTES = [
        ("1", "Pruebas"),
        ("2", "Producción"),
    ]

    TIPOS_EMISION = [
        ("1", "Normal"),
    ]

    TIPOS_COMPROBANTE = [
        ("01", "Factura"),
    ]

    TIPOS_IDENTIFICACION = [
        ("04", "RUC"),
        ("05", "Cédula"),
        ("06", "Pasaporte"),
        ("07", "Consumidor Final"),
    ]

    FORMAS_PAGO = [
        ("01", "Sin utilización del sistema financiero"),
        ("15", "Compensación de deudas"),
        ("16", "Tarjeta de débito"),
        ("17", "Dinero electrónico"),
        ("18", "Tarjeta prepago"),
        ("19", "Tarjeta de crédito"),
        ("20", "Otros con utilización del sistema financiero"),
        ("21", "Endoso de títulos"),
    ]

    MONEDAS = [
        ("DOLAR", "Dólar"),
    ]

    orden = models.OneToOneField(
        "ordenes_de_trabajo.OrdenTrabajo",
        on_delete=models.SET_NULL,
        related_name="factura_electronica",
        null=True,
        blank=True,
    )

    sucursal = models.ForeignKey(
            'ordenes_de_trabajo.Sucursal',
            on_delete=models.PROTECT,
            related_name='facturas_venta',
            null=True,
            blank=True,
        )

    empresa = models.ForeignKey(
        "empresa.EmpresaEmisora",
        on_delete=models.PROTECT,
        related_name="facturas",
    )

    firma_electronica = models.ForeignKey(
        "empresa.FirmaElectronica",
        on_delete=models.PROTECT,
        related_name="facturas",
        blank=True,
        null=True,
    )

    # -----------------------------------------------------
    # DATOS DEL COMPROBANTE
    # -----------------------------------------------------
    guia_remision = models.CharField(max_length=20, blank=True, null=True)
    vendedor = models.CharField(max_length=200, blank=True, null=True)
    fecha_emision = models.DateField(default=timezone.localdate)

    tipo_comprobante = models.CharField(
        max_length=2,
        choices=TIPOS_COMPROBANTE,
        default="01",
        editable=False,
    )

    ambiente = models.CharField(
        max_length=1,
        choices=AMBIENTES,
        default="1",
    )

    tipo_emision = models.CharField(
        max_length=1,
        choices=TIPOS_EMISION,
        default="1",
    )

    establecimiento = models.CharField(
        max_length=3,
        blank=True,
        validators=[solo_3_digitos],
    )

    punto_emision = models.CharField(
        max_length=3,
        blank=True,
        validators=[solo_3_digitos],
    )

    secuencial = models.CharField(
        max_length=9,
        blank=True,
        validators=[solo_9_digitos],
    )

    clave_acceso = models.CharField(
        max_length=49,
        unique=True,
        editable=False,
        blank=True,
    )

    codigo_numerico = models.CharField(
        max_length=8,
        blank=True,
        editable=False,
    )

    # -----------------------------------------------------
    # DATOS COMPRADOR
    # -----------------------------------------------------
    tipo_identificacion_comprador = models.CharField(
        max_length=2,
        choices=TIPOS_IDENTIFICACION,
        default="05",
    )

    razon_social_comprador = models.CharField(max_length=300)
    identificacion_comprador = models.CharField(max_length=20)
    direccion_comprador = models.CharField(max_length=500, blank=True, null=True)
    telefono_comprador = models.CharField(max_length=20, blank=True, null=True)
    correo_comprador = models.EmailField(blank=True, null=True)

    # -----------------------------------------------------
    # TOTALES
    # -----------------------------------------------------
    total_sin_impuestos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    subtotal_iva_15 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    iva_15 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    subtotal_iva_0 = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    propina = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    importe_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    moneda = models.CharField(
        max_length=10,
        choices=MONEDAS,
        default="DOLAR",
    )

    # -----------------------------------------------------
    # ESTADO SRI
    # -----------------------------------------------------
    estado = models.CharField(
        max_length=15,
        choices=ESTADOS_SRI,
        default="BORRADOR",
    )

    numero_autorizacion = models.CharField(max_length=50, blank=True, null=True)
    fecha_autorizacion = models.DateTimeField(blank=True, null=True)
    mensaje_sri = models.TextField(blank=True, null=True)

    # -----------------------------------------------------
    # FIRMA
    # -----------------------------------------------------
    fecha_firma = models.DateTimeField(blank=True, null=True)
    huella_firma = models.CharField(max_length=255, blank=True, null=True)
    mensaje_firma = models.TextField(blank=True, null=True)

    # -----------------------------------------------------
    # ARCHIVOS
    # -----------------------------------------------------
    xml_generado = models.FileField(
        upload_to="facturas/ventas/xml/generado/",
        blank=True,
        null=True,
    )

    xml_firmado = models.FileField(
        upload_to="facturas/ventas/xml/firmado/",
        blank=True,
        null=True,
    )

    xml_autorizado = models.FileField(
        upload_to="facturas/ventas/xml/autorizado/",
        blank=True,
        null=True,
    )

    pdf_ride = models.FileField(
        upload_to="facturas/ventas/pdf/",
        blank=True,
        null=True,
    )

    # -----------------------------------------------------
    # EXTRA
    # -----------------------------------------------------
    comentario = models.CharField(max_length=500, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Factura de venta"
        verbose_name_plural = "Facturas de venta"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "establecimiento", "punto_emision", "secuencial"],
                name="unique_factura_serie_secuencial",
            )
        ]
        indexes = [
            models.Index(fields=["sucursal", "fecha_emision"]),
            models.Index(fields=["empresa", "fecha_emision"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["clave_acceso"]),
        ]

    def __str__(self):
        return f"Factura {self.establecimiento}-{self.punto_emision}-{self.secuencial}"

    @property
    def numero_factura(self):
        return f"{self.establecimiento}-{self.punto_emision}-{self.secuencial}"

    # =====================================================
    # VALIDACIONES
    # =====================================================

    def clean(self):
        super().clean()

        if not self.sucursal_id:
            raise ValidationError({"sucursal": "La sucursal es obligatoria."})

        if not self.empresa_id and self.sucursal_id:
            empresa_sucursal = getattr(self.sucursal, "empresa", None)
            if empresa_sucursal:
                self.empresa = empresa_sucursal

        if not self.empresa_id:
            raise ValidationError({"empresa": "La empresa emisora es obligatoria."})

        # La sucursal debe pertenecer a la empresa
        empresa_sucursal = getattr(self.sucursal, "empresa", None)
        if empresa_sucursal and self.empresa_id and empresa_sucursal.id != self.empresa_id:
            raise ValidationError({
                "sucursal": "La sucursal seleccionada no pertenece a la empresa emisora."
            })

        # Establecimiento y punto de emisión: primero desde sucursal
        if self.sucursal:
            establecimiento_sucursal = getattr(self.sucursal, "establecimiento", None)
            punto_emision_sucursal = getattr(self.sucursal, "punto_emision", None)

            if not self.establecimiento and establecimiento_sucursal:
                self.establecimiento = establecimiento_sucursal

            if not self.punto_emision and punto_emision_sucursal:
                self.punto_emision = punto_emision_sucursal

        # Fallback desde empresa
        if self.empresa:
            if not self.establecimiento:
                self.establecimiento = self.empresa.establecimiento

            if not self.punto_emision:
                self.punto_emision = self.empresa.punto_emision

        if not self.establecimiento:
            raise ValidationError({"establecimiento": "El establecimiento es obligatorio."})

        if not self.punto_emision:
            raise ValidationError({"punto_emision": "El punto de emisión es obligatorio."})

        if self.clave_acceso and len(self.clave_acceso) != 49:
            raise ValidationError({
                "clave_acceso": "La clave de acceso debe tener exactamente 49 dígitos."
            })

        if self.firma_electronica:
            if self.firma_electronica.empresa_id != self.empresa_id:
                raise ValidationError({
                    "firma_electronica": "La firma electrónica no pertenece a la empresa emisora seleccionada."
                })

            if self.firma_electronica.ruc != self.obtener_ruc_emisor():
                raise ValidationError({
                    "firma_electronica": "El RUC de la firma electrónica no coincide con el RUC del emisor."
                })

        if self.tipo_identificacion_comprador == "04":
            if not self.identificacion_comprador.isdigit() or len(self.identificacion_comprador) != 13:
                raise ValidationError({
                    "identificacion_comprador": "Para RUC debe tener exactamente 13 dígitos."
                })
        elif self.tipo_identificacion_comprador == "05":
            if not self.identificacion_comprador.isdigit() or len(self.identificacion_comprador) != 10:
                raise ValidationError({
                    "identificacion_comprador": "Para cédula debe tener exactamente 10 dígitos."
                })
        elif self.tipo_identificacion_comprador == "06":
            if len(self.identificacion_comprador.strip()) < 3:
                raise ValidationError({
                    "identificacion_comprador": "Para pasaporte debes ingresar una identificación válida."
                })
        elif self.tipo_identificacion_comprador == "07":
            if self.identificacion_comprador != "9999999999999":
                raise ValidationError({
                    "identificacion_comprador": "Para consumidor final debe usar 9999999999999."
                })

    # =====================================================
    # CONFIGURACIÓN EMISOR
    # =====================================================

    def obtener_ruc_emisor(self):
        return self.empresa.ruc

    def obtener_serie(self):
        return f"{self.establecimiento}{self.punto_emision}"

    # =====================================================
    # SECUENCIAL
    # =====================================================

    @classmethod
    def generar_siguiente_secuencial(cls, empresa, establecimiento="001", punto_emision="001"):
        ultima = (
            cls.objects.filter(
                empresa=empresa,
                establecimiento=establecimiento,
                punto_emision=punto_emision,
            )
            .exclude(secuencial__isnull=True)
            .exclude(secuencial__exact="")
            .order_by("-secuencial")
            .first()
        )

        if not ultima:
            return "000000001"

        try:
            ultimo_numero = int(ultima.secuencial)
        except ValueError:
            ultimo_numero = 0

        return str(ultimo_numero + 1).zfill(9)

    # =====================================================
    # CLAVE DE ACCESO
    # =====================================================

    @staticmethod
    def calcular_digito_verificador(clave_parcial):
        if len(clave_parcial) != 48 or not clave_parcial.isdigit():
            raise ValueError("La clave parcial debe contener exactamente 48 dígitos numéricos.")

        factores = [2, 3, 4, 5, 6, 7]
        total = 0
        indice_factor = 0

        for digito in reversed(clave_parcial):
            total += int(digito) * factores[indice_factor]
            indice_factor = (indice_factor + 1) % len(factores)

        residuo = total % 11
        verificador = 11 - residuo

        if verificador == 11:
            verificador = 0
        elif verificador == 10:
            verificador = 1

        return str(verificador)

    def generar_codigo_numerico(self):
        return str(random.randint(10000000, 99999999))

    def construir_clave_parcial(self, codigo_numerico):
        fecha = self.fecha_emision.strftime("%d%m%Y")
        tipo_comprobante = self.tipo_comprobante
        ruc = self.obtener_ruc_emisor()
        ambiente = self.ambiente
        serie = self.obtener_serie()
        secuencial = self.secuencial.zfill(9)
        tipo_emision = self.tipo_emision

        return (
            f"{fecha}"
            f"{tipo_comprobante}"
            f"{ruc}"
            f"{ambiente}"
            f"{serie}"
            f"{secuencial}"
            f"{codigo_numerico}"
            f"{tipo_emision}"
        )

    def generar_clave_acceso(self):
        for _ in range(20):
            codigo_numerico = self.generar_codigo_numerico()
            clave_parcial = self.construir_clave_parcial(codigo_numerico)
            digito_verificador = self.calcular_digito_verificador(clave_parcial)
            clave_completa = f"{clave_parcial}{digito_verificador}"

            if not FacturaVenta.objects.filter(clave_acceso=clave_completa).exists():
                self.codigo_numerico = codigo_numerico
                return clave_completa

        raise ValidationError("No se pudo generar una clave de acceso única después de varios intentos.")

    # =====================================================
    # TOTALES
    # =====================================================

    def recalcular_totales(self, guardar=True):
        detalles = self.detalles.all()

        total_sin_impuestos = Decimal("0.00")
        total_descuento = Decimal("0.00")
        subtotal_iva_15 = Decimal("0.00")
        iva_15 = Decimal("0.00")
        subtotal_iva_0 = Decimal("0.00")

        for detalle in detalles:
            total_sin_impuestos += detalle.precio_total_sin_impuesto
            total_descuento += detalle.descuento

            if detalle.codigo_porcentaje_iva == "4":
                subtotal_iva_15 += detalle.precio_total_sin_impuesto
                iva_15 += detalle.valor_iva
            elif detalle.codigo_porcentaje_iva == "0":
                subtotal_iva_0 += detalle.precio_total_sin_impuesto

        self.total_sin_impuestos = total_sin_impuestos.quantize(Decimal("0.01"))
        self.total_descuento = total_descuento.quantize(Decimal("0.01"))
        self.subtotal_iva_15 = subtotal_iva_15.quantize(Decimal("0.01"))
        self.iva_15 = iva_15.quantize(Decimal("0.01"))
        self.subtotal_iva_0 = subtotal_iva_0.quantize(Decimal("0.01"))
        self.importe_total = (
            self.total_sin_impuestos - self.total_descuento + self.iva_15 + self.propina
        ).quantize(Decimal("0.01"))

        if guardar:
            self.save(update_fields=[
                "total_sin_impuestos",
                "total_descuento",
                "subtotal_iva_15",
                "iva_15",
                "subtotal_iva_0",
                "importe_total",
                "updated_at",
            ])

    def total_pagado(self):
        return self.pagos.aggregate(total=Sum("total")).get("total") or Decimal("0.00")

    def saldo_pendiente(self):
        return (self.importe_total - self.total_pagado()).quantize(Decimal("0.01"))

    def tiene_pagos_completos(self):
        return self.total_pagado().quantize(Decimal("0.01")) == self.importe_total.quantize(Decimal("0.01"))

    # =====================================================
    # FIRMA
    # =====================================================

    def puede_firmarse(self):
        if not self.firma_electronica:
            return False, "No hay firma electrónica asignada."

        if not self.firma_electronica.esta_vigente():
            return False, "La firma electrónica no está vigente o no está activa."

        if not self.xml_generado:
            return False, "Primero debes generar el XML."

        if not self.tiene_pagos_completos():
            return False, "La factura no tiene pagos completos."

        return True, "Factura lista para firmarse."

    def marcar_como_firmado(self, huella_firma=None, mensaje=None):
        self.estado = "FIRMADO"
        self.fecha_firma = timezone.now()
        self.huella_firma = huella_firma
        self.mensaje_firma = mensaje
        self.save(update_fields=[
            "estado",
            "fecha_firma",
            "huella_firma",
            "mensaje_firma",
            "updated_at",
        ])

    def marcar_error_firma(self, mensaje):
        self.mensaje_firma = mensaje
        self.save(update_fields=["mensaje_firma", "updated_at"])

    # =====================================================
    # SRI
    # =====================================================

    def marcar_como_recibido(self, mensaje=None):
        self.estado = "RECIBIDO"
        self.mensaje_sri = mensaje
        self.save(update_fields=["estado", "mensaje_sri", "updated_at"])

    def marcar_como_autorizado(self, numero_autorizacion, fecha_autorizacion=None, mensaje=None):
        self.estado = "AUTORIZADO"
        self.numero_autorizacion = numero_autorizacion
        self.fecha_autorizacion = fecha_autorizacion or timezone.now()
        self.mensaje_sri = mensaje
        self.save(update_fields=[
            "estado",
            "numero_autorizacion",
            "fecha_autorizacion",
            "mensaje_sri",
            "updated_at",
        ])

    def marcar_como_rechazado(self, mensaje):
        self.estado = "RECHAZADO"
        self.mensaje_sri = mensaje
        self.save(update_fields=["estado", "mensaje_sri", "updated_at"])

    # =====================================================
    # GUARDADO
    # =====================================================

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        if self.sucursal_id and not self.empresa_id:
            empresa_sucursal = getattr(self.sucursal, "empresa", None)
            if empresa_sucursal:
                self.empresa = empresa_sucursal

        if self.sucursal:
            establecimiento_sucursal = getattr(self.sucursal, "establecimiento", None)
            punto_emision_sucursal = getattr(self.sucursal, "punto_emision", None)

            if not self.establecimiento and establecimiento_sucursal:
                self.establecimiento = establecimiento_sucursal

            if not self.punto_emision and punto_emision_sucursal:
                self.punto_emision = punto_emision_sucursal

        if self.empresa:
            if not self.establecimiento:
                self.establecimiento = self.empresa.establecimiento
            if not self.punto_emision:
                self.punto_emision = self.empresa.punto_emision

        if not self.fecha_emision:
            self.fecha_emision = timezone.localdate()

        if not self.secuencial:
            self.secuencial = self.generar_siguiente_secuencial(
                empresa=self.empresa,
                establecimiento=self.establecimiento or "001",
                punto_emision=self.punto_emision or "001",
            )

        self.secuencial = str(self.secuencial).zfill(9)

        if not self.clave_acceso and self.empresa_id:
            self.clave_acceso = self.generar_clave_acceso()

        self.full_clean()

        for intento in range(3):
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if intento == 2 or not es_nuevo:
                    raise

                self.secuencial = self.generar_siguiente_secuencial(
                    empresa=self.empresa,
                    establecimiento=self.establecimiento,
                    punto_emision=self.punto_emision,
                )
                self.clave_acceso = self.generar_clave_acceso()


# =========================================================
# DETALLE FACTURA
# =========================================================

class DetalleFacturaVenta(models.Model):
    CODIGOS_IVA = [
        ("0", "0%"),
        ("4", "15%"),
    ]

    factura = models.ForeignKey(
        FacturaVenta,
        on_delete=models.CASCADE,
        related_name="detalles",
    )

    codigo_principal = models.CharField(max_length=50)
    codigo_auxiliar = models.CharField(max_length=50, blank=True, null=True)
    descripcion = models.CharField(max_length=500)

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0.000001"))],
    )

    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    descuento = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    precio_total_sin_impuesto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    codigo_impuesto = models.CharField(
        max_length=1,
        default="2",
        help_text="2 = IVA",
    )

    codigo_porcentaje_iva = models.CharField(
        max_length=1,
        choices=CODIGOS_IVA,
        default="4",
    )

    tarifa_iva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
    )

    base_imponible = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    valor_iva = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    unidad_medida = models.CharField(max_length=50, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Detalle de factura"
        verbose_name_plural = "Detalles de factura"
        ordering = ["id"]

    def __str__(self):
        return f"{self.descripcion} - {self.factura_id}"

    def clean(self):
        super().clean()

        if self.descuento < 0:
            raise ValidationError({"descuento": "El descuento no puede ser negativo."})

    def recalcular(self):
        subtotal = (self.cantidad * self.precio_unitario) - self.descuento
        if subtotal < 0:
            subtotal = Decimal("0.00")

        subtotal = subtotal.quantize(Decimal("0.01"))

        self.precio_total_sin_impuesto = subtotal
        self.base_imponible = subtotal

        if self.codigo_porcentaje_iva == "4":
            self.tarifa_iva = Decimal("15.00")
            self.valor_iva = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
        else:
            self.tarifa_iva = Decimal("0.00")
            self.valor_iva = Decimal("0.00")

    def save(self, *args, **kwargs):
        self.recalcular()
        super().save(*args, **kwargs)

        if self.factura_id:
            self.factura.recalcular_totales(guardar=True)

    def delete(self, *args, **kwargs):
        factura = self.factura
        super().delete(*args, **kwargs)
        if factura:
            factura.recalcular_totales(guardar=True)


class PagoFacturaVenta(models.Model):
    factura = models.ForeignKey(
        FacturaVenta,
        on_delete=models.CASCADE,
        related_name="pagos",
    )

    forma_pago = models.CharField(
        max_length=2,
        choices=FacturaVenta.FORMAS_PAGO,
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    plazo = models.PositiveIntegerField(default=0)
    unidad_tiempo = models.CharField(max_length=20, default="Días")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pago de factura"
        verbose_name_plural = "Pagos de factura"

    def __str__(self):
        return f"{self.factura.numero_factura} - {self.get_forma_pago_display()} - {self.total}"

    def clean(self):
        super().clean()

        if self.total <= Decimal("0.00"):
            raise ValidationError({
                "total": "El valor del pago debe ser mayor a 0."
            })

        if self.factura_id:
            total_otros_pagos = (
                self.factura.pagos.exclude(pk=self.pk).aggregate(total=Sum("total")).get("total")
                or Decimal("0.00")
            )

            total_con_este = total_otros_pagos + self.total

            if total_con_este > self.factura.importe_total:
                raise ValidationError({
                    "total": "La suma de los pagos no puede exceder el importe total de la factura."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)