from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# =========================================================
# OPCIONES GENERALES
# =========================================================

class EstadoRevision(models.TextChoices):
    NO_REVISADO = "NO_REVISADO", "No revisado"
    NRR = "NRR", "No requiere reparación"
    RRM = "RRM", "Requiere reparación menor"
    RRT = "RRT", "Requiere reparación total"


class RespuestaSiNo(models.TextChoices):
    NO_REVISADO = "NO_REVISADO", "No revisado"
    SI = "SI", "Sí"
    NO = "NO", "No"
    NO_APLICA = "NO_APLICA", "No aplica"


class EstadoAvaluo(models.TextChoices):
    BORRADOR = "BORRADOR", "Borrador"
    FINALIZADO = "FINALIZADO", "Finalizado"
    ANULADO = "ANULADO", "Anulado"


# =========================================================
# AVALÚO MECÁNICO PRINCIPAL
# =========================================================

class AvaluoMecanico(models.Model):
    RESULTADOS_GENERALES = [
        ("SIN_DEFINIR", "Sin definir"),
        ("BUEN_ESTADO", "Vehículo en buen estado"),
        ("MANTENIMIENTO", "Requiere mantenimiento"),
        ("REPARACION_MENOR", "Requiere reparación menor"),
        ("REPARACION_MAYOR", "Requiere reparación mayor"),
        ("NO_RECOMENDABLE", "No recomendable"),
    ]

    TIPOS_TRANSMISION = [
        ("NO_DEFINIDA", "No definida"),
        ("MANUAL", "Manual"),
        ("AUTOMATICA", "Automática"),
        ("CVT", "CVT"),
        ("DOBLE_EMBRAGUE", "Doble embrague"),
        ("OTRA", "Otra"),
    ]

    # =====================================================
    # IDENTIFICACIÓN
    # =====================================================

    numero_avaluo = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        db_index=True,
    )

    orden = models.OneToOneField(
        "ordenes_de_trabajo.OrdenTrabajo",
        on_delete=models.PROTECT,
        related_name="avaluo_mecanico",
        verbose_name="Orden de trabajo",
    )

    estado = models.CharField(
        max_length=15,
        choices=EstadoAvaluo.choices,
        default=EstadoAvaluo.BORRADOR,
        db_index=True,
    )

    resultado_general = models.CharField(
        max_length=30,
        choices=RESULTADOS_GENERALES,
        default="SIN_DEFINIR",
    )

    solicitado_por = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    fecha_avaluo = models.DateField(
        default=timezone.localdate,
    )

    # =====================================================
    # USUARIOS RESPONSABLES
    # =====================================================

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="avaluos_creados",
    )

    evaluador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="avaluos_evaluados",
        null=True,
        blank=True,
        verbose_name="Evaluador del taller",
    )

    responsable_taller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="avaluos_responsable_taller",
        null=True,
        blank=True,
    )

    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="avaluos_actualizados",
        null=True,
        blank=True,
    )

    # =====================================================
    # DATOS HISTÓRICOS DE LA ORDEN
    # Se copian al crear el avalúo para conservarlos.
    # =====================================================

    numero_orden_respaldo = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    sucursal_respaldo = models.CharField(
        max_length=150,
        null=True,
        blank=True,
    )

    cliente_respaldo = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    identificacion_cliente_respaldo = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    telefono_cliente_respaldo = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    direccion_cliente_respaldo = models.TextField(
        null=True,
        blank=True,
    )

    placa_respaldo = models.CharField(
        max_length=15,
        null=True,
        blank=True,
        db_index=True,
    )

    marca_respaldo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    modelo_respaldo = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    vehiculo_respaldo = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    anio_modelo_respaldo = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    color_respaldo = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    kilometraje_respaldo = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    chasis_respaldo = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    # =====================================================
    # DATOS TÉCNICOS DEL VEHÍCULO
    # =====================================================

    numero_motor = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    motor = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    cilindraje = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    tipo_transmision = models.CharField(
        max_length=20,
        choices=TIPOS_TRANSMISION,
        default="NO_DEFINIDA",
    )

    aire_acondicionado = models.BooleanField(
        null=True,
        blank=True,
    )

    vidrios_electricos = models.BooleanField(
        null=True,
        blank=True,
    )

    alarma = models.BooleanField(
        null=True,
        blank=True,
    )

    aros = models.BooleanField(
        null=True,
        blank=True,
    )

    radio = models.BooleanField(
        null=True,
        blank=True,
    )

    cierre_centralizado = models.BooleanField(
        null=True,
        blank=True,
    )

    ruido_motor_otros = models.TextField(
        null=True,
        blank=True,
    )

    # =====================================================
    # DIAGNÓSTICO GENERAL
    # =====================================================

    diagnostico_general = models.TextField(
        null=True,
        blank=True,
    )

    reparaciones_recomendadas = models.TextField(
        null=True,
        blank=True,
    )

    observaciones_generales = models.TextField(
        null=True,
        blank=True,
    )

    # =====================================================
    # VEHÍCULOS USADOS / PARTE DE PAGO
    # =====================================================

    aplica_vehiculo_usado = models.BooleanField(
        default=False,
    )

    recibido_como_parte_pago_de = models.CharField(
        max_length=250,
        null=True,
        blank=True,
    )

    vendedor_que_solicita = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    anio_matricula = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    anio_modelo_usado = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    cilindraje_usado = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    reserva_dominio = models.BooleanField(
        null=True,
        blank=True,
    )

    color_usado = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    propietario = models.CharField(
        max_length=200,
        null=True,
        blank=True,
    )

    telefono_propietario = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )

    direccion_propietario = models.TextField(
        null=True,
        blank=True,
    )

    identificacion_propietario = models.CharField(
        max_length=30,
        null=True,
        blank=True,
    )

    avaluo_comercial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    precio_recepcion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    costo_reparacion = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    costo_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # =====================================================
    # FIRMAS
    # =====================================================

    firma_evaluador = models.ImageField(
        upload_to="avaluos/firmas/evaluadores/%Y/%m/",
        null=True,
        blank=True,
    )

    firma_responsable = models.ImageField(
        upload_to="avaluos/firmas/responsables/%Y/%m/",
        null=True,
        blank=True,
    )

    # =====================================================
    # CONTROL
    # =====================================================

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    finalizado_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-fecha_avaluo", "-id"]
        verbose_name = "Avalúo mecánico"
        verbose_name_plural = "Avalúos mecánicos"

        indexes = [
            models.Index(
                fields=["estado", "fecha_avaluo"],
                name="avaluo_estado_fecha_idx",
            ),
            models.Index(
                fields=["placa_respaldo", "fecha_avaluo"],
                name="avaluo_placa_fecha_idx",
            ),
            models.Index(
                fields=["evaluador", "estado"],
                name="avaluo_eval_estado_idx",
            ),
        ]

    # =====================================================
    # NORMALIZACIÓN
    # =====================================================

    def normalizar_textos(self):
        campos = [
            "solicitado_por",
            "numero_orden_respaldo",
            "sucursal_respaldo",
            "cliente_respaldo",
            "identificacion_cliente_respaldo",
            "telefono_cliente_respaldo",
            "direccion_cliente_respaldo",
            "placa_respaldo",
            "marca_respaldo",
            "modelo_respaldo",
            "vehiculo_respaldo",
            "color_respaldo",
            "chasis_respaldo",
            "numero_motor",
            "motor",
            "cilindraje",
            "ruido_motor_otros",
            "diagnostico_general",
            "reparaciones_recomendadas",
            "observaciones_generales",
            "recibido_como_parte_pago_de",
            "vendedor_que_solicita",
            "cilindraje_usado",
            "color_usado",
            "propietario",
            "telefono_propietario",
            "direccion_propietario",
            "identificacion_propietario",
        ]

        for campo in campos:
            valor = getattr(self, campo, None)

            if isinstance(valor, str):
                valor = valor.strip()
                setattr(self, campo, valor or None)

        campos_upper = [
            "numero_orden_respaldo",
            "placa_respaldo",
            "marca_respaldo",
            "modelo_respaldo",
            "vehiculo_respaldo",
            "color_respaldo",
            "chasis_respaldo",
            "numero_motor",
            "motor",
            "cilindraje",
            "color_usado",
            "cilindraje_usado",
        ]

        for campo in campos_upper:
            valor = getattr(self, campo, None)

            if valor:
                setattr(self, campo, valor.upper())

    # =====================================================
    # COPIAR DATOS DESDE LA OT
    # =====================================================

    def cargar_datos_desde_orden(self):
        if not self.orden_id:
            return

        orden = self.orden
        expediente = orden.expediente
        cliente = orden.cliente

        self.numero_orden_respaldo = (
            self.numero_orden_respaldo
            or orden.numero_orden
        )

        self.sucursal_respaldo = (
            self.sucursal_respaldo
            or orden.sucursal.nombre
        )

        self.cliente_respaldo = (
            self.cliente_respaldo
            or orden.nombre_cliente_final
        )

        if cliente:
            self.identificacion_cliente_respaldo = (
                self.identificacion_cliente_respaldo
                or cliente.identificacion
            )

            self.telefono_cliente_respaldo = (
                self.telefono_cliente_respaldo
                or cliente.telefono
            )

            self.direccion_cliente_respaldo = (
                self.direccion_cliente_respaldo
                or cliente.direccion
            )

        self.placa_respaldo = (
            self.placa_respaldo
            or orden.placa
        )

        self.vehiculo_respaldo = (
            self.vehiculo_respaldo
            or orden.vehiculo
        )

        self.anio_modelo_respaldo = (
            self.anio_modelo_respaldo
            or orden.anio_vehiculo
        )

        self.color_respaldo = (
            self.color_respaldo
            or orden.color
        )

        self.kilometraje_respaldo = (
            self.kilometraje_respaldo
            if self.kilometraje_respaldo is not None
            else orden.kilometraje
        )

        if expediente:
            self.marca_respaldo = (
                self.marca_respaldo
                or expediente.marca_api
            )

            self.modelo_respaldo = (
                self.modelo_respaldo
                or expediente.modelo_api
            )

            self.chasis_respaldo = (
                self.chasis_respaldo
                or expediente.numero_chasis
            )

    # =====================================================
    # VALIDACIONES
    # =====================================================

    def clean(self):
        super().clean()

        self.normalizar_textos()

        errores = {}

        if not self.orden_id:
            errores["orden"] = (
                "Debe seleccionar una orden de trabajo."
            )

        # La OT debe estar abierta únicamente cuando se crea
        # inicialmente el avalúo.
        if (
            self.orden_id
            and not self.pk
            and self.orden.estado != "ABIERTA"
        ):
            errores["orden"] = (
                "Solo puede iniciar el avalúo de una orden abierta."
            )

        campos_monetarios = [
            "avaluo_comercial",
            "precio_recepcion",
            "costo_reparacion",
            "costo_total",
        ]

        for campo in campos_monetarios:
            valor = getattr(self, campo)

            if valor is not None and valor < Decimal("0.00"):
                errores[campo] = (
                    "El valor no puede ser negativo."
                )

        anio_actual = timezone.localdate().year + 1

        campos_anio = [
            "anio_modelo_respaldo",
            "anio_matricula",
            "anio_modelo_usado",
        ]

        for campo in campos_anio:
            valor = getattr(self, campo)

            if valor is not None:
                if valor < 1900 or valor > anio_actual:
                    errores[campo] = (
                        "El año ingresado no es válido."
                    )

        if self.estado == EstadoAvaluo.FINALIZADO:
            if not self.evaluador_id:
                errores["evaluador"] = (
                    "Debe seleccionar al evaluador del taller."
                )

            if self.resultado_general == "SIN_DEFINIR":
                errores["resultado_general"] = (
                    "Debe seleccionar el resultado general."
                )

        if errores:
            raise ValidationError(errores)

    # =====================================================
    # FINALIZAR
    # =====================================================

    def finalizar(self, usuario=None):
        self.estado = EstadoAvaluo.FINALIZADO
        self.finalizado_en = timezone.now()

        if usuario:
            self.actualizado_por = usuario

            if not self.evaluador_id:
                self.evaluador = usuario

        self.save()

    def reabrir(self, usuario=None):
        self.estado = EstadoAvaluo.BORRADOR
        self.finalizado_en = None

        if usuario:
            self.actualizado_por = usuario

        self.save()

    # =====================================================
    # SAVE
    # =====================================================

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        if es_nuevo:
            self.cargar_datos_desde_orden()

        self.normalizar_textos()

        if self.estado == EstadoAvaluo.FINALIZADO:
            if not self.finalizado_en:
                self.finalizado_en = timezone.now()
        else:
            self.finalizado_en = None

        self.full_clean()

        super().save(*args, **kwargs)

        # El número se genera usando el PK para evitar duplicados.
        if not self.numero_avaluo:
            numero = f"AV-{self.pk:06d}"

            type(self).objects.filter(
                pk=self.pk
            ).update(
                numero_avaluo=numero
            )

            self.numero_avaluo = numero

    def __str__(self):
        numero = self.numero_avaluo or "AV-SIN-NÚMERO"
        orden = self.numero_orden_respaldo or self.orden.numero_orden
        placa = self.placa_respaldo or "SIN PLACA"

        return f"{numero} | OT {orden} | {placa}"


# =========================================================
# CATÁLOGO DE ÍTEMS NRR / RRM / RRT
# =========================================================

class ItemInspeccionAvaluo(models.Model):
    SECCIONES = [
        ("EXTERIOR", "Apariencia exterior"),
        ("INTERIOR", "Apariencia interior"),
        ("MECANICA", "Revisión mecánica"),
        ("ELECTRICO", "Sistema eléctrico"),
        ("FRENOS", "Sistema de frenos"),
        ("OTROS", "Otros"),
    ]

    seccion = models.CharField(
        max_length=20,
        choices=SECCIONES,
        db_index=True,
    )

    codigo = models.CharField(
        max_length=50,
        unique=True,
    )

    nombre = models.CharField(
        max_length=180,
    )

    orden_visual = models.PositiveIntegerField(
        default=1,
    )

    activo = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "seccion",
            "orden_visual",
            "nombre",
        ]

        verbose_name = "Ítem de inspección"
        verbose_name_plural = "Ítems de inspección"

        constraints = [
            models.UniqueConstraint(
                fields=["seccion", "nombre"],
                name="avaluo_item_seccion_nombre_unico",
            ),
        ]

        indexes = [
            models.Index(
                fields=["seccion", "activo", "orden_visual"],
                name="avaluo_item_seccion_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.codigo:
            self.codigo = (
                self.codigo
                .strip()
                .upper()
                .replace(" ", "_")
            )

        if self.nombre:
            self.nombre = self.nombre.strip().upper()

        errores = {}

        if not self.codigo:
            errores["codigo"] = (
                "El código es obligatorio."
            )

        if not self.nombre:
            errores["nombre"] = (
                "El nombre es obligatorio."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.get_seccion_display()} | "
            f"{self.nombre}"
        )


# =========================================================
# RESULTADO NRR / RRM / RRT
# =========================================================

class ResultadoInspeccionAvaluo(models.Model):
    avaluo = models.ForeignKey(
        AvaluoMecanico,
        on_delete=models.CASCADE,
        related_name="resultados_inspeccion",
    )

    item = models.ForeignKey(
        ItemInspeccionAvaluo,
        on_delete=models.PROTECT,
        related_name="resultados",
    )

    estado = models.CharField(
        max_length=15,
        choices=EstadoRevision.choices,
        default=EstadoRevision.NO_REVISADO,
    )

    observacion = models.TextField(
        null=True,
        blank=True,
    )

    diagnostico = models.TextField(
        null=True,
        blank=True,
    )

    costo_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "item__seccion",
            "item__orden_visual",
            "item__nombre",
        ]

        verbose_name = "Resultado de inspección"
        verbose_name_plural = "Resultados de inspección"

        constraints = [
            models.UniqueConstraint(
                fields=["avaluo", "item"],
                name="avaluo_resultado_item_unico",
            ),
        ]

        indexes = [
            models.Index(
                fields=["avaluo", "estado"],
                name="avaluo_resultado_estado_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.observacion:
            self.observacion = self.observacion.strip()

        if self.diagnostico:
            self.diagnostico = self.diagnostico.strip()

        if (
            self.costo_estimado is not None
            and self.costo_estimado < Decimal("0.00")
        ):
            raise ValidationError({
                "costo_estimado": (
                    "El costo estimado no puede ser negativo."
                ),
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.avaluo.numero_avaluo} | "
            f"{self.item.nombre} | "
            f"{self.get_estado_display()}"
        )


# =========================================================
# CATÁLOGO DE REVISIONES SÍ / NO
# Partículas, fugas y otras comprobaciones.
# =========================================================

class ItemRevisionSiNo(models.Model):
    SECCIONES = [
        ("PARTICULAS_FUGAS", "Partículas y fugas"),
        ("MOTOR", "Motor"),
        ("FLUIDOS", "Fluidos"),
        ("OTROS", "Otros"),
    ]

    seccion = models.CharField(
        max_length=30,
        choices=SECCIONES,
        default="PARTICULAS_FUGAS",
    )

    codigo = models.CharField(
        max_length=50,
        unique=True,
    )

    nombre = models.CharField(
        max_length=250,
    )

    orden_visual = models.PositiveIntegerField(
        default=1,
    )

    activo = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "seccion",
            "orden_visual",
            "nombre",
        ]

        verbose_name = "Ítem de revisión Sí/No"
        verbose_name_plural = "Ítems de revisión Sí/No"

        constraints = [
            models.UniqueConstraint(
                fields=["seccion", "nombre"],
                name="avaluo_revision_sino_nombre_unico",
            ),
        ]

    def clean(self):
        super().clean()

        if self.codigo:
            self.codigo = (
                self.codigo
                .strip()
                .upper()
                .replace(" ", "_")
            )

        if self.nombre:
            self.nombre = self.nombre.strip().upper()

        errores = {}

        if not self.codigo:
            errores["codigo"] = "El código es obligatorio."

        if not self.nombre:
            errores["nombre"] = "El nombre es obligatorio."

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


# =========================================================
# RESULTADOS DE REVISIONES SÍ / NO
# =========================================================

class ResultadoRevisionSiNo(models.Model):
    avaluo = models.ForeignKey(
        AvaluoMecanico,
        on_delete=models.CASCADE,
        related_name="resultados_revision_sino",
    )

    item = models.ForeignKey(
        ItemRevisionSiNo,
        on_delete=models.PROTECT,
        related_name="resultados",
    )

    respuesta = models.CharField(
        max_length=15,
        choices=RespuestaSiNo.choices,
        default=RespuestaSiNo.NO_REVISADO,
    )

    observacion = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "item__seccion",
            "item__orden_visual",
        ]

        verbose_name = "Resultado de revisión Sí/No"
        verbose_name_plural = "Resultados de revisión Sí/No"

        constraints = [
            models.UniqueConstraint(
                fields=["avaluo", "item"],
                name="avaluo_revision_sino_item_unico",
            ),
        ]

    def clean(self):
        super().clean()

        if self.observacion:
            self.observacion = self.observacion.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.avaluo.numero_avaluo} | "
            f"{self.item.nombre} | "
            f"{self.get_respuesta_display()}"
        )


# =========================================================
# CATÁLOGO DE PRUEBA DE RUTA
# =========================================================

class ItemPruebaRuta(models.Model):
    codigo = models.CharField(
        max_length=50,
        unique=True,
    )

    pregunta = models.CharField(
        max_length=250,
    )

    permite_observacion = models.BooleanField(
        default=True,
    )

    orden_visual = models.PositiveIntegerField(
        default=1,
    )

    activo = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "orden_visual",
            "pregunta",
        ]

        verbose_name = "Pregunta de prueba de ruta"
        verbose_name_plural = "Preguntas de prueba de ruta"

    def clean(self):
        super().clean()

        if self.codigo:
            self.codigo = (
                self.codigo
                .strip()
                .upper()
                .replace(" ", "_")
            )

        if self.pregunta:
            self.pregunta = self.pregunta.strip()

        errores = {}

        if not self.codigo:
            errores["codigo"] = "El código es obligatorio."

        if not self.pregunta:
            errores["pregunta"] = (
                "La pregunta es obligatoria."
            )

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.pregunta


# =========================================================
# RESULTADO DE PRUEBA DE RUTA
# =========================================================

class ResultadoPruebaRuta(models.Model):
    avaluo = models.ForeignKey(
        AvaluoMecanico,
        on_delete=models.CASCADE,
        related_name="resultados_prueba_ruta",
    )

    item = models.ForeignKey(
        ItemPruebaRuta,
        on_delete=models.PROTECT,
        related_name="resultados",
    )

    respuesta = models.CharField(
        max_length=15,
        choices=RespuestaSiNo.choices,
        default=RespuestaSiNo.NO_REVISADO,
    )

    observacion = models.TextField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "item__orden_visual",
            "item__pregunta",
        ]

        verbose_name = "Resultado de prueba de ruta"
        verbose_name_plural = "Resultados de prueba de ruta"

        constraints = [
            models.UniqueConstraint(
                fields=["avaluo", "item"],
                name="avaluo_prueba_ruta_item_unico",
            ),
        ]

    def clean(self):
        super().clean()

        if self.observacion:
            self.observacion = self.observacion.strip()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.avaluo.numero_avaluo} | "
            f"{self.item.pregunta}"
        )


# =========================================================
# COMPRESIÓN DEL MOTOR
# =========================================================

class CompresionCilindro(models.Model):
    UNIDADES = [
        ("PSI", "PSI"),
        ("BAR", "Bar"),
        ("KPA", "kPa"),
    ]

    avaluo = models.ForeignKey(
        AvaluoMecanico,
        on_delete=models.CASCADE,
        related_name="compresiones_motor",
    )

    numero_cilindro = models.PositiveSmallIntegerField()

    valor = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    unidad = models.CharField(
        max_length=10,
        choices=UNIDADES,
        default="PSI",
    )

    observacion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["numero_cilindro"]

        verbose_name = "Compresión de cilindro"
        verbose_name_plural = "Compresiones de cilindros"

        constraints = [
            models.UniqueConstraint(
                fields=["avaluo", "numero_cilindro"],
                name="avaluo_compresion_cilindro_unico",
            ),
        ]

    def clean(self):
        super().clean()

        errores = {}

        if (
            self.numero_cilindro is None
            or self.numero_cilindro < 1
            or self.numero_cilindro > 16
        ):
            errores["numero_cilindro"] = (
                "El número de cilindro debe estar entre 1 y 16."
            )

        if self.valor is not None and self.valor < Decimal("0.00"):
            errores["valor"] = (
                "El valor de compresión no puede ser negativo."
            )

        if self.observacion:
            self.observacion = self.observacion.strip()

        if errores:
            raise ValidationError(errores)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        valor = (
            f"{self.valor} {self.unidad}"
            if self.valor is not None
            else "SIN VALOR"
        )

        return (
            f"{self.avaluo.numero_avaluo} | "
            f"Cilindro {self.numero_cilindro}: {valor}"
        )


# =========================================================
# FOTOGRAFÍAS DEL AVALÚO
# =========================================================

class FotoAvaluo(models.Model):
    TIPOS_FOTO = [
        ("FRONTAL", "Parte frontal"),
        ("POSTERIOR", "Parte posterior"),
        ("LATERAL_IZQUIERDO", "Lateral izquierdo"),
        ("LATERAL_DERECHO", "Lateral derecho"),
        ("MOTOR", "Motor"),
        ("INTERIOR", "Interior"),
        ("TABLERO", "Tablero"),
        ("KILOMETRAJE", "Kilometraje"),
        ("CHASIS", "Chasis / VIN"),
        ("MATRICULA", "Matrícula"),
        ("DANIO", "Daño encontrado"),
        ("DOCUMENTO", "Documento"),
        ("OTRA", "Otra"),
    ]

    avaluo = models.ForeignKey(
        AvaluoMecanico,
        on_delete=models.CASCADE,
        related_name="fotografias",
    )

    imagen = models.ImageField(
        upload_to="avaluos/fotos/%Y/%m/",
    )

    tipo_foto = models.CharField(
        max_length=30,
        choices=TIPOS_FOTO,
        default="OTRA",
    )

    descripcion = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    orden_visual = models.PositiveIntegerField(
        default=1,
    )

    subida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fotos_avaluos_subidas",
    )

    fecha_subida = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "orden_visual",
            "fecha_subida",
            "id",
        ]

        verbose_name = "Fotografía del avalúo"
        verbose_name_plural = "Fotografías del avalúo"

        indexes = [
            models.Index(
                fields=["avaluo", "tipo_foto"],
                name="avaluo_foto_tipo_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.descripcion:
            self.descripcion = self.descripcion.strip()

        if not self.imagen:
            raise ValidationError({
                "imagen": "Debe seleccionar una fotografía.",
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.avaluo.numero_avaluo} | "
            f"{self.get_tipo_foto_display()}"
        )