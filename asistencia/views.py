import logging
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (
    ConfiguracionAsistenciaUsuario,
    RegistroAsistencia,
)
from .services import (
    adjuntar_fotografia_opcional,
    autenticar_terminal,
    autenticar_usuario_asistencia,
    obtener_marcacion_por_uuid,
    obtener_resumen_jornada,
    registrar_marcacion,
)


logger = logging.getLogger(__name__)


# =========================================================
# CONFIGURACIÓN
# =========================================================

MAX_FOTO_BYTES = 5 * 1024 * 1024  # 5 MB

TIPOS_IMAGEN_PERMITIDOS = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}


# =========================================================
# UTILIDADES DE REQUEST
# =========================================================

def _obtener_ip(request):
    """
    Durante desarrollo usamos REMOTE_ADDR.

    En producción, cuando esté detrás de Nginx y
    Cloudflare, se configurará la IP real correctamente.
    """

    return request.META.get(
        "REMOTE_ADDR"
    )


def _obtener_user_agent(request):
    return (
        request.META.get(
            "HTTP_USER_AGENT",
            "",
        )
        or ""
    )


def _obtener_codigo_terminal(request):
    """
    Header recomendado:

        X-Terminal-Code: NORTE-01
    """

    return (
        request.headers.get(
            "X-Terminal-Code"
        )
        or request.POST.get(
            "terminal_codigo"
        )
        or ""
    ).strip().upper()


def _obtener_token_terminal(request):
    """
    Header recomendado:

        X-Terminal-Token: TOKEN_PRIVADO
    """

    return (
        request.headers.get(
            "X-Terminal-Token"
        )
        or request.POST.get(
            "terminal_token"
        )
        or ""
    ).strip()


# =========================================================
# ERRORES
# =========================================================

def _serializar_error_validacion(exc):

    if hasattr(
        exc,
        "message_dict",
    ):
        return exc.message_dict

    if hasattr(
        exc,
        "messages",
    ):
        return exc.messages

    return [
        str(exc)
    ]


def _respuesta_error(
    mensaje,
    status=400,
    detalles=None,
):

    contenido = {
        "ok": False,
        "error": mensaje,
    }

    if detalles is not None:
        contenido[
            "detalles"
        ] = detalles

    return JsonResponse(
        contenido,
        status=status,
    )


# =========================================================
# TIPO DE MARCACIÓN
# =========================================================

def _nombre_tipo_marcacion(
    tipo,
):

    if not tipo:
        return None

    return dict(
        RegistroAsistencia
        .TIPOS_MARCACION
    ).get(
        tipo,
        tipo,
    )


# =========================================================
# UUID
# =========================================================

def _normalizar_uuid_api(
    valor,
):
    """
    Convierte un UUID recibido como texto.

    Retorna None si viene vacío.
    """

    valor = str(
        valor or ""
    ).strip()

    if not valor:
        return None

    try:

        return UUID(
            valor
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
# FECHA/HORA OFFLINE
# =========================================================

def _parsear_fecha_hora_dispositivo(
    valor,
):
    """
    Recibe algo como:

        2026-09-21T07:51:23-05:00

    Se recomienda siempre enviar zona horaria.
    """

    valor = str(
        valor or ""
    ).strip()

    if not valor:
        raise ValidationError(
            "No se recibió la fecha y hora "
            "de la marcación offline."
        )

    momento = parse_datetime(
        valor
    )

    if momento is None:
        raise ValidationError(
            "La fecha y hora de la marcación "
            "offline no tiene un formato válido."
        )

    if timezone.is_naive(
        momento
    ):
        momento = timezone.make_aware(
            momento,
            timezone.get_current_timezone(),
        )

    return momento


# =========================================================
# FOTOGRAFÍA OPCIONAL
# =========================================================

def _preparar_fotografia_opcional(
    fotografia,
):
    """
    La fotografía nunca impide registrar asistencia.

    Retorna:

        fotografia válida, advertencia

    o:

        None, advertencia
    """

    if fotografia is None:
        return (
            None,
            None,
        )

    # =====================================================
    # ARCHIVO VACÍO
    # =====================================================

    if fotografia.size <= 0:

        return (
            None,
            (
                "La fotografía recibida estaba vacía. "
                "La asistencia se registró sin fotografía."
            ),
        )

    # =====================================================
    # TAMAÑO
    # =====================================================

    if (
        fotografia.size
        > MAX_FOTO_BYTES
    ):

        return (
            None,
            (
                "La fotografía superaba el límite "
                "de 5 MB. "
                "La asistencia se registró sin fotografía."
            ),
        )

    # =====================================================
    # TIPO
    # =====================================================

    content_type = (
        fotografia.content_type
        or ""
    ).lower()

    if (
        content_type
        not in TIPOS_IMAGEN_PERMITIDOS
    ):

        return (
            None,
            (
                "La fotografía no tenía un formato "
                "permitido. "
                "La asistencia se registró sin fotografía."
            ),
        )

    return (
        fotografia,
        None,
    )


# =========================================================
# USUARIO PARA SINCRONIZACIÓN OFFLINE
# =========================================================

def _obtener_usuario_offline(
    *,
    usuario_id=None,
    identificador=None,
):
    """
    Cuando una marcación se hizo SIN INTERNET,
    el PIN ya fue validado localmente por la terminal.

    Cuando vuelve Internet no almacenamos ni reenviamos
    el PIN en texto plano.

    Por eso la sincronización se autentica mediante:

        - token de terminal
        - usuario conocido
        - UUID de marcación

    Más adelante la aplicación mantendrá una caché local
    protegida de los trabajadores habilitados.
    """

    Usuario = get_user_model()

    usuario = None

    # =====================================================
    # PREFERIR ID
    # =====================================================

    if usuario_id not in {
        None,
        "",
    }:

        try:

            usuario_id = int(
                usuario_id
            )

        except (
            ValueError,
            TypeError,
        ) as exc:

            raise ValidationError(
                "El ID del trabajador "
                "no es válido."
            ) from exc

        usuario = (
            Usuario.objects
            .select_related(
                "sucursal"
            )
            .filter(
                pk=usuario_id,
            )
            .first()
        )

    # =====================================================
    # FALLBACK: USERNAME / CÉDULA
    # =====================================================

    if (
        usuario is None
        and identificador
    ):

        identificador = str(
            identificador
        ).strip()

        usuario = (
            Usuario.objects
            .select_related(
                "sucursal"
            )
            .filter(
                username__iexact=(
                    identificador
                )
            )
            .first()
        )

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

    if usuario is None:
        raise ValidationError(
            "No se encontró el trabajador "
            "de la marcación offline."
        )

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
            "El usuario no tiene "
            "asistencia configurada."
        )

    if not configuracion.puede_marcar:
        raise ValidationError(
            "El usuario no está habilitado "
            "para registrar asistencia."
        )

    return usuario


# =========================================================
# SERIALIZAR RESPUESTA
# =========================================================

def _respuesta_marcacion(
    *,
    registro,
    usuario,
    advertencias=None,
    reintento=False,
    sincronizada=False,
):

    advertencias = (
        advertencias
        if isinstance(
            advertencias,
            list,
        )
        else []
    )

    # =====================================================
    # HORA LOCAL
    # =====================================================

    fecha_hora_local = (
        timezone.localtime(
            registro.fecha_hora
        )
    )

    # =====================================================
    # RESUMEN DE JORNADA
    # =====================================================

    resumen = (
        obtener_resumen_jornada(
            usuario,
            registro.fecha,
        )
    )

    siguiente_tipo = (
        resumen[
            "siguiente_tipo"
        ]
    )

    # =====================================================
    # INCIDENCIAS
    # =====================================================

    incidencias = []

    for incidencia in (
        registro
        .incidencias
        .all()
        .order_by(
            "creado_en"
        )
    ):

        incidencias.append(
            {
                "id": (
                    incidencia.id
                ),

                "tipo": (
                    incidencia.tipo
                ),

                "descripcion": (
                    incidencia
                    .get_tipo_display()
                ),

                "minutos": (
                    incidencia.minutos
                ),

                "estado": (
                    incidencia.estado
                ),
            }
        )

    # =====================================================
    # FOTO
    # =====================================================

    fotografia_nombre = None

    if registro.fotografia:

        fotografia_nombre = (
            registro
            .fotografia
            .name
        )

    # =====================================================
    # FECHA/HORA DEL DISPOSITIVO
    # =====================================================

    fecha_hora_dispositivo = None

    if (
        registro
        .fecha_hora_dispositivo
    ):

        fecha_hora_dispositivo = (
            timezone.localtime(
                registro
                .fecha_hora_dispositivo
            )
            .isoformat()
        )

    # =====================================================
    # MENSAJE
    # =====================================================

    if reintento:

        mensaje = (
            "La marcación ya había sido "
            "registrada anteriormente."
        )

    elif sincronizada:

        mensaje = (
            f"{registro.get_tipo_display()} "
            f"offline sincronizada correctamente."
        )

    else:

        mensaje = (
            f"{registro.get_tipo_display()} "
            f"registrada correctamente."
        )

    # =====================================================
    # JSON
    # =====================================================

    return JsonResponse(
        {
            "ok": True,

            "mensaje": (
                mensaje
            ),

            "reintento": (
                reintento
            ),

            "sincronizada": (
                sincronizada
            ),

            # =============================================
            # USUARIO
            # =============================================

            "usuario": {
                "id": (
                    usuario.id
                ),

                "username": (
                    usuario.username
                ),

                "nombre": (
                    usuario.get_full_name()
                    or usuario.username
                ),

                "cedula": (
                    usuario.cedula
                ),
            },

            # =============================================
            # REGISTRO
            # =============================================

            "registro": {
                "id": (
                    registro.id
                ),

                "uuid_marcacion": (
                    str(
                        registro
                        .uuid_marcacion
                    )
                ),

                "tipo": (
                    registro.tipo
                ),

                "tipo_descripcion": (
                    registro
                    .get_tipo_display()
                ),

                "fecha": (
                    registro
                    .fecha
                    .isoformat()
                ),

                "hora": (
                    fecha_hora_local
                    .strftime(
                        "%H:%M:%S"
                    )
                ),

                "fecha_hora": (
                    fecha_hora_local
                    .isoformat()
                ),

                "es_offline": (
                    registro.es_offline
                ),

                "fecha_hora_dispositivo": (
                    fecha_hora_dispositivo
                ),

                # =========================================
                # SUCURSAL
                # =========================================

                "sucursal": {
                    "id": (
                        registro
                        .sucursal_id
                    ),

                    "codigo": (
                        registro
                        .sucursal
                        .codigo
                    ),

                    "nombre": (
                        registro
                        .sucursal
                        .nombre
                    ),
                },

                # =========================================
                # TERMINAL
                # =========================================

                "terminal": {
                    "id": (
                        registro
                        .terminal_id
                    ),

                    "codigo": (
                        registro
                        .terminal
                        .codigo
                    ),

                    "nombre": (
                        registro
                        .terminal
                        .nombre
                    ),
                },

                # =========================================
                # FOTO
                # =========================================

                "fotografia": (
                    fotografia_nombre
                ),

                "tiene_fotografia": (
                    bool(
                        registro.fotografia
                    )
                ),
            },

            # =============================================
            # JORNADA
            # =============================================

            "jornada": {
                "cantidad_marcaciones": (
                    resumen[
                        "cantidad_marcaciones"
                    ]
                ),

                "completa": (
                    resumen[
                        "jornada_completa"
                    ]
                ),

                "siguiente_tipo": (
                    siguiente_tipo
                ),

                "siguiente_descripcion": (
                    _nombre_tipo_marcacion(
                        siguiente_tipo
                    )
                ),

                "duracion_almuerzo_minutos": (
                    resumen[
                        "duracion_almuerzo_minutos"
                    ]
                ),

                "sucursales": (
                    resumen[
                        "sucursales"
                    ]
                ),
            },

            # =============================================
            # INCIDENCIAS
            # =============================================

            "incidencias": (
                incidencias
            ),

            # =============================================
            # ADVERTENCIAS
            # =============================================

            "advertencias": (
                advertencias
            ),
        },
        status=201,
    )


# =========================================================
# API ONLINE
# =========================================================

@csrf_exempt
@require_POST
def api_marcar_asistencia(
    request,
):
    """
    Marcación normal con Internet.

    La aplicación envía:

        identificador
        pin
        uuid_marcacion       opcional por compatibilidad
        fotografia           opcional

    Headers:

        X-Terminal-Code
        X-Terminal-Token

    El tipo de marcación NO se recibe.

    Django lo determina automáticamente.
    """

    try:

        # =================================================
        # DATOS
        # =================================================

        identificador = (
            request.POST.get(
                "identificador",
                ""
            )
            .strip()
        )

        pin = (
            request.POST.get(
                "pin",
                ""
            )
            .strip()
        )

        uuid_marcacion = (
            request.POST.get(
                "uuid_marcacion"
            )
        )

        codigo_terminal = (
            _obtener_codigo_terminal(
                request
            )
        )

        token_terminal = (
            _obtener_token_terminal(
                request
            )
        )

        fotografia_recibida = (
            request.FILES.get(
                "fotografia"
            )
        )

        # =================================================
        # VALIDACIONES
        # =================================================

        if not identificador:
            return _respuesta_error(
                "Debes ingresar tu usuario "
                "o cédula."
            )

        if not pin:
            return _respuesta_error(
                "Debes ingresar tu PIN "
                "de asistencia."
            )

        if not codigo_terminal:
            return _respuesta_error(
                "No se recibió el código "
                "de la terminal."
            )

        if not token_terminal:
            return _respuesta_error(
                "No se recibió la credencial "
                "de la terminal."
            )

        # =================================================
        # UUID OPCIONAL
        # =================================================

        uuid_marcacion = (
            _normalizar_uuid_api(
                uuid_marcacion
            )
        )

        # =================================================
        # TERMINAL
        # =================================================

        terminal = (
            autenticar_terminal(
                codigo_terminal,
                token_terminal,
            )
        )

        # =================================================
        # USUARIO + PIN
        # =================================================

        usuario = (
            autenticar_usuario_asistencia(
                identificador,
                pin,
            )
        )

        # =================================================
        # FOTO
        # =================================================

        (
            fotografia,
            advertencia_foto,
        ) = _preparar_fotografia_opcional(
            fotografia_recibida
        )

        advertencias = []

        if advertencia_foto:
            advertencias.append(
                advertencia_foto
            )

        # =================================================
        # ¿YA EXISTÍA EL UUID?
        # =================================================

        registro_previo = None

        if uuid_marcacion:

            registro_previo = (
                obtener_marcacion_por_uuid(
                    uuid_marcacion
                )
            )

        # =================================================
        # REGISTRAR
        # =================================================

        registro = (
            registrar_marcacion(
                usuario=usuario,
                terminal=terminal,

                uuid_marcacion=(
                    uuid_marcacion
                ),

                tipo_marcacion=None,

                ip=_obtener_ip(
                    request
                ),

                user_agent=(
                    _obtener_user_agent(
                        request
                    )
                ),

                es_offline=False,

                fecha_hora_dispositivo=None,
            )
        )

        # =================================================
        # FOTO DESPUÉS DE GUARDAR ASISTENCIA
        # =================================================

        if fotografia is not None:

            guardada = (
                adjuntar_fotografia_opcional(
                    registro,
                    fotografia,
                )
            )

            if not guardada:

                advertencias.append(
                    (
                        "La asistencia quedó registrada, "
                        "pero no fue posible guardar "
                        "la fotografía."
                    )
                )

        registro.refresh_from_db()

        # =================================================
        # RESPUESTA
        # =================================================

        return _respuesta_marcacion(
            registro=registro,
            usuario=usuario,
            advertencias=advertencias,
            reintento=(
                registro_previo
                is not None
            ),
            sincronizada=False,
        )

    except ValidationError as exc:

        return JsonResponse(
            {
                "ok": False,

                "error": (
                    "No se pudo registrar "
                    "la marcación."
                ),

                "detalles": (
                    _serializar_error_validacion(
                        exc
                    )
                ),
            },
            status=400,
        )

    except Exception:

        logger.exception(
            "Error inesperado en "
            "api_marcar_asistencia."
        )

        return JsonResponse(
            {
                "ok": False,

                "error": (
                    "Ocurrió un error interno "
                    "al registrar la asistencia."
                ),
            },
            status=500,
        )


# =========================================================
# API DE SINCRONIZACIÓN OFFLINE
# =========================================================

@csrf_exempt
@require_POST
def api_sincronizar_marcacion(
    request,
):
    """
    Recibe una marcación almacenada por la PC mientras
    no había Internet.

    Datos requeridos:

        uuid_marcacion
        tipo_marcacion
        fecha_hora_dispositivo

    Identidad:

        usuario_id
            preferido

        o

        identificador
            username / cédula

    Fotografía:

        opcional

    Headers:

        X-Terminal-Code
        X-Terminal-Token


    IMPORTANTE:

    Aquí NO recibimos el PIN original.

    El PIN habrá sido validado localmente cuando se creó
    la marcación offline.

    Nunca almacenaremos el PIN del trabajador en texto
    plano para reenviarlo posteriormente.
    """

    try:

        # =================================================
        # TERMINAL
        # =================================================

        codigo_terminal = (
            _obtener_codigo_terminal(
                request
            )
        )

        token_terminal = (
            _obtener_token_terminal(
                request
            )
        )

        if not codigo_terminal:
            return _respuesta_error(
                "No se recibió el código "
                "de la terminal."
            )

        if not token_terminal:
            return _respuesta_error(
                "No se recibió la credencial "
                "de la terminal."
            )

        terminal = (
            autenticar_terminal(
                codigo_terminal,
                token_terminal,
            )
        )

        # =================================================
        # DATOS OFFLINE
        # =================================================

        uuid_marcacion = (
            _normalizar_uuid_api(
                request.POST.get(
                    "uuid_marcacion"
                )
            )
        )

        if uuid_marcacion is None:
            raise ValidationError(
                "La sincronización offline "
                "requiere uuid_marcacion."
            )

        tipo_marcacion = (
            request.POST.get(
                "tipo_marcacion",
                "",
            )
            .strip()
            .upper()
        )

        if not tipo_marcacion:
            raise ValidationError(
                "La sincronización offline "
                "requiere tipo_marcacion."
            )

        fecha_hora_dispositivo = (
            _parsear_fecha_hora_dispositivo(
                request.POST.get(
                    "fecha_hora_dispositivo"
                )
            )
        )

        # =================================================
        # USUARIO
        # =================================================

        usuario = (
            _obtener_usuario_offline(
                usuario_id=(
                    request.POST.get(
                        "usuario_id"
                    )
                ),

                identificador=(
                    request.POST.get(
                        "identificador"
                    )
                ),
            )
        )

        # =================================================
        # FOTO OPCIONAL
        # =================================================

        fotografia_recibida = (
            request.FILES.get(
                "fotografia"
            )
        )

        (
            fotografia,
            advertencia_foto,
        ) = _preparar_fotografia_opcional(
            fotografia_recibida
        )

        advertencias = []

        if advertencia_foto:

            advertencias.append(
                advertencia_foto
            )

        # =================================================
        # ¿UUID YA EXISTE?
        # =================================================
        #
        # Este caso es muy importante:
        #
        # La PC pudo enviar una marcación online,
        # Django guardarla, pero perderse la respuesta.
        #
        # Luego la PC la reenvía desde la cola local.
        #
        # Si el mismo UUID ya está en Django no debemos
        # volver a crear nada.
        # =================================================

        existente = (
            obtener_marcacion_por_uuid(
                uuid_marcacion
            )
        )

        if existente is not None:

            # =============================================
            # UUID DE OTRO USUARIO
            # =============================================

            if (
                existente.usuario_id
                != usuario.id
            ):

                raise ValidationError(
                    "El UUID recibido ya pertenece "
                    "a otro trabajador."
                )

            # =============================================
            # UUID DE OTRA TERMINAL
            # =============================================

            if (
                existente.terminal_id
                != terminal.id
            ):

                raise ValidationError(
                    "El UUID recibido ya pertenece "
                    "a otra terminal."
                )

            # =============================================
            # SI EL REGISTRO ORIGINAL TAMBIÉN ERA OFFLINE,
            # VALIDAMOS SU CONTENIDO.
            # =============================================

            if existente.es_offline:

                if (
                    existente.tipo
                    != tipo_marcacion
                ):

                    raise ValidationError(
                        "El UUID ya existe con "
                        "otro tipo de marcación."
                    )

                if (
                    existente
                    .fecha_hora_dispositivo
                    is not None
                    and existente
                    .fecha_hora_dispositivo
                    != fecha_hora_dispositivo
                ):

                    raise ValidationError(
                        "El UUID ya existe con "
                        "otra fecha u hora."
                    )

            # =============================================
            # ADJUNTAR FOTO SI ANTES NO EXISTÍA
            # =============================================

            if fotografia is not None:

                guardada = (
                    adjuntar_fotografia_opcional(
                        existente,
                        fotografia,
                    )
                )

                if not guardada:

                    advertencias.append(
                        (
                            "La marcación ya existía, "
                            "pero no fue posible guardar "
                            "la fotografía."
                        )
                    )

            existente.refresh_from_db()

            return _respuesta_marcacion(
                registro=existente,
                usuario=usuario,
                advertencias=advertencias,
                reintento=True,
                sincronizada=True,
            )

        # =================================================
        # CREAR NUEVA MARCACIÓN OFFLINE
        # =================================================

        registro = (
            registrar_marcacion(
                usuario=usuario,
                terminal=terminal,

                uuid_marcacion=(
                    uuid_marcacion
                ),

                tipo_marcacion=(
                    tipo_marcacion
                ),

                ip=_obtener_ip(
                    request
                ),

                user_agent=(
                    _obtener_user_agent(
                        request
                    )
                ),

                es_offline=True,

                fecha_hora_dispositivo=(
                    fecha_hora_dispositivo
                ),
            )
        )

        # =================================================
        # FOTO OPCIONAL
        # =================================================

        if fotografia is not None:

            guardada = (
                adjuntar_fotografia_opcional(
                    registro,
                    fotografia,
                )
            )

            if not guardada:

                advertencias.append(
                    (
                        "La marcación offline fue "
                        "sincronizada, pero no fue posible "
                        "guardar la fotografía."
                    )
                )

        registro.refresh_from_db()

        # =================================================
        # RESPUESTA
        # =================================================

        return _respuesta_marcacion(
            registro=registro,
            usuario=usuario,
            advertencias=advertencias,
            reintento=False,
            sincronizada=True,
        )

    except ValidationError as exc:

        return JsonResponse(
            {
                "ok": False,

                "error": (
                    "No se pudo sincronizar "
                    "la marcación."
                ),

                "detalles": (
                    _serializar_error_validacion(
                        exc
                    )
                ),
            },
            status=400,
        )

    except Exception:

        logger.exception(
            "Error inesperado en "
            "api_sincronizar_marcacion."
        )

        return JsonResponse(
            {
                "ok": False,

                "error": (
                    "Ocurrió un error interno "
                    "al sincronizar la marcación."
                ),
            },
            status=500,
        )



# =========================================================
# API - CACHÉ DE TERMINAL
# =========================================================

@csrf_exempt
@require_POST
def api_cache_terminal(
    request,
):
    """
    Entrega a una terminal autorizada la información
    necesaria para poder funcionar temporalmente offline.

    Incluye:

    - trabajadores habilitados
    - hash del PIN
    - estado de la jornada actual
    - siguiente marcación esperada

    IMPORTANTE:

    En producción este endpoint debe utilizar
    exclusivamente HTTPS.
    """

    try:

        # =================================================
        # AUTENTICAR TERMINAL
        # =================================================

        codigo_terminal = (
            _obtener_codigo_terminal(
                request
            )
        )

        token_terminal = (
            _obtener_token_terminal(
                request
            )
        )

        if not codigo_terminal:
            return _respuesta_error(
                "No se recibió el código "
                "de la terminal."
            )

        if not token_terminal:
            return _respuesta_error(
                "No se recibió la credencial "
                "de la terminal."
            )

        terminal = (
            autenticar_terminal(
                codigo_terminal,
                token_terminal,
            )
        )

        # =================================================
        # FECHA/HORA DEL SERVIDOR
        # =================================================

        ahora_servidor = (
            timezone.localtime(
                timezone.now()
            )
        )

        fecha_actual = (
            ahora_servidor.date()
        )

        # =================================================
        # USUARIOS HABILITADOS
        # =================================================

        configuraciones = (
            ConfiguracionAsistenciaUsuario
            .objects
            .select_related(
                "usuario",
                "usuario__sucursal",
            )
            .filter(
                habilitado=True,
                usuario__is_active=True,
            )
            .exclude(
                pin_hash="",
            )
            .order_by(
                "usuario__username"
            )
        )

        usuarios = []

        for configuracion in configuraciones:

            usuario = (
                configuracion.usuario
            )

            # =============================================
            # ESTADO ACTUAL DE LA JORNADA
            # =============================================

            try:

                resumen = (
                    obtener_resumen_jornada(
                        usuario,
                        fecha_actual,
                    )
                )

                cantidad_marcaciones = (
                    resumen[
                        "cantidad_marcaciones"
                    ]
                )

                jornada_completa = (
                    resumen[
                        "jornada_completa"
                    ]
                )

                siguiente_tipo = (
                    resumen[
                        "siguiente_tipo"
                    ]
                )

                siguiente_descripcion = (
                    _nombre_tipo_marcacion(
                        siguiente_tipo
                    )
                )

                jornada_valida = True

                error_jornada = None

            except ValidationError as exc:

                # -----------------------------------------
                # No dejamos que un problema de un usuario
                # impida actualizar toda la terminal.
                # -----------------------------------------

                cantidad_marcaciones = 0

                jornada_completa = False

                siguiente_tipo = None

                siguiente_descripcion = None

                jornada_valida = False

                error_jornada = (
                    _serializar_error_validacion(
                        exc
                    )
                )

            # =============================================
            # SUCURSAL HABITUAL
            # =============================================

            sucursal_habitual = None

            if usuario.sucursal_id:

                sucursal_habitual = {
                    "id": (
                        usuario.sucursal_id
                    ),

                    "codigo": (
                        usuario
                        .sucursal
                        .codigo
                    ),

                    "nombre": (
                        usuario
                        .sucursal
                        .nombre
                    ),
                }

            # =============================================
            # USUARIO
            # =============================================

            usuarios.append(
                {
                    "usuario_id": (
                        usuario.id
                    ),

                    "username": (
                        usuario.username
                    ),

                    "cedula": (
                        usuario.cedula
                    ),

                    "nombre": (
                        usuario.get_full_name()
                        or usuario.username
                    ),

                    # =====================================
                    # SOLO HASH.
                    #
                    # NUNCA enviamos el PIN real.
                    # =====================================

                    "pin_hash": (
                        configuracion
                        .pin_hash
                    ),

                    "habilitado": (
                        configuracion
                        .habilitado
                    ),

                    "activo": (
                        usuario.is_active
                    ),

                    "sucursal_habitual": (
                        sucursal_habitual
                    ),

                    # =====================================
                    # JORNADA
                    # =====================================

                    "jornada": {
                        "fecha": (
                            fecha_actual
                            .isoformat()
                        ),

                        "cantidad_marcaciones": (
                            cantidad_marcaciones
                        ),

                        "completa": (
                            jornada_completa
                        ),

                        "siguiente_tipo": (
                            siguiente_tipo
                        ),

                        "siguiente_descripcion": (
                            siguiente_descripcion
                        ),

                        "valida": (
                            jornada_valida
                        ),

                        "error": (
                            error_jornada
                        ),
                    },
                }
            )

        # =================================================
        # REGISTRAR CONEXIÓN DE TERMINAL
        # =================================================

        terminal.registrar_conexion(
            ip=_obtener_ip(
                request
            )
        )

        # =================================================
        # RESPUESTA
        # =================================================

        return JsonResponse(
            {
                "ok": True,

                "servidor": {
                    "fecha": (
                        fecha_actual
                        .isoformat()
                    ),

                    "fecha_hora": (
                        ahora_servidor
                        .isoformat()
                    ),
                },

                "terminal": {
                    "id": (
                        terminal.id
                    ),

                    "codigo": (
                        terminal.codigo
                    ),

                    "nombre": (
                        terminal.nombre
                    ),

                    "sucursal": {
                        "id": (
                            terminal
                            .sucursal_id
                        ),

                        "codigo": (
                            terminal
                            .sucursal
                            .codigo
                        ),

                        "nombre": (
                            terminal
                            .sucursal
                            .nombre
                        ),
                    },
                },

                "usuarios": (
                    usuarios
                ),

                "cantidad_usuarios": (
                    len(
                        usuarios
                    )
                ),
            },
            status=200,
        )

    except ValidationError as exc:

        return JsonResponse(
            {
                "ok": False,

                "error": (
                    "No fue posible actualizar "
                    "la caché de la terminal."
                ),

                "detalles": (
                    _serializar_error_validacion(
                        exc
                    )
                ),
            },
            status=400,
        )

    except Exception:

        logger.exception(
            "Error inesperado en "
            "api_cache_terminal."
        )

        return JsonResponse(
            {
                "ok": False,

                "error": (
                    "Ocurrió un error interno "
                    "al actualizar la terminal."
                ),
            },
            status=500,
        )