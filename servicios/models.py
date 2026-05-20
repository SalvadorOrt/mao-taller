from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Max, Min

class ServicioCatalogo(models.Model):
    CATEGORIAS = [
        ("MEC", "Mecánica"),
        ("PIN", "Pintura"),
        ("END", "Enderezada"),
        ("ELE", "Electricidad"),
        ("EXT", "Trabajo Externo"),
    ]

    TIPOS_SERVICIO = [
        ("SIMPLE", "Simple"),
        ("PAQUETE", "Paquete con procedimientos"),
        ("VARIABLE", "Precio variable"),
    ]

    categoria = models.CharField(max_length=3, choices=CATEGORIAS, db_index=True)
    codigo = models.CharField(max_length=50, unique=True, db_index=True)
    descripcion = models.CharField(max_length=255)

    tipo_servicio = models.CharField(
        max_length=20,
        choices=TIPOS_SERVICIO,
        default="SIMPLE",
        db_index=True,
    )

    precio_sugerido = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    requiere_tipo_tarifa = models.BooleanField(default=False)
    requiere_variante = models.BooleanField(default=False)
    activo = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["categoria", "descripcion"]
        verbose_name = "Servicio"
        verbose_name_plural = "Servicios"
        indexes = [
            models.Index(fields=["categoria", "activo"]),
            models.Index(fields=["descripcion"]),
            models.Index(fields=["codigo", "activo"]),
        ]

    def clean(self):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()

        if self.descripcion:
            self.descripcion = self.descripcion.strip()

        if not self.codigo:
            raise ValidationError({"codigo": "El código del servicio es obligatorio."})

        if not self.descripcion:
            raise ValidationError({"descripcion": "La descripción del servicio es obligatoria."})

        if self.precio_sugerido is None or self.precio_sugerido < 0:
            raise ValidationError({"precio_sugerido": "El precio sugerido no puede ser negativo."})
        if self.requiere_tipo_tarifa or self.requiere_variante:
            self.tipo_servicio = "VARIABLE"
            
    def save(self, *args, **kwargs):
        if self.codigo:
            self.codigo = self.codigo.strip().upper()

        if self.descripcion:
            self.descripcion = self.descripcion.strip()

        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def es_externo(self):
        return self.categoria == "EXT"

    @property
    def es_interno(self):
        return self.categoria in {"MEC", "PIN", "END", "ELE"}

    def obtener_precio_referencial(self, sucursal=None, tipo_tarifa=None, variante="NORMAL"):
        """
        Devuelve el precio configurado según sucursal, tarifa y variante.
        Si no existe configuración, usa precio_sugerido.
        """
        queryset = self.precios_configurados.all()

        tipo_tarifa_final = tipo_tarifa if self.requiere_tipo_tarifa and tipo_tarifa else "NO_APLICA"
        variante_final = variante if self.requiere_variante and variante else "NORMAL"

        if sucursal is not None:
            queryset = queryset.filter(sucursal=sucursal)

        queryset = queryset.filter(
            tipo_tarifa_vehiculo=tipo_tarifa_final,
            variante_precio=variante_final,
        )

        precio_cfg = queryset.first()
        if precio_cfg:
            return precio_cfg.precio

        return self.precio_sugerido

    def obtener_estadisticas_historicas(self, sucursal=None, tipo_tarifa=None, variante="NORMAL"):
        from ordenes_de_trabajo.models import OrdenServicioDetalle

        queryset = OrdenServicioDetalle.objects.filter(servicio=self)

        tipo_tarifa_final = tipo_tarifa if tipo_tarifa else "NO_APLICA"
        variante_final = variante if variante else "NORMAL"

        queryset = queryset.filter(
            tipo_tarifa_aplicada=tipo_tarifa_final,
            variante_precio_aplicada=variante_final,
        )

        if sucursal is not None:
            queryset = queryset.filter(orden__sucursal=sucursal)

        stats = queryset.aggregate(
            promedio=Avg("precio_unitario"),
            minimo=Min("precio_unitario"),
            maximo=Max("precio_unitario"),
        )

        return {
            "cantidad_registros": queryset.count(),
            "promedio": stats["promedio"],
            "minimo": stats["minimo"],
            "maximo": stats["maximo"],
        }

    def obtener_precio_inteligente(self, sucursal=None, tipo_tarifa=None, variante="NORMAL"):
        """
        Combina:
        - precio configurado / referencial
        - promedio histórico real

        Regla:
        - si hay histórico, mezcla 60% precio base + 40% promedio histórico
        - si no hay histórico, usa precio base
        """
        precio_base = self.obtener_precio_referencial(
            sucursal=sucursal,
            tipo_tarifa=tipo_tarifa,
            variante=variante,
        )

        historico = self.obtener_estadisticas_historicas(
            sucursal=sucursal,
            tipo_tarifa=tipo_tarifa if tipo_tarifa else "NO_APLICA",
            variante=variante if variante else "NORMAL",
        )

        promedio = historico["promedio"]

        if promedio is not None:
            precio = (Decimal("0.60") * precio_base) + (Decimal("0.40") * promedio)
        else:
            precio = precio_base

        return precio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def obtener_resumen_precio(self, sucursal=None, tipo_tarifa=None, variante="NORMAL"):
        tipo_tarifa_final = tipo_tarifa if self.requiere_tipo_tarifa and tipo_tarifa else "NO_APLICA"
        variante_final = variante if self.requiere_variante and variante else "NORMAL"

        precio_base = self.obtener_precio_referencial(
            sucursal=sucursal,
            tipo_tarifa=tipo_tarifa_final,
            variante=variante_final,
        )

        historico = self.obtener_estadisticas_historicas(
            sucursal=sucursal,
            tipo_tarifa=tipo_tarifa_final,
            variante=variante_final,
        )

        precio_inteligente = self.obtener_precio_inteligente(
            sucursal=sucursal,
            tipo_tarifa=tipo_tarifa_final,
            variante=variante_final,
        )

        return {
            "servicio_id": self.id,
            "codigo": self.codigo,
            "descripcion": self.descripcion,
            "categoria": self.categoria,
            "categoria_display": self.get_categoria_display(),
            "es_interno": self.es_interno,
            "es_externo": self.es_externo,
            "sucursal_id": sucursal.id if sucursal else None,
            "sucursal_codigo": sucursal.codigo if sucursal else None,
            "tipo_tarifa_aplicada": tipo_tarifa_final,
            "variante_aplicada": variante_final,
            "precio_sugerido": self.precio_sugerido,
            "precio_base": precio_base,
            "precio_promedio_historico": historico["promedio"],
            "precio_minimo_historico": historico["minimo"],
            "precio_maximo_historico": historico["maximo"],
            "cantidad_historial": historico["cantidad_registros"],
            "precio_recomendado": precio_inteligente,
        }

    def __str__(self):
        return f"[{self.codigo}] {self.get_categoria_display()} - {self.descripcion}"

class ServicioProcedimiento(models.Model):
    servicio = models.ForeignKey(
        ServicioCatalogo,
        on_delete=models.CASCADE,
        related_name="procedimientos",
    )

    descripcion = models.CharField(
        max_length=300,
        help_text="Tarea interna incluida dentro del servicio."
    )

    orden = models.PositiveIntegerField(default=1)

    obligatorio = models.BooleanField(
        default=True,
        help_text="Indica si esta tarea siempre debe hacerse dentro del servicio."
    )

    visible_en_ot = models.BooleanField(
        default=True,
        help_text="Permite mostrar esta tarea como checklist interno en la OT."
    )

    class Meta:
        ordering = ["servicio", "orden", "id"]
        verbose_name = "Procedimiento de servicio"
        verbose_name_plural = "Procedimientos de servicios"

    def clean(self):
        if not self.descripcion or not self.descripcion.strip():
            raise ValidationError("La descripción del procedimiento es obligatoria.")

    def save(self, *args, **kwargs):
        if self.descripcion:
            self.descripcion = self.descripcion.strip().upper()

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.servicio.codigo} - {self.descripcion}"
class PrecioServicio(models.Model):
    TIPOS_TARIFA_VEHICULO = [
        ("NO_APLICA", "No aplica"),
        ("AUTO", "Auto"),
        ("AUTO_3P", "Auto 3 puertas"),
        ("AUTO_5P", "Auto 5 puertas"),
        ("SUV_3P", "SUV 3 puertas"),
        ("SUV_5P", "SUV 5 puertas"),
        ("CAMIONETA_CS", "Camioneta cabina sencilla"),
        ("CAMIONETA_DC", "Camioneta doble cabina"),
        ("CAMIONETA_GRANDE", "Camioneta grande"),
    ]

    VARIANTES_PRECIO = [
        ("NORMAL", "Normal"),
        ("REPINTADO", "Repintado"),
        ("NUEVO", "Nuevo"),
        ("TRICAPA", "Tricapa / Candys"),
        ("ESPECIAL", "Color especial"),
    ]

    servicio = models.ForeignKey(
        ServicioCatalogo,
        related_name="precios_configurados",
        on_delete=models.CASCADE,
    )
    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name="precios_servicio",
        null=True,
        blank=True,
    )
    tipo_tarifa_vehiculo = models.CharField(
        max_length=20,
        choices=TIPOS_TARIFA_VEHICULO,
        default="NO_APLICA",
    )
    variante_precio = models.CharField(
        max_length=20,
        choices=VARIANTES_PRECIO,
        default="NORMAL",
    )
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        ordering = ["sucursal__codigo", "servicio__descripcion", "tipo_tarifa_vehiculo", "variante_precio"]
        verbose_name = "Precio de servicio"
        verbose_name_plural = "Precios de servicios"
        constraints = [
            models.UniqueConstraint(
                fields=["servicio", "sucursal", "tipo_tarifa_vehiculo", "variante_precio"],
                name="uq_precio_servicio_sucursal_tarifa_variante",
            )
        ]
        indexes = [
            models.Index(fields=["sucursal", "servicio"]),
            models.Index(fields=["servicio", "tipo_tarifa_vehiculo"]),
            models.Index(fields=["servicio", "variante_precio"]),
            models.Index(fields=["sucursal", "tipo_tarifa_vehiculo", "variante_precio"]),
        ]

    def clean(self):
        errores = {}

        if not self.servicio_id:
            errores["servicio"] = "Debe seleccionar un servicio."
        '''
        if not self.sucursal_id:
            errores["sucursal"] = "Debe seleccionar una sucursal."
        '''
        if self.precio is None or self.precio < 0:
            errores["precio"] = "El precio no puede ser negativo."

        if errores:
            raise ValidationError(errores)

        servicio = self.servicio

        if not servicio.requiere_tipo_tarifa:
            self.tipo_tarifa_vehiculo = "NO_APLICA"

        if not servicio.requiere_variante:
            self.variante_precio = "NORMAL"

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        sucursal = self.sucursal.codigo if self.sucursal else "GENERAL"

        return (
            f"{sucursal} | "
            f"{self.servicio.codigo} - {self.servicio.descripcion} | "
            f"{self.get_tipo_tarifa_vehiculo_display()} | "
            f"{self.get_variante_precio_display()} | "
            f"${self.precio}"
        )
    
