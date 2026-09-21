import logging

from datetime import datetime, timedelta
from math import ceil
from uuid import UUID
from .fotos import preparar_fotografia_sellada
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    ConfiguracionAsistenciaUsuario,
    HorarioSucursal,
    IncidenciaAsistencia,
    RegistroAsistencia,
    TerminalAsistencia,
)


logger = logging.getLogger(__name__)


# =========================================================
# SECUENCIA OFICIAL DE MARCACIONES
# =========================================================

SECUENCIA_MARCACIONES = [
    RegistroAsistencia.ENTRADA,
    RegistroAsistencia.INICIO_ALMUERZO,
    RegistroAsistencia.FIN_ALMUERZO,
    RegistroAsistencia.SALIDA,
]


# =========================================================
# UTILIDADES DE FECHA Y HORA
# =========================================================

def _combinar_fecha_hora(
    fecha,
    hora,
):
    """
    Combina una fecha y una hora usando la zona horaria
    configurada actualmente en Django.
    """

    valor = datetime.combine(
        fecha,
        hora,
    )

    return timezone.make_aware(
        valor,
        timezone.get_current_timezone(),
    )


def _normalizar_datetime(
    valor,
):
    """
    Garantiza que un datetime tenga zona horaria.
    """

    if valor is None:
        return None

    if timezone.is_naive(
        valor
    ):
        return timezone.make_aware(
            valor,
            timezone.get_current_timezone(),
        )

    return valor


def _minutos_entre(
    inicio,
    fin,
):
    """
    Calcula minutos entre dos datetime.

    Cualquier fracción positiva se redondea hacia arriba.

    Ejemplos:

        60 segundos  -> 1 minuto
        61 segundos  -> 2 minutos
        119 segundos -> 2 minutos
    """

    if (
        inicio is None
        or fin is None
    ):
        return 0

    segundos = (
        fin - inicio
    ).total_seconds()

    if segundos <= 0:
        return 0

    return int(
        ceil(
            segundos / 60
        )
    )


# =========================================================
# UTILIDADES UUID
# =========================================================

def _normalizar_uuid(
    valor,
):
    """
    Convierte el UUID recibido por la terminal a UUID.

    Acepta:

        UUID(...)
        "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

    Si no se recibió UUID retorna None.

    ONLINE:
        temporalmente permitimos None para mantener
        compatibilidad con el endpoint actual.

    OFFLINE:
        registrar_marcacion exigirá UUID.
    """

    if valor in {
        None,
        "",
    }:
        return None

    if isinstance(
        valor,
        UUID,
    ):
        return valor

    try:

        return UUID(
            str(
                valor
            ).strip()
        )

    except (
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:

        raise ValidationError(
            "El UUID de la marcación "
            "no es válido."
        ) from exc


# =========================================================
# VALIDAR TIPO DE MARCACIÓN
# =========================================================

def _validar_tipo_marcacion(
    tipo,
):
    """
    Valida un tipo enviado durante una sincronización
    offline.

    IMPORTANTE:

    En modo ONLINE el cliente nunca selecciona el tipo.
    """

    tipo = str(
        tipo or ""
    ).strip().upper()

    if (
        tipo
        not in SECUENCIA_MARCACIONES
    ):
        raise ValidationError(
            "El tipo de marcación "
            "recibido no es válido."
        )

    return tipo


# =========================================================
# AUTENTICAR USUARIO DE ASISTENCIA
# =========================================================

def autenticar_usuario_asistencia(
    identificador,
    pin,
):
    """
    Identifica al trabajador mediante:

    - username
    o
    - cédula

    Después valida su PIN independiente de asistencia.

    IMPORTANTE:

    La contraseña del ERP NO se utiliza para marcar.
    """

    Usuario = get_user_model()

    identificador = str(
        identificador or ""
    ).strip()

    pin = str(
        pin or ""
    ).strip()

    if not identificador:
        raise ValidationError(
            "Debes ingresar tu usuario o cédula."
        )

    if not pin:
        raise ValidationError(
            "Debes ingresar tu PIN de asistencia."
        )

    # =====================================================
    # BUSCAR POR USERNAME
    # =====================================================

    usuario = (
        Usuario.objects
        .select_related(
            "sucursal"
        )
        .filter(
            username__iexact=(
                identificador
            ),
        )
        .first()
    )

    # =====================================================
    # SI NO EXISTE, BUSCAR POR CÉDULA
    # =====================================================

    if usuario is None:

        usuario = (
            Usuario.objects
            .select_related(
                "sucursal"
            )
            .filter(
                cedula=identificador,
            )
            .first()
        )

    # =====================================================
    # NO ENCONTRADO
    # =====================================================

    if usuario is None:
        raise ValidationError(
            "Usuario o PIN incorrecto."
        )

    # =====================================================
    # DESHABILITADO
    # =====================================================

    if not usuario.is_active:
        raise ValidationError(
            "El usuario está deshabilitado."
        )

    # =====================================================
    # CONFIGURACIÓN DE ASISTENCIA
    # =====================================================

    try:

        configuracion = (
            ConfiguracionAsistenciaUsuario
            .objects
            .get(
                usuario=usuario,
            )
        )

    except (
        ConfiguracionAsistenciaUsuario
        .DoesNotExist
    ):

        raise ValidationError(
            "Este usuario no tiene "
            "asistencia configurada."
        )

    if not configuracion.habilitado:
        raise ValidationError(
            "La asistencia de este usuario "
            "está deshabilitada."
        )

    if not configuracion.tiene_pin:
        raise ValidationError(
            "Este usuario todavía no tiene "
            "un PIN de asistencia configurado."
        )

    if not configuracion.check_pin(
        pin
    ):
        raise ValidationError(
            "Usuario o PIN incorrecto."
        )

    return usuario


# =========================================================
# AUTENTICAR TERMINAL
# =========================================================

def autenticar_terminal(
    codigo,
    token,
):
    """
    Valida una terminal de asistencia.

    Ejemplos:

        NORTE-01
        SUR-01

    La sucursal de la terminal determina dónde se
    encuentra físicamente la marcación.
    """

    codigo = str(
        codigo or ""
    ).strip().upper()

    token = str(
        token or ""
    ).strip()

    if not codigo:
        raise ValidationError(
            "No se recibió el código "
            "de la terminal."
        )

    if not token:
        raise ValidationError(
            "No se recibió la credencial "
            "de la terminal."
        )

    try:

        terminal = (
            TerminalAsistencia.objects
            .select_related(
                "sucursal"
            )
            .get(
                codigo=codigo,
            )
        )

    except TerminalAsistencia.DoesNotExist:

        raise ValidationError(
            "Terminal no autorizada."
        )

    if not terminal.activa:
        raise ValidationError(
            "Esta terminal está deshabilitada."
        )

    if not terminal.tiene_token:
        raise ValidationError(
            "La terminal no tiene una "
            "credencial configurada."
        )

    if not terminal.check_token(
        token
    ):
        raise ValidationError(
            "Credencial de terminal incorrecta."
        )

    return terminal


# =========================================================
# OBTENER HORARIO DE SUCURSAL
# =========================================================

def obtener_horario_sucursal(
    sucursal,
):
    """
    Devuelve el horario correspondiente a la sucursal
    donde físicamente ocurre la marcación.

    NO utiliza:

        usuario.sucursal

    Utiliza:

        terminal.sucursal
    """

    if sucursal is None:
        raise ValidationError(
            "No se pudo determinar la sucursal "
            "de la marcación."
        )

    try:

        return (
            HorarioSucursal.objects
            .select_related(
                "sucursal"
            )
            .get(
                sucursal=sucursal,
                activo=True,
            )
        )

    except HorarioSucursal.DoesNotExist:

        raise ValidationError(
            f"La sucursal {sucursal} no tiene "
            "un horario de asistencia activo."
        )


# =========================================================
# OBTENER MARCACIONES DEL DÍA
# =========================================================

def obtener_marcaciones_dia(
    usuario,
    fecha=None,
):
    """
    Obtiene TODAS las marcaciones del trabajador durante
    una fecha, independientemente de la sucursal.

    Ejemplo:

        ENTRADA          -> NORTE
        INICIO_ALMUERZO  -> NORTE
        FIN_ALMUERZO     -> SUR
        SALIDA           -> SUR
    """

    if fecha is None:
        fecha = (
            timezone.localdate()
        )

    return (
        RegistroAsistencia.objects
        .filter(
            usuario=usuario,
            fecha=fecha,
        )
        .select_related(
            "usuario",
            "sucursal",
            "terminal",
        )
        .order_by(
            "fecha_hora",
            "id",
        )
    )


# =========================================================
# DETERMINAR SIGUIENTE MARCACIÓN
# =========================================================

def obtener_siguiente_tipo_marcacion(
    usuario,
    fecha=None,
):
    """
    Django determina automáticamente la secuencia:

        0 -> ENTRADA
        1 -> INICIO_ALMUERZO
        2 -> FIN_ALMUERZO
        3 -> SALIDA
        4 -> JORNADA COMPLETA

    En modo ONLINE este es siempre el mecanismo utilizado.

    En sincronización OFFLINE también utilizamos esta
    secuencia para comprobar que el tipo guardado por la
    terminal corresponde realmente al siguiente esperado.
    """

    if fecha is None:
        fecha = (
            timezone.localdate()
        )

    tipos_existentes = list(
        RegistroAsistencia.objects
        .filter(
            usuario=usuario,
            fecha=fecha,
        )
        .order_by(
            "fecha_hora",
            "id",
        )
        .values_list(
            "tipo",
            flat=True,
        )
    )

    # =====================================================
    # JORNADA COMPLETA
    # =====================================================

    if (
        len(
            tipos_existentes
        )
        >= len(
            SECUENCIA_MARCACIONES
        )
    ):
        return None

    # =====================================================
    # VALIDAR SECUENCIA EXISTENTE
    # =====================================================

    secuencia_esperada = (
        SECUENCIA_MARCACIONES[
            :len(
                tipos_existentes
            )
        ]
    )

    if (
        tipos_existentes
        != secuencia_esperada
    ):
        raise ValidationError(
            "La jornada contiene una secuencia "
            "de marcaciones inconsistente. "
            "Debe ser revisada por un administrador."
        )

    return (
        SECUENCIA_MARCACIONES[
            len(
                tipos_existentes
            )
        ]
    )


# =========================================================
# BUSCAR MARCACIÓN POR UUID
# =========================================================

def obtener_marcacion_por_uuid(
    uuid_marcacion,
):
    """
    Busca una marcación utilizando el UUID generado
    por la PC.

    Retorna None cuando no existe.
    """

    uuid_marcacion = (
        _normalizar_uuid(
            uuid_marcacion
        )
    )

    if uuid_marcacion is None:
        return None

    return (
        RegistroAsistencia.objects
        .select_related(
            "usuario",
            "sucursal",
            "terminal",
        )
        .filter(
            uuid_marcacion=(
                uuid_marcacion
            ),
        )
        .first()
    )


# =========================================================
# VALIDAR REINTENTO IDEMPOTENTE
# =========================================================

def _validar_reintento_idempotente(
    *,
    registro,
    usuario,
    terminal,
    es_offline,
    tipo_marcacion=None,
    fecha_hora_dispositivo=None,
):
    """
    Si llega nuevamente un UUID que ya existe,
    comprobamos que realmente representa la MISMA
    marcación.

    Esto evita que alguien reutilice accidentalmente
    un UUID para otro usuario o terminal.
    """

    if registro.usuario_id != usuario.pk:
        raise ValidationError(
            "El UUID recibido ya pertenece "
            "a otro usuario."
        )

    if registro.terminal_id != terminal.pk:
        raise ValidationError(
            "El UUID recibido ya pertenece "
            "a otra terminal."
        )

    # =====================================================
    # ORIGEN ONLINE / OFFLINE
    # =====================================================

    if (
        bool(
            registro.es_offline
        )
        != bool(
            es_offline
        )
    ):
        raise ValidationError(
            "El UUID recibido ya existe con "
            "un origen diferente."
        )

    # =====================================================
    # VALIDACIONES OFFLINE
    # =====================================================

    if es_offline:

        tipo_marcacion = (
            _validar_tipo_marcacion(
                tipo_marcacion
            )
        )

        if (
            registro.tipo
            != tipo_marcacion
        ):
            raise ValidationError(
                "El UUID recibido ya existe "
                "con otro tipo de marcación."
            )

        momento = (
            _normalizar_datetime(
                fecha_hora_dispositivo
            )
        )

        if momento is None:
            raise ValidationError(
                "No se recibió la fecha y hora "
                "original de la marcación offline."
            )

        if (
            registro.fecha_hora_dispositivo
            is not None
            and registro.fecha_hora_dispositivo
            != momento
        ):
            raise ValidationError(
                "El UUID recibido ya existe "
                "con otra fecha u hora."
            )

    return registro


# =========================================================
# ACTUALIZAR CONEXIÓN DE TERMINAL
# =========================================================

def _actualizar_conexion_terminal(
    terminal,
    momento,
    ip=None,
):
    """
    Actualiza la última conexión conocida de la terminal.
    """

    terminal.ultima_conexion = (
        momento
    )

    campos = [
        "ultima_conexion",
        "actualizado_en",
    ]

    if ip:
        terminal.ultima_ip = ip

        campos.append(
            "ultima_ip"
        )

    terminal.save(
        update_fields=campos
    )


# =========================================================
# CREAR O ACTUALIZAR INCIDENCIA AUTOMÁTICA
# =========================================================

def _crear_incidencia(
    *,
    usuario,
    fecha,
    tipo,
    registro=None,
    minutos=0,
    detalles=None,
):
    """
    Crea una incidencia.

    Si pertenece a una marcación concreta, evita duplicarla
    cuando un registro vuelve a analizarse.
    """

    minutos = max(
        int(
            minutos or 0
        ),
        0,
    )

    detalles = (
        detalles
        if isinstance(
            detalles,
            dict,
        )
        else {}
    )

    # =====================================================
    # INCIDENCIA VINCULADA
    # =====================================================

    if registro is not None:

        incidencia, _ = (
            IncidenciaAsistencia.objects
            .update_or_create(
                registro=registro,
                tipo=tipo,
                defaults={
                    "usuario": usuario,
                    "fecha": fecha,
                    "minutos": minutos,
                    "detalles": detalles,
                    "generado_automaticamente": True,
                },
            )
        )

        return incidencia

    # =====================================================
    # INCIDENCIA SIN REGISTRO
    # =====================================================

    return (
        IncidenciaAsistencia.objects
        .create(
            usuario=usuario,
            fecha=fecha,
            tipo=tipo,
            registro=None,
            minutos=minutos,
            detalles=detalles,
            generado_automaticamente=True,
        )
    )


# =========================================================
# ANALIZAR ENTRADA
# =========================================================

def _analizar_entrada(
    registro,
    horario,
):
    """
    Detecta atraso según el horario de la sucursal
    donde físicamente se realizó la entrada.
    """

    hora_programada = (
        _combinar_fecha_hora(
            registro.fecha,
            horario.hora_entrada,
        )
    )

    limite_con_tolerancia = (
        hora_programada
        + timedelta(
            minutes=(
                horario
                .tolerancia_entrada_minutos
            )
        )
    )

    # =====================================================
    # A TIEMPO
    # =====================================================

    if (
        registro.fecha_hora
        <= limite_con_tolerancia
    ):
        return None

    # =====================================================
    # ATRASO REAL
    # =====================================================

    atraso_real = (
        _minutos_entre(
            hora_programada,
            registro.fecha_hora,
        )
    )

    atraso_aplicable = (
        _minutos_entre(
            limite_con_tolerancia,
            registro.fecha_hora,
        )
    )

    return _crear_incidencia(
        usuario=registro.usuario,
        fecha=registro.fecha,
        tipo=(
            IncidenciaAsistencia
            .ATRASO_ENTRADA
        ),
        registro=registro,
        minutos=atraso_aplicable,
        detalles={
            "sucursal": (
                registro
                .sucursal
                .codigo
            ),

            "terminal": (
                registro
                .terminal
                .codigo
            ),

            "hora_esperada": (
                horario
                .hora_entrada
                .strftime(
                    "%H:%M"
                )
            ),

            "hora_real": (
                timezone.localtime(
                    registro.fecha_hora
                ).strftime(
                    "%H:%M:%S"
                )
            ),

            "tolerancia_minutos": (
                horario
                .tolerancia_entrada_minutos
            ),

            "atraso_real_minutos": (
                atraso_real
            ),

            "atraso_aplicable_minutos": (
                atraso_aplicable
            ),
        },
    )


# =========================================================
# ANALIZAR FIN DE ALMUERZO
# =========================================================

def _analizar_fin_almuerzo(
    registro,
    horario,
):
    """
    Calcula cuánto duró el almuerzo.

    El trabajador puede iniciar el almuerzo en una sucursal
    y terminarlo en otra.
    """

    inicio = (
        RegistroAsistencia.objects
        .filter(
            usuario=registro.usuario,
            fecha=registro.fecha,
            tipo=(
                RegistroAsistencia
                .INICIO_ALMUERZO
            ),
        )
        .select_related(
            "sucursal",
            "terminal",
        )
        .order_by(
            "fecha_hora",
            "id",
        )
        .first()
    )

    if inicio is None:
        raise ValidationError(
            "No existe una marcación de "
            "inicio de almuerzo."
        )

    if (
        registro.fecha_hora
        <= inicio.fecha_hora
    ):
        raise ValidationError(
            "La hora de fin de almuerzo debe "
            "ser posterior al inicio de almuerzo."
        )

    duracion_real = (
        _minutos_entre(
            inicio.fecha_hora,
            registro.fecha_hora,
        )
    )

    limite_con_tolerancia = (
        horario.minutos_almuerzo
        + horario
        .tolerancia_almuerzo_minutos
    )

    if (
        duracion_real
        <= limite_con_tolerancia
    ):
        return None

    exceso = (
        duracion_real
        - limite_con_tolerancia
    )

    return _crear_incidencia(
        usuario=registro.usuario,
        fecha=registro.fecha,
        tipo=(
            IncidenciaAsistencia
            .EXCESO_ALMUERZO
        ),
        registro=registro,
        minutos=exceso,
        detalles={
            "sucursal_inicio": (
                inicio
                .sucursal
                .codigo
            ),

            "sucursal_fin": (
                registro
                .sucursal
                .codigo
            ),

            "terminal_inicio": (
                inicio
                .terminal
                .codigo
            ),

            "terminal_fin": (
                registro
                .terminal
                .codigo
            ),

            "inicio_almuerzo": (
                timezone.localtime(
                    inicio.fecha_hora
                ).strftime(
                    "%H:%M:%S"
                )
            ),

            "fin_almuerzo": (
                timezone.localtime(
                    registro.fecha_hora
                ).strftime(
                    "%H:%M:%S"
                )
            ),

            "duracion_real_minutos": (
                duracion_real
            ),

            "duracion_programada_minutos": (
                horario
                .minutos_almuerzo
            ),

            "tolerancia_minutos": (
                horario
                .tolerancia_almuerzo_minutos
            ),

            "exceso_minutos": (
                exceso
            ),
        },
    )


# =========================================================
# ANALIZAR SALIDA
# =========================================================

def _analizar_salida(
    registro,
    horario,
):
    """
    Analiza la salida según la sucursal donde físicamente
    se realiza.

    Detecta:

    - salida anticipada
    - tiempo posterior a jornada

    El tiempo posterior NO se convierte automáticamente
    en horas extra aprobadas.
    """

    hora_programada = (
        _combinar_fecha_hora(
            registro.fecha,
            horario.hora_salida,
        )
    )

    tolerancia = (
        horario
        .tolerancia_salida_minutos
    )

    limite_anticipado = (
        hora_programada
        - timedelta(
            minutes=tolerancia
        )
    )

    # =====================================================
    # SALIDA ANTICIPADA
    # =====================================================

    if (
        registro.fecha_hora
        < limite_anticipado
    ):

        minutos = (
            _minutos_entre(
                registro.fecha_hora,
                limite_anticipado,
            )
        )

        return _crear_incidencia(
            usuario=registro.usuario,
            fecha=registro.fecha,
            tipo=(
                IncidenciaAsistencia
                .SALIDA_ANTICIPADA
            ),
            registro=registro,
            minutos=minutos,
            detalles={
                "sucursal": (
                    registro
                    .sucursal
                    .codigo
                ),

                "terminal": (
                    registro
                    .terminal
                    .codigo
                ),

                "hora_esperada": (
                    horario
                    .hora_salida
                    .strftime(
                        "%H:%M"
                    )
                ),

                "hora_real": (
                    timezone.localtime(
                        registro.fecha_hora
                    ).strftime(
                        "%H:%M:%S"
                    )
                ),

                "tolerancia_minutos": (
                    tolerancia
                ),

                "salida_anticipada_minutos": (
                    minutos
                ),
            },
        )

    # =====================================================
    # TIEMPO POSTERIOR A JORNADA
    # =====================================================

    if (
        registro.fecha_hora
        > hora_programada
    ):

        minutos = (
            _minutos_entre(
                hora_programada,
                registro.fecha_hora,
            )
        )

        if minutos > 0:

            return _crear_incidencia(
                usuario=registro.usuario,
                fecha=registro.fecha,
                tipo=(
                    IncidenciaAsistencia
                    .TIEMPO_POSTERIOR_JORNADA
                ),
                registro=registro,
                minutos=minutos,
                detalles={
                    "sucursal": (
                        registro
                        .sucursal
                        .codigo
                    ),

                    "terminal": (
                        registro
                        .terminal
                        .codigo
                    ),

                    "hora_programada": (
                        horario
                        .hora_salida
                        .strftime(
                            "%H:%M"
                        )
                    ),

                    "hora_real": (
                        timezone.localtime(
                            registro.fecha_hora
                        ).strftime(
                            "%H:%M:%S"
                        )
                    ),

                    "minutos_posteriores": (
                        minutos
                    ),

                    "es_hora_extra_aprobada": (
                        False
                    ),
                },
            )

    return None


# =========================================================
# ANALIZAR MARCACIÓN
# =========================================================

def analizar_marcacion(
    registro,
):
    """
    Analiza automáticamente una marcación.

    El horario se obtiene mediante:

        registro.sucursal

    NO mediante:

        usuario.sucursal
    """

    horario = (
        obtener_horario_sucursal(
            registro.sucursal
        )
    )

    incidencia = None

    # =====================================================
    # ENTRADA
    # =====================================================

    if (
        registro.tipo
        == RegistroAsistencia.ENTRADA
    ):

        incidencia = (
            _analizar_entrada(
                registro,
                horario,
            )
        )

    # =====================================================
    # INICIO DE ALMUERZO
    # =====================================================

    elif (
        registro.tipo
        == RegistroAsistencia
        .INICIO_ALMUERZO
    ):

        pass

    # =====================================================
    # FIN DE ALMUERZO
    # =====================================================

    elif (
        registro.tipo
        == RegistroAsistencia
        .FIN_ALMUERZO
    ):

        incidencia = (
            _analizar_fin_almuerzo(
                registro,
                horario,
            )
        )

    # =====================================================
    # SALIDA
    # =====================================================

    elif (
        registro.tipo
        == RegistroAsistencia.SALIDA
    ):

        incidencia = (
            _analizar_salida(
                registro,
                horario,
            )
        )

    # =====================================================
    # INCIDENCIA POR ORIGEN OFFLINE
    # =====================================================

    if registro.es_offline:

        _crear_incidencia(
            usuario=registro.usuario,
            fecha=registro.fecha,
            tipo=(
                IncidenciaAsistencia
                .MARCACION_OFFLINE
            ),
            registro=registro,
            minutos=0,
            detalles={
                "sucursal": (
                    registro
                    .sucursal
                    .codigo
                ),

                "terminal": (
                    registro
                    .terminal
                    .codigo
                ),

                "uuid_marcacion": (
                    str(
                        registro
                        .uuid_marcacion
                    )
                ),

                "fecha_hora_dispositivo": (
                    (
                        registro
                        .fecha_hora_dispositivo
                        .isoformat()
                    )
                    if (
                        registro
                        .fecha_hora_dispositivo
                    )
                    else None
                ),

                "recibido_en": (
                    (
                        registro
                        .recibido_en
                        .isoformat()
                    )
                    if registro.recibido_en
                    else None
                ),
            },
        )

    return incidencia


# =========================================================
# REGISTRAR MARCACIÓN
# =========================================================

@transaction.atomic
def registrar_marcacion(
    *,
    usuario,
    terminal,

    # -----------------------------------------------------
    # UUID generado por la PC.
    #
    # ONLINE:
    # todavía puede ser None para compatibilidad.
    #
    # OFFLINE:
    # es obligatorio.
    # -----------------------------------------------------

    uuid_marcacion=None,

    # -----------------------------------------------------
    # SOLO OFFLINE.
    #
    # ONLINE siempre debe ser None.
    # -----------------------------------------------------

    tipo_marcacion=None,

    ip=None,

    user_agent="",

    es_offline=False,

    fecha_hora_dispositivo=None,
):
    """
    Registra una marcación de asistencia.

    =======================================================
    ONLINE
    =======================================================

    - El servidor utiliza su propia hora.
    - Django decide automáticamente el tipo.
    - El cliente NO puede escoger Entrada/Salida/etc.
    - Puede incluir un UUID generado por la terminal.

    =======================================================
    OFFLINE
    =======================================================

    - La PC creó el UUID al momento de marcar.
    - La PC conserva la hora original.
    - La PC conserva el tipo que correspondía localmente.
    - Cuando vuelve Internet envía esos datos.
    - Django verifica que la secuencia sea coherente.
    - Se genera incidencia MARCACION_OFFLINE.

    =======================================================
    IDEMPOTENCIA
    =======================================================

    Si llega nuevamente un UUID que ya existe:

        NO crea otra marcación.

    Devuelve el registro existente después de validar
    que pertenezca al mismo usuario y terminal.

    =======================================================
    FOTO
    =======================================================

    La fotografía NO se procesa aquí.

    Primero se guarda la asistencia.

    Posteriormente:

        adjuntar_fotografia_opcional()

    De esta forma una falla de cámara o almacenamiento
    nunca elimina una marcación válida.
    """

    recibido_ahora = (
        timezone.now()
    )

    # =====================================================
    # VALIDAR USUARIO
    # =====================================================

    if usuario is None:
        raise ValidationError(
            "No se recibió un usuario."
        )

    if not usuario.is_active:
        raise ValidationError(
            "El usuario está deshabilitado."
        )

    try:

        configuracion = (
            ConfiguracionAsistenciaUsuario
            .objects
            .select_for_update()
            .get(
                usuario=usuario,
            )
        )

    except (
        ConfiguracionAsistenciaUsuario
        .DoesNotExist
    ):

        raise ValidationError(
            "El usuario no tiene "
            "asistencia configurada."
        )

    if not configuracion.puede_marcar:
        raise ValidationError(
            "El usuario no está habilitado "
            "para registrar asistencia."
        )

    # =====================================================
    # VALIDAR TERMINAL
    # =====================================================

    if terminal is None:
        raise ValidationError(
            "No se recibió una terminal."
        )

    try:

        terminal = (
            TerminalAsistencia.objects
            .select_for_update()
            .select_related(
                "sucursal"
            )
            .get(
                pk=terminal.pk,
            )
        )

    except TerminalAsistencia.DoesNotExist:

        raise ValidationError(
            "La terminal ya no existe."
        )

    if not terminal.activa:
        raise ValidationError(
            "La terminal está deshabilitada."
        )

    # =====================================================
    # VALIDAR HORARIO DE SUCURSAL REAL
    # =====================================================

    obtener_horario_sucursal(
        terminal.sucursal
    )

    # =====================================================
    # NORMALIZAR UUID
    # =====================================================

    uuid_marcacion = (
        _normalizar_uuid(
            uuid_marcacion
        )
    )

    # =====================================================
    # OFFLINE EXIGE UUID
    # =====================================================

    if (
        es_offline
        and uuid_marcacion is None
    ):
        raise ValidationError(
            "Una marcación offline debe "
            "incluir su UUID."
        )

    # =====================================================
    # COMPROBAR SI EL UUID YA EXISTE
    # =====================================================

    if uuid_marcacion is not None:

        registro_existente = (
            RegistroAsistencia.objects
            .select_for_update()
            .select_related(
                "usuario",
                "sucursal",
                "terminal",
            )
            .filter(
                uuid_marcacion=(
                    uuid_marcacion
                )
            )
            .first()
        )

        if registro_existente is not None:

            _validar_reintento_idempotente(
                registro=registro_existente,
                usuario=usuario,
                terminal=terminal,
                es_offline=es_offline,
                tipo_marcacion=(
                    tipo_marcacion
                ),
                fecha_hora_dispositivo=(
                    fecha_hora_dispositivo
                ),
            )

            _actualizar_conexion_terminal(
                terminal,
                recibido_ahora,
                ip,
            )

            # ---------------------------------------------
            # MISMO UUID:
            #
            # devolvemos el registro original.
            # NO generamos otro.
            # ---------------------------------------------

            return registro_existente

    # =====================================================
    # DETERMINAR FECHA/HORA
    # =====================================================

    if es_offline:

        # -------------------------------------------------
        # UUID ya fue exigido arriba.
        # -------------------------------------------------

        if (
            fecha_hora_dispositivo
            is None
        ):
            raise ValidationError(
                "Una marcación offline debe "
                "tener fecha y hora del dispositivo."
            )

        fecha_hora_dispositivo = (
            _normalizar_datetime(
                fecha_hora_dispositivo
            )
        )

        # -------------------------------------------------
        # El tipo solamente es aceptado en modo offline.
        # -------------------------------------------------

        tipo_marcacion = (
            _validar_tipo_marcacion(
                tipo_marcacion
            )
        )

        momento_marcacion = (
            fecha_hora_dispositivo
        )

    else:

        # -------------------------------------------------
        # ONLINE:
        #
        # El cliente jamás debe seleccionar el tipo.
        # -------------------------------------------------

        if tipo_marcacion not in {
            None,
            "",
        }:
            raise ValidationError(
                "En una marcación online el tipo "
                "es determinado por el servidor."
            )

        # -------------------------------------------------
        # ONLINE:
        #
        # Nunca confiamos en el reloj de Windows.
        # -------------------------------------------------

        momento_marcacion = (
            recibido_ahora
        )

        fecha_hora_dispositivo = (
            None
        )

    # =====================================================
    # FECHA LOCAL
    # =====================================================

    fecha_local = (
        timezone.localtime(
            momento_marcacion
        ).date()
    )

    # =====================================================
    # BLOQUEAR MARCACIONES EXISTENTES DEL DÍA
    # =====================================================

    list(
        RegistroAsistencia.objects
        .select_for_update()
        .filter(
            usuario=usuario,
            fecha=fecha_local,
        )
        .order_by(
            "fecha_hora",
            "id",
        )
    )

    # =====================================================
    # SIGUIENTE TIPO ESPERADO POR EL SERVIDOR
    # =====================================================

    siguiente_tipo = (
        obtener_siguiente_tipo_marcacion(
            usuario,
            fecha_local,
        )
    )

    if siguiente_tipo is None:
        raise ValidationError(
            "La jornada de esta fecha ya tiene "
            "las cuatro marcaciones."
        )

    # =====================================================
    # ONLINE
    # =====================================================

    if not es_offline:

        tipo_final = (
            siguiente_tipo
        )

    # =====================================================
    # OFFLINE
    # =====================================================

    else:

        # -------------------------------------------------
        # La terminal puede informar qué tipo guardó
        # localmente, PERO Django verifica la secuencia.
        # -------------------------------------------------

        if (
            tipo_marcacion
            != siguiente_tipo
        ):
            raise ValidationError(
                (
                    "La marcación offline no coincide "
                    "con la secuencia esperada. "
                    f"Se esperaba "
                    f"{siguiente_tipo} "
                    f"y se recibió "
                    f"{tipo_marcacion}."
                )
            )

        tipo_final = (
            tipo_marcacion
        )

    # =====================================================
    # DATOS DEL REGISTRO
    # =====================================================

    datos_registro = {
        "usuario": usuario,

        # -------------------------------------------------
        # SUCURSAL REAL:
        #
        # terminal.sucursal
        #
        # NO:
        #
        # usuario.sucursal
        # -------------------------------------------------

        "sucursal": (
            terminal.sucursal
        ),

        "terminal": terminal,

        "tipo": tipo_final,

        "fecha_hora": (
            momento_marcacion
        ),

        "ip": ip,

        "user_agent": (
            str(
                user_agent or ""
            )
        ),

        "es_offline": (
            es_offline
        ),

        "fecha_hora_dispositivo": (
            fecha_hora_dispositivo
        ),
    }

    # =====================================================
    # UUID
    # =====================================================
    #
    # Si la PC envió uno, utilizamos exactamente ese.
    #
    # Si online todavía no envió UUID, dejamos que el
    # default=uuid.uuid4 del modelo lo genere.
    # =====================================================

    if uuid_marcacion is not None:

        datos_registro[
            "uuid_marcacion"
        ] = uuid_marcacion

    registro = (
        RegistroAsistencia(
            **datos_registro
        )
    )

    # =====================================================
    # GUARDAR
    # =====================================================

    try:

        # -------------------------------------------------
        # SAVEPOINT interno.
        #
        # Si PostgreSQL detecta una colisión de UUID,
        # podemos recuperarnos sin romper la transacción
        # exterior.
        # -------------------------------------------------

        with transaction.atomic():

            registro.save()

    except IntegrityError as exc:

        # =================================================
        # POSIBLE REINTENTO SIMULTÁNEO DEL MISMO UUID
        # =================================================

        if uuid_marcacion is not None:

            existente = (
                RegistroAsistencia.objects
                .select_related(
                    "usuario",
                    "sucursal",
                    "terminal",
                )
                .filter(
                    uuid_marcacion=(
                        uuid_marcacion
                    )
                )
                .first()
            )

            if existente is not None:

                _validar_reintento_idempotente(
                    registro=existente,
                    usuario=usuario,
                    terminal=terminal,
                    es_offline=es_offline,
                    tipo_marcacion=(
                        tipo_marcacion
                    ),
                    fecha_hora_dispositivo=(
                        fecha_hora_dispositivo
                    ),
                )

                _actualizar_conexion_terminal(
                    terminal,
                    recibido_ahora,
                    ip,
                )

                return existente

        # =================================================
        # OTRO DUPLICADO:
        #
        # por ejemplo usuario + fecha + tipo
        # =================================================

        raise ValidationError(
            "Esta marcación ya fue registrada "
            "o existe otra marcación equivalente."
        ) from exc

    # =====================================================
    # ANALIZAR INCIDENCIAS
    # =====================================================

    analizar_marcacion(
        registro
    )

    # =====================================================
    # ACTUALIZAR CONEXIÓN
    # =====================================================

    _actualizar_conexion_terminal(
        terminal,
        recibido_ahora,
        ip,
    )

    return registro


# =========================================================
# ADJUNTAR FOTOGRAFÍA OPCIONAL
# =========================================================
def adjuntar_fotografia_opcional(
    registro,
    fotografia,
):
    """
    Adjunta la fotografía después de que la marcación
    ya fue guardada.

    La foto se sella con:

    - tipo de marcación
    - ONLINE/OFFLINE
    - fecha
    - hora
    - sucursal
    - trabajador
    - referencia UUID

    Si cualquier cosa falla, la asistencia NO se elimina.
    """

    if not fotografia:

        return False

    if registro.fotografia:

        return True

    try:

        (
            nombre_archivo,
            contenido,
        ) = preparar_fotografia_sellada(
            registro,
            fotografia,
        )

        registro.fotografia.save(
            nombre_archivo,
            contenido,
            save=True,
        )

        return True

    except Exception:

        logger.exception(
            (
                "No fue posible guardar/sellar "
                "la fotografía de asistencia "
                "del registro %s."
            ),
            registro.pk,
        )

        return False

# =========================================================
# RESUMEN DE JORNADA
# =========================================================

def obtener_resumen_jornada(
    usuario,
    fecha=None,
):
    """
    Devuelve el resumen completo de la jornada.

    Las marcaciones pueden pertenecer a distintas
    sucursales.
    """

    if fecha is None:
        fecha = (
            timezone.localdate()
        )

    registros = list(
        obtener_marcaciones_dia(
            usuario,
            fecha,
        )
    )

    por_tipo = {
        registro.tipo: registro
        for registro in registros
    }

    entrada = (
        por_tipo.get(
            RegistroAsistencia
            .ENTRADA
        )
    )

    inicio_almuerzo = (
        por_tipo.get(
            RegistroAsistencia
            .INICIO_ALMUERZO
        )
    )

    fin_almuerzo = (
        por_tipo.get(
            RegistroAsistencia
            .FIN_ALMUERZO
        )
    )

    salida = (
        por_tipo.get(
            RegistroAsistencia
            .SALIDA
        )
    )

    # =====================================================
    # DURACIÓN DEL ALMUERZO
    # =====================================================

    duracion_almuerzo = None

    if (
        inicio_almuerzo
        and fin_almuerzo
    ):

        duracion_almuerzo = (
            _minutos_entre(
                inicio_almuerzo
                .fecha_hora,

                fin_almuerzo
                .fecha_hora,
            )
        )

    # =====================================================
    # SIGUIENTE MARCACIÓN
    # =====================================================

    siguiente_tipo = (
        obtener_siguiente_tipo_marcacion(
            usuario,
            fecha,
        )
    )

    # =====================================================
    # INCIDENCIAS
    # =====================================================

    incidencias = (
        IncidenciaAsistencia.objects
        .filter(
            usuario=usuario,
            fecha=fecha,
        )
        .select_related(
            "registro",
            "registro__sucursal",
            "registro__terminal",
        )
        .order_by(
            "creado_en"
        )
    )

    # =====================================================
    # SUCURSALES UTILIZADAS
    # =====================================================

    sucursales = []

    for registro in registros:

        codigo = (
            registro
            .sucursal
            .codigo
        )

        if (
            codigo
            not in sucursales
        ):
            sucursales.append(
                codigo
            )

    # =====================================================
    # UUIDS DE LA JORNADA
    # =====================================================

    uuids = [
        str(
            registro.uuid_marcacion
        )
        for registro in registros
    ]

    # =====================================================
    # RESPUESTA
    # =====================================================

    return {
        "fecha": fecha,

        "usuario": usuario,

        "entrada": entrada,

        "inicio_almuerzo": (
            inicio_almuerzo
        ),

        "fin_almuerzo": (
            fin_almuerzo
        ),

        "salida": salida,

        "duracion_almuerzo_minutos": (
            duracion_almuerzo
        ),

        "cantidad_marcaciones": (
            len(
                registros
            )
        ),

        "jornada_completa": (
            len(
                registros
            )
            == len(
                SECUENCIA_MARCACIONES
            )
        ),

        "siguiente_tipo": (
            siguiente_tipo
        ),

        "sucursales": (
            sucursales
        ),

        "uuids": (
            uuids
        ),

        "incidencias": (
            incidencias
        ),
    }