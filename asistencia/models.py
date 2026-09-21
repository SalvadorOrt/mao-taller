import uuid

from django.conf import settings
from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# =========================================================
# UTILIDADES
# =========================================================

def ruta_foto_asistencia(
    instance,
    filename,
):
    """
    Guarda las fotografías separadas por fecha y usuario.

    Ejemplo:

        asistencia/
            2026/
                09/
                    21/
                        usuario_5/
                            abc123.jpg

    La fotografía es evidencia complementaria.

    IMPORTANTE:
    Una marcación puede existir perfectamente sin foto.
    """

    momento = (
        instance.fecha_hora
        if instance.fecha_hora
        else timezone.now()
    )

    momento_local = timezone.localtime(
        momento
    )

    extension = (
        filename.rsplit(
            ".",
            1,
        )[-1].lower()
        if "." in filename
        else "jpg"
    )

    extensiones_permitidas = {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }

    if (
        extension
        not in extensiones_permitidas
    ):
        extension = "jpg"

    nombre_archivo = (
        f"{uuid.uuid4().hex}."
        f"{extension}"
    )

    return (
        f"asistencia/"
        f"{momento_local.year}/"
        f"{momento_local.month:02d}/"
        f"{momento_local.day:02d}/"
        f"usuario_{instance.usuario_id}/"
        f"{nombre_archivo}"
    )


# =========================================================
# CONFIGURACIÓN DE ASISTENCIA DEL USUARIO
# =========================================================

class ConfiguracionAsistenciaUsuario(
    models.Model
):

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name=(
            "configuracion_asistencia"
        ),
    )

    # -----------------------------------------------------
    # PIN
    #
    # Nunca se guarda el PIN real.
    # Solo se conserva su hash.
    # -----------------------------------------------------

    pin_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
    )

    habilitado = models.BooleanField(
        default=True,
        help_text=(
            "Indica si este usuario puede "
            "utilizar el sistema de asistencia."
        ),
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        verbose_name = (
            "Configuración de asistencia"
        )

        verbose_name_plural = (
            "Configuraciones de asistencia"
        )

    # =====================================================
    # PIN
    # =====================================================

    def set_pin(
        self,
        pin,
    ):
        """
        Configura un PIN de asistencia
        de exactamente 6 dígitos.
        """

        pin = str(
            pin or ""
        ).strip()

        if (
            not pin.isdigit()
            or len(pin) != 6
        ):
            raise ValidationError(
                "El PIN de asistencia debe "
                "tener exactamente 6 dígitos."
            )

        self.pin_hash = make_password(
            pin
        )

    def check_pin(
        self,
        pin,
    ):
        """
        Comprueba el PIN contra el hash.
        """

        if not self.pin_hash:
            return False

        return check_password(
            str(
                pin or ""
            ),
            self.pin_hash,
        )

    @property
    def tiene_pin(
        self,
    ):
        return bool(
            self.pin_hash
        )

    @property
    def puede_marcar(
        self,
    ):
        """
        El trabajador puede marcar cuando:

        - configuración habilitada
        - usuario Django activo
        - tiene PIN configurado
        """

        return (
            self.habilitado
            and self.usuario.is_active
            and self.tiene_pin
        )

    def __str__(
        self,
    ):

        estado = (
            "HABILITADO"
            if self.habilitado
            else "DESHABILITADO"
        )

        return (
            f"{self.usuario.username} - "
            f"{estado}"
        )


# =========================================================
# HORARIO POR SUCURSAL
# =========================================================

class HorarioSucursal(
    models.Model
):

    sucursal = models.OneToOneField(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.CASCADE,
        related_name=(
            "horario_asistencia"
        ),
    )

    hora_entrada = models.TimeField()

    hora_salida = models.TimeField()

    # -----------------------------------------------------
    # ALMUERZO
    #
    # No hay una hora fija de inicio.
    # Se controla la duración.
    # -----------------------------------------------------

    minutos_almuerzo = (
        models.PositiveSmallIntegerField(
            default=60,
        )
    )

    # -----------------------------------------------------
    # TOLERANCIAS
    # -----------------------------------------------------

    tolerancia_entrada_minutos = (
        models.PositiveSmallIntegerField(
            default=0,
            help_text=(
                "Minutos de tolerancia después "
                "de la hora de entrada."
            ),
        )
    )

    tolerancia_almuerzo_minutos = (
        models.PositiveSmallIntegerField(
            default=0,
            help_text=(
                "Minutos adicionales permitidos "
                "sobre la duración del almuerzo."
            ),
        )
    )

    tolerancia_salida_minutos = (
        models.PositiveSmallIntegerField(
            default=0,
            help_text=(
                "Minutos permitidos para salir "
                "antes de la hora establecida."
            ),
        )
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

        verbose_name = (
            "Horario de sucursal"
        )

        verbose_name_plural = (
            "Horarios de sucursales"
        )

        ordering = [
            "sucursal__codigo",
        ]

    def clean(
        self,
    ):

        errores = {}

        if (
            self.hora_entrada
            and self.hora_salida
            and self.hora_entrada
            >= self.hora_salida
        ):
            errores[
                "hora_salida"
            ] = (
                "La hora de salida debe ser "
                "posterior a la hora de entrada."
            )

        if (
            self.minutos_almuerzo
            <= 0
        ):
            errores[
                "minutos_almuerzo"
            ] = (
                "La duración del almuerzo "
                "debe ser mayor que cero."
            )

        if errores:
            raise ValidationError(
                errores
            )

    def save(
        self,
        *args,
        **kwargs,
    ):

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    def __str__(
        self,
    ):

        return (
            f"{self.sucursal.codigo} | "
            f"{self.hora_entrada:%H:%M} - "
            f"{self.hora_salida:%H:%M} | "
            f"Almuerzo: "
            f"{self.minutos_almuerzo} min"
        )


# =========================================================
# TERMINAL AUTORIZADA
# =========================================================

class TerminalAsistencia(
    models.Model
):

    nombre = models.CharField(
        max_length=100,
    )

    codigo = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text=(
            "Ejemplo: NORTE-01 o SUR-01."
        ),
    )

    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name=(
            "terminales_asistencia"
        ),
    )

    # -----------------------------------------------------
    # TOKEN
    #
    # La aplicación de escritorio posee un token propio.
    # El servidor conserva únicamente el hash.
    # -----------------------------------------------------

    token_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
    )

    activa = models.BooleanField(
        default=True,
    )

    ultima_ip = (
        models.GenericIPAddressField(
            null=True,
            blank=True,
        )
    )

    ultima_conexion = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        ordering = [
            "sucursal__codigo",
            "nombre",
        ]

        verbose_name = (
            "Terminal de asistencia"
        )

        verbose_name_plural = (
            "Terminales de asistencia"
        )

    def clean(
        self,
    ):

        if self.codigo:
            self.codigo = (
                self.codigo
                .strip()
                .upper()
            )

        if self.nombre:
            self.nombre = (
                self.nombre
                .strip()
            )

    def save(
        self,
        *args,
        **kwargs,
    ):

        if self.codigo:
            self.codigo = (
                self.codigo
                .strip()
                .upper()
            )

        if self.nombre:
            self.nombre = (
                self.nombre
                .strip()
            )

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    # =====================================================
    # TOKEN DE TERMINAL
    # =====================================================

    def set_token(
        self,
        token,
    ):

        token = str(
            token or ""
        ).strip()

        if len(token) < 20:
            raise ValidationError(
                "El token de la terminal "
                "es demasiado corto."
            )

        self.token_hash = (
            make_password(
                token
            )
        )

    def check_token(
        self,
        token,
    ):

        if not self.token_hash:
            return False

        return check_password(
            str(
                token or ""
            ),
            self.token_hash,
        )

    @property
    def tiene_token(
        self,
    ):

        return bool(
            self.token_hash
        )

    def registrar_conexion(
        self,
        ip=None,
    ):

        self.ultima_conexion = (
            timezone.now()
        )

        if ip:
            self.ultima_ip = ip

        self.save(
            update_fields=[
                "ultima_conexion",
                "ultima_ip",
                "actualizado_en",
            ]
        )

    def __str__(
        self,
    ):

        estado = (
            "ACTIVA"
            if self.activa
            else "INACTIVA"
        )

        return (
            f"{self.codigo} - "
            f"{self.sucursal.codigo} - "
            f"{estado}"
        )


# =========================================================
# REGISTRO DE ASISTENCIA
# =========================================================

class RegistroAsistencia(
    models.Model
):

    # =====================================================
    # TIPOS DE MARCACIÓN
    # =====================================================

    ENTRADA = "ENTRADA"

    INICIO_ALMUERZO = (
        "INICIO_ALMUERZO"
    )

    FIN_ALMUERZO = (
        "FIN_ALMUERZO"
    )

    SALIDA = "SALIDA"

    TIPOS_MARCACION = [
        (
            ENTRADA,
            "Entrada",
        ),
        (
            INICIO_ALMUERZO,
            "Inicio de almuerzo",
        ),
        (
            FIN_ALMUERZO,
            "Fin de almuerzo",
        ),
        (
            SALIDA,
            "Salida",
        ),
    ]

    # =====================================================
    # UUID DE LA MARCACIÓN
    # =====================================================
    #
    # Es independiente del ID de PostgreSQL.
    #
    # Sirve especialmente para la aplicación de escritorio
    # cuando trabaja sin Internet.
    #
    # Ejemplo:
    #
    #     PC crea UUID X
    #            ↓
    #     intenta sincronizar
    #            ↓
    #     Django guarda UUID X
    #            ↓
    #     conexión se corta antes de la respuesta
    #            ↓
    #     PC reintenta UUID X
    #            ↓
    #     Django reconoce que ya existe
    #
    # Esto permite hacer la sincronización idempotente.
    # =====================================================

    uuid_marcacion = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    # =====================================================
    # TRABAJADOR
    # =====================================================

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name=(
            "registros_asistencia"
        ),
    )

    # =====================================================
    # SUCURSAL REAL
    # =====================================================
    #
    # No necesariamente coincide con usuario.sucursal.
    #
    # La sucursal real viene de la terminal utilizada.
    # =====================================================

    sucursal = models.ForeignKey(
        "ordenes_de_trabajo.Sucursal",
        on_delete=models.PROTECT,
        related_name=(
            "registros_asistencia"
        ),
    )

    # =====================================================
    # TERMINAL
    # =====================================================

    terminal = models.ForeignKey(
        TerminalAsistencia,
        on_delete=models.PROTECT,
        related_name="registros",
    )

    # =====================================================
    # TIPO
    # =====================================================

    tipo = models.CharField(
        max_length=30,
        choices=TIPOS_MARCACION,
        db_index=True,
    )

    # =====================================================
    # FECHA
    # =====================================================

    fecha = models.DateField(
        default=timezone.localdate,
        editable=False,
        db_index=True,
    )

    # =====================================================
    # FECHA/HORA EFECTIVA
    # =====================================================
    #
    # ONLINE:
    #
    #     hora del servidor
    #
    # OFFLINE:
    #
    #     hora reportada por el dispositivo
    #
    # Conservando además recibido_en.
    # =====================================================

    fecha_hora = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    # =====================================================
    # MOMENTO EN QUE DJANGO RECIBIÓ EL REGISTRO
    # =====================================================

    recibido_en = models.DateTimeField(
        auto_now_add=True,
    )

    # =====================================================
    # HORA DEL DISPOSITIVO
    # =====================================================
    #
    # Solo se utiliza para marcaciones originadas
    # mientras la PC estaba offline.
    # =====================================================

    fecha_hora_dispositivo = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    # =====================================================
    # ORIGEN OFFLINE
    # =====================================================

    es_offline = models.BooleanField(
        default=False,
        db_index=True,
    )

    # =====================================================
    # FOTOGRAFÍA
    # =====================================================
    #
    # SIEMPRE OPCIONAL.
    #
    # Una falla de webcam nunca debe impedir que la
    # asistencia sea registrada.
    # =====================================================

    fotografia = models.ImageField(
        upload_to=ruta_foto_asistencia,
        null=True,
        blank=True,
    )

    # =====================================================
    # EVIDENCIA TÉCNICA
    # =====================================================

    ip = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.TextField(
        blank=True,
        default="",
    )

    observacion = models.TextField(
        blank=True,
        null=True,
    )

    class Meta:

        ordering = [
            "-fecha_hora",
        ]

        verbose_name = (
            "Registro de asistencia"
        )

        verbose_name_plural = (
            "Registros de asistencia"
        )

        # -------------------------------------------------
        # Solo puede existir una marcación de cada tipo
        # para un trabajador en una fecha.
        # -------------------------------------------------

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "usuario",
                    "fecha",
                    "tipo",
                ],
                name=(
                    "asistencia_marcacion_"
                    "unica_usuario_fecha_tipo"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "usuario",
                    "fecha",
                ],
            ),

            models.Index(
                fields=[
                    "sucursal",
                    "fecha",
                ],
            ),

            models.Index(
                fields=[
                    "fecha",
                    "tipo",
                ],
            ),

            models.Index(
                fields=[
                    "terminal",
                    "fecha",
                ],
            ),

            models.Index(
                fields=[
                    "es_offline",
                    "fecha",
                ],
            ),
        ]

        permissions = [
            (
                "ver_todas_sucursales_asistencia",
                (
                    "Ver asistencia de "
                    "todas las sucursales"
                ),
            ),
            (
                "corregir_asistencia",
                "Corregir asistencia",
            ),
        ]

    def clean(
        self,
    ):

        errores = {}

        # -------------------------------------------------
        # La sucursal guardada debe corresponder
        # físicamente a la terminal utilizada.
        # -------------------------------------------------

        if (
            self.terminal_id
            and self.sucursal_id
            and self.terminal.sucursal_id
            != self.sucursal_id
        ):
            errores[
                "terminal"
            ] = (
                "La terminal seleccionada no "
                "pertenece a esta sucursal."
            )

        # -------------------------------------------------
        # Si es offline y se conoce una hora del
        # dispositivo, debe conservarse.
        #
        # No hacemos obligatorio el campo a nivel de modelo
        # porque los registros históricos podrían no tenerlo.
        # La capa de servicios será la que lo exija para
        # nuevas sincronizaciones offline.
        # -------------------------------------------------

        if errores:
            raise ValidationError(
                errores
            )

    def save(
        self,
        *args,
        **kwargs,
    ):

        # -------------------------------------------------
        # DERIVAR FECHA
        # -------------------------------------------------

        if self.fecha_hora:

            momento = (
                self.fecha_hora
            )

            if timezone.is_naive(
                momento
            ):
                momento = (
                    timezone.make_aware(
                        momento,
                        timezone
                        .get_current_timezone(),
                    )
                )

            self.fecha = (
                timezone.localtime(
                    momento
                )
                .date()
            )

        if self.observacion:
            self.observacion = (
                self.observacion
                .strip()
            )

        self.full_clean()

        super().save(
            *args,
            **kwargs,
        )

    def __str__(
        self,
    ):

        momento_local = (
            timezone.localtime(
                self.fecha_hora
            )
        )

        origen = (
            "OFFLINE"
            if self.es_offline
            else "ONLINE"
        )

        return (
            f"{self.usuario.username} | "
            f"{self.fecha} | "
            f"{self.get_tipo_display()} | "
            f"{momento_local:%H:%M:%S} | "
            f"{origen}"
        )


# =========================================================
# INCIDENCIAS DE ASISTENCIA
# =========================================================

class IncidenciaAsistencia(
    models.Model
):

    # =====================================================
    # TIPOS
    # =====================================================

    ATRASO_ENTRADA = (
        "ATRASO_ENTRADA"
    )

    EXCESO_ALMUERZO = (
        "EXCESO_ALMUERZO"
    )

    SALIDA_ANTICIPADA = (
        "SALIDA_ANTICIPADA"
    )

    MARCACION_FALTANTE = (
        "MARCACION_FALTANTE"
    )

    JORNADA_INCOMPLETA = (
        "JORNADA_INCOMPLETA"
    )

    MARCACION_OFFLINE = (
        "MARCACION_OFFLINE"
    )

    TIEMPO_POSTERIOR_JORNADA = (
        "TIEMPO_POSTERIOR_JORNADA"
    )

    CORRECCION_MANUAL = (
        "CORRECCION_MANUAL"
    )

    TIPOS_INCIDENCIA = [
        (
            ATRASO_ENTRADA,
            "Atraso de entrada",
        ),
        (
            EXCESO_ALMUERZO,
            "Exceso de almuerzo",
        ),
        (
            SALIDA_ANTICIPADA,
            "Salida anticipada",
        ),
        (
            MARCACION_FALTANTE,
            "Marcación faltante",
        ),
        (
            JORNADA_INCOMPLETA,
            "Jornada incompleta",
        ),
        (
            MARCACION_OFFLINE,
            "Marcación offline",
        ),
        (
            TIEMPO_POSTERIOR_JORNADA,
            (
                "Tiempo posterior "
                "a la jornada"
            ),
        ),
        (
            CORRECCION_MANUAL,
            "Corrección manual",
        ),
    ]

    # =====================================================
    # ESTADO
    # =====================================================

    PENDIENTE = "PENDIENTE"

    JUSTIFICADA = "JUSTIFICADA"

    NO_JUSTIFICADA = (
        "NO_JUSTIFICADA"
    )

    ESTADOS = [
        (
            PENDIENTE,
            "Pendiente",
        ),
        (
            JUSTIFICADA,
            "Justificada",
        ),
        (
            NO_JUSTIFICADA,
            "No justificada",
        ),
    ]

    # =====================================================
    # TRABAJADOR
    # =====================================================

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name=(
            "incidencias_asistencia"
        ),
    )

    fecha = models.DateField(
        db_index=True,
    )

    tipo = models.CharField(
        max_length=40,
        choices=TIPOS_INCIDENCIA,
        db_index=True,
    )

    # =====================================================
    # REGISTRO RELACIONADO
    # =====================================================
    #
    # Puede ser NULL.
    #
    # Ejemplo:
    # MARCACION_FALTANTE no necesariamente tiene
    # RegistroAsistencia relacionado.
    # =====================================================

    registro = models.ForeignKey(
        RegistroAsistencia,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidencias",
    )

    minutos = (
        models.PositiveIntegerField(
            default=0,
        )
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=PENDIENTE,
        db_index=True,
    )

    motivo = models.TextField(
        blank=True,
        null=True,
    )

    generado_automaticamente = (
        models.BooleanField(
            default=True,
        )
    )

    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name=(
            "incidencias_asistencia_revisadas"
        ),
    )

    revisado_en = (
        models.DateTimeField(
            null=True,
            blank=True,
        )
    )

    detalles = models.JSONField(
        default=dict,
        blank=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        ordering = [
            "-fecha",
            "-creado_en",
        ]

        verbose_name = (
            "Incidencia de asistencia"
        )

        verbose_name_plural = (
            "Incidencias de asistencia"
        )

        indexes = [
            models.Index(
                fields=[
                    "usuario",
                    "fecha",
                ],
            ),

            models.Index(
                fields=[
                    "estado",
                    "fecha",
                ],
            ),

            models.Index(
                fields=[
                    "tipo",
                    "fecha",
                ],
            ),
        ]

    def clean(
        self,
    ):

        if (
            self.estado
            in {
                self.JUSTIFICADA,
                self.NO_JUSTIFICADA,
            }
            and not self.revisado_por_id
        ):
            raise ValidationError(
                {
                    "revisado_por": (
                        "Debe indicar quién "
                        "revisó la incidencia."
                    )
                }
            )

    def marcar_justificada(
        self,
        usuario,
        motivo=None,
    ):

        self.estado = (
            self.JUSTIFICADA
        )

        self.revisado_por = (
            usuario
        )

        self.revisado_en = (
            timezone.now()
        )

        if motivo:
            self.motivo = (
                motivo.strip()
            )

        self.save()

    def marcar_no_justificada(
        self,
        usuario,
        motivo=None,
    ):

        self.estado = (
            self.NO_JUSTIFICADA
        )

        self.revisado_por = (
            usuario
        )

        self.revisado_en = (
            timezone.now()
        )

        if motivo:
            self.motivo = (
                motivo.strip()
            )

        self.save()

    def __str__(
        self,
    ):

        return (
            f"{self.usuario.username} | "
            f"{self.fecha} | "
            f"{self.get_tipo_display()} | "
            f"{self.minutos} min"
        )