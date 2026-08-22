from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import CodigoAccesoAsistente


class CodigoSSOInvalido(Exception):
    """
    Se lanza cuando un código SSO no existe, expiró,
    ya fue utilizado o no puede ser aceptado.
    """
    pass


# =========================================================
# GENERAR CÓDIGO SSO
# =========================================================

def generar_codigo_sso(usuario, sucursal=None):
    """
    Genera un código criptográficamente seguro de un solo uso.

    El código original se devuelve únicamente al navegador.
    En la base de datos se guarda solo su SHA-256.

    También se conserva la sucursal operativa seleccionada
    al momento de generar el acceso.

    Esto permite que usuarios que pueden cambiar de sucursal
    (por ejemplo, administradores) ingresen al Asistente con
    la sucursal que tienen activa en su sesión ERP.
    """

    if not usuario or not usuario.pk:
        raise ValueError(
            "Se requiere un usuario persistido."
        )

    if not usuario.is_active:
        raise ValueError(
            "No se puede generar acceso para un usuario inactivo."
        )

    ttl_segundos = getattr(
        settings,
        "ASISTENTE_SSO_TTL_SECONDS",
        60,
    )

    codigo = CodigoAccesoAsistente.generar_codigo()

    codigo_hash = CodigoAccesoAsistente.calcular_hash(
        codigo
    )

    registro = CodigoAccesoAsistente.objects.create(
        usuario=usuario,
        sucursal=sucursal,
        codigo_hash=codigo_hash,
        expira_en=(
            timezone.now()
            + timedelta(seconds=ttl_segundos)
        ),
    )

    return codigo, registro


# =========================================================
# CANJEAR CÓDIGO SSO
# =========================================================

def canjear_codigo_sso(codigo):
    """
    Valida y consume un código SSO.

    La fila se bloquea durante el canje para impedir que
    dos solicitudes concurrentes puedan utilizar el mismo código.

    Si el usuario fue desactivado después de generar el código,
    el código se consume igualmente antes de rechazar el acceso.

    La sucursal utilizada es la que quedó registrada cuando
    se generó el código SSO.
    """

    if not codigo:
        raise CodigoSSOInvalido(
            "Código inválido."
        )

    codigo_hash = CodigoAccesoAsistente.calcular_hash(
        codigo
    )

    usuario_inactivo = False
    identidad = None

    with transaction.atomic():

        try:
            registro = (
                CodigoAccesoAsistente.objects
                .select_for_update()
                .select_related(
                    "usuario",
                )
                .get(
                    codigo_hash=codigo_hash
                )
            )

        except CodigoAccesoAsistente.DoesNotExist:
            raise CodigoSSOInvalido(
                "Código inválido."
            )

        ahora = timezone.now()

        # =====================================================
        # CÓDIGO YA UTILIZADO
        # =====================================================

        if registro.usado_en is not None:
            raise CodigoSSOInvalido(
                "Código ya utilizado."
            )

        # =====================================================
        # CÓDIGO EXPIRADO
        # =====================================================

        if ahora >= registro.expira_en:
            raise CodigoSSOInvalido(
                "Código expirado."
            )

        usuario = registro.usuario

        # =====================================================
        # USUARIO ERP INACTIVO
        # =====================================================

        if not usuario.is_active:

            # El código debe quedar consumido incluso aunque
            # posteriormente rechacemos el acceso.

            registro.usado_en = ahora

            registro.save(
                update_fields=[
                    "usado_en",
                ]
            )

            usuario_inactivo = True

        else:

            # =================================================
            # CONSUMIR CÓDIGO
            # =================================================

            registro.usado_en = ahora

            registro.save(
                update_fields=[
                    "usado_en",
                ]
            )

            # =================================================
            # SUCURSAL ERP
            # =================================================

            # La sucursal principal es la que estaba activa
            # cuando se generó este código SSO.
            sucursal = registro.sucursal

            # Compatibilidad con códigos antiguos generados
            # antes de que CodigoAccesoAsistente almacenara
            # explícitamente una sucursal.
            if sucursal is None:
                sucursal = usuario.sucursal

            # =================================================
            # IDENTIDAD ERP
            # =================================================

            sucursal_data = None

            if sucursal:
                sucursal_data = {
                    "erp_sucursal_id": sucursal.pk,
                    "codigo": sucursal.codigo,
                    "nombre": sucursal.nombre,
                    "activa": sucursal.activa,
                }

            identidad = {
                "erp_user_id": usuario.pk,
                "username": usuario.get_username(),
                "first_name": usuario.first_name or "",
                "last_name": usuario.last_name or "",
                "activo": usuario.is_active,
                "sucursal": sucursal_data,
            }

    # Esta excepción se produce DESPUÉS de que la transacción
    # haya hecho commit, por lo que usado_en permanece guardado.
    if usuario_inactivo:
        raise CodigoSSOInvalido(
            "Usuario inactivo."
        )

    return identidad