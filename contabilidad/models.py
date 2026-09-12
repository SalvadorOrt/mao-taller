from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


CERO = Decimal("0.00")


# =========================================================
# PLAN DE CUENTAS
# =========================================================

class CuentaContable(models.Model):
    TIPOS = [
        ("ACTIVO", "Activo"),
        ("PASIVO", "Pasivo"),
        ("PATRIMONIO", "Patrimonio"),
        ("INGRESO", "Ingreso"),
        ("COSTO", "Costo"),
        ("GASTO", "Gasto"),
        ("ORDEN", "Cuenta de orden"),
    ]

    codigo = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    nombre = models.CharField(
        max_length=200,
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
    )

    cuenta_padre = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcuentas",
    )

    permite_movimiento = models.BooleanField(
        default=True,
    )

    activa = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Cuenta contable"
        verbose_name_plural = "Cuentas contables"

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# =========================================================
# PERIODOS CONTABLES
# =========================================================

class PeriodoContable(models.Model):
    ESTADOS = [
        ("ABIERTO", "Abierto"),
        ("CERRADO", "Cerrado"),
    ]

    anio = models.PositiveIntegerField()
    mes = models.PositiveSmallIntegerField()

    estado = models.CharField(
        max_length=10,
        choices=ESTADOS,
        default="ABIERTO",
    )

    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-anio", "-mes"]

        constraints = [
            models.UniqueConstraint(
                fields=["anio", "mes"],
                name="contabilidad_periodo_unico",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(mes__gte=1)
                    & models.Q(mes__lte=12)
                ),
                name="contabilidad_mes_valido",
            ),
        ]

    def __str__(self):
        return f"{self.mes:02d}/{self.anio} - {self.estado}"


# =========================================================
# ASIENTO CONTABLE
# =========================================================

class AsientoContable(models.Model):
    ESTADOS = [
        ("BORRADOR", "Borrador"),
        ("CONTABILIZADO", "Contabilizado"),
        ("ANULADO", "Anulado"),
    ]

    TIPOS_ORIGEN = [
        ("MANUAL", "Manual"),
        ("VENTA", "Venta"),
        ("COMPRA", "Compra"),
        ("COBRO", "Cobro"),
        ("PAGO", "Pago"),
        ("INVENTARIO", "Inventario"),
        ("AJUSTE", "Ajuste"),
    ]

    numero = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    fecha = models.DateField(
        db_index=True,
    )

    periodo = models.ForeignKey(
        PeriodoContable,
        on_delete=models.PROTECT,
        related_name="asientos",
    )

    descripcion = models.CharField(
        max_length=300,
    )

    tipo_origen = models.CharField(
        max_length=20,
        choices=TIPOS_ORIGEN,
        default="MANUAL",
    )

    origen_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    documento_referencia = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asientos_contables",
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="BORRADOR",
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-fecha", "-id"]

        indexes = [
            models.Index(
                fields=["tipo_origen", "origen_id"]
            ),
            models.Index(
                fields=["fecha", "estado"]
            ),
        ]

    @property
    def total_debe(self):
        return sum(
            (d.debe for d in self.detalles.all()),
            CERO,
        )

    @property
    def total_haber(self):
        return sum(
            (d.haber for d in self.detalles.all()),
            CERO,
        )

    @property
    def esta_cuadrado(self):
        return self.total_debe == self.total_haber

    def clean(self):
        if (
            self.periodo_id
            and self.periodo.estado == "CERRADO"
        ):
            raise ValidationError(
                "No se pueden registrar movimientos "
                "en un periodo cerrado."
            )

    def __str__(self):
        return f"{self.numero} - {self.descripcion}"


# =========================================================
# DETALLE DEL ASIENTO
# =========================================================

class DetalleAsiento(models.Model):
    asiento = models.ForeignKey(
        AsientoContable,
        on_delete=models.CASCADE,
        related_name="detalles",
    )

    cuenta = models.ForeignKey(
        CuentaContable,
        on_delete=models.PROTECT,
        related_name="movimientos",
    )

    descripcion = models.CharField(
        max_length=300,
        blank=True,
        null=True,
    )

    debe = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=CERO,
    )

    haber = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=CERO,
    )

    class Meta:
        ordering = ["id"]

    def clean(self):
        errores = {}

        if self.debe < CERO:
            errores["debe"] = (
                "El valor del debe no puede ser negativo."
            )

        if self.haber < CERO:
            errores["haber"] = (
                "El valor del haber no puede ser negativo."
            )

        if self.debe > CERO and self.haber > CERO:
            raise ValidationError(
                "Una línea no puede tener Debe y Haber "
                "al mismo tiempo."
            )

        if self.debe == CERO and self.haber == CERO:
            raise ValidationError(
                "La línea debe tener un valor en Debe o Haber."
            )

        if (
            self.cuenta_id
            and not self.cuenta.permite_movimiento
        ):
            errores["cuenta"] = (
                "La cuenta seleccionada no permite movimientos."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.asiento.numero} - "
            f"{self.cuenta.codigo}"
        )