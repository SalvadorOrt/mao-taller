# integraciones/mao_asistente/client.py

import logging

import requests

from django.conf import settings


logger = logging.getLogger(__name__)


# ==========================================================
# EXCEPCIONES
# ==========================================================

class MAOAsistenteException(Exception):
    """
    Excepción base de integración ERP -> MAO Asistente.
    """

    pass


class MAOAsistenteNoConfigurado(
    MAOAsistenteException
):
    """
    La integración con MAO Asistente no está configurada.
    """

    pass


class MAOAsistenteNoDisponible(
    MAOAsistenteException
):
    """
    MAO Asistente no respondió correctamente.
    """

    pass


class MAOAsistenteSolicitudInvalida(
    MAOAsistenteException
):
    """
    MAO Asistente rechazó los datos enviados.
    """

    pass


class MAOAsistenteNoAutorizado(
    MAOAsistenteException
):
    """
    MAO Asistente rechazó la autenticación
    servidor-a-servidor.
    """

    pass


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

def _obtener_configuracion():
    """
    Obtiene la configuración necesaria para comunicarse
    desde el ERP con MAO Asistente.
    """

    base_url = (
        getattr(
            settings,
            "MAO_ASISTENTE_BASE_URL",
            "",
        )
        or ""
    ).strip().rstrip("/")

    token = (
        getattr(
            settings,
            "MAO_ASISTENTE_SERVICE_TOKEN",
            "",
        )
        or ""
    ).strip()

    timeout = getattr(
        settings,
        "MAO_ASISTENTE_TIMEOUT_SECONDS",
        30,
    )

    if not base_url:
        raise MAOAsistenteNoConfigurado(
            "MAO_ASISTENTE_BASE_URL no está configurado."
        )

    if not token:
        raise MAOAsistenteNoConfigurado(
            "MAO_ASISTENTE_SERVICE_TOKEN "
            "no está configurado."
        )

    if (
        not settings.DEBUG
        and not base_url.startswith("https://")
    ):
        raise MAOAsistenteNoConfigurado(
            "La conexión con MAO Asistente "
            "debe utilizar HTTPS."
        )

    try:
        timeout = float(timeout)

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise MAOAsistenteNoConfigurado(
            "MAO_ASISTENTE_TIMEOUT_SECONDS "
            "no contiene un valor válido."
        ) from exc

    if timeout <= 0:
        raise MAOAsistenteNoConfigurado(
            "MAO_ASISTENTE_TIMEOUT_SECONDS "
            "debe ser mayor que cero."
        )

    return (
        base_url,
        token,
        timeout,
    )


# ==========================================================
# ENVIAR FICHA TÉCNICA POR WHATSAPP
# ==========================================================

def enviar_ficha_whatsapp_asistente(
    *,
    telefono,
    numero_orden,
    pdf_bytes,
    nombre_archivo,
    sucursal="",
    usuario_erp="",
    caption="",
):
    """
    Envía desde el ERP hacia MAO Asistente una ficha
    técnica en PDF.

    telefono:
        Número destinatario obtenido desde la OT.

    pdf_bytes:
        PDF de la ficha técnica FRONTAL.

    MAO Asistente se encarga de comunicarse posteriormente
    con Meta WhatsApp Cloud API.
    """

    # ======================================================
    # VALIDACIONES LOCALES
    # ======================================================

    telefono = str(
        telefono
        or ""
    ).strip()

    numero_orden = str(
        numero_orden
        or ""
    ).strip()

    nombre_archivo = str(
        nombre_archivo
        or ""
    ).strip()

    sucursal = str(
        sucursal
        or ""
    ).strip()

    usuario_erp = str(
        usuario_erp
        or ""
    ).strip()

    caption = str(
        caption
        or ""
    ).strip()

    if not telefono:
        raise MAOAsistenteSolicitudInvalida(
            "La orden no tiene un teléfono para WhatsApp."
        )

    if not numero_orden:
        raise MAOAsistenteSolicitudInvalida(
            "La orden no tiene número de orden."
        )

    if not pdf_bytes:
        raise MAOAsistenteSolicitudInvalida(
            "No se generó el PDF de la ficha técnica."
        )

    if not isinstance(
        pdf_bytes,
        (
            bytes,
            bytearray,
        ),
    ):
        raise MAOAsistenteSolicitudInvalida(
            "El contenido de la ficha técnica "
            "no es un PDF binario válido."
        )

    pdf_bytes = bytes(
        pdf_bytes
    )

    if not pdf_bytes.startswith(
        b"%PDF"
    ):
        raise MAOAsistenteSolicitudInvalida(
            "El documento generado no contiene "
            "una estructura PDF válida."
        )

    if not nombre_archivo:
        nombre_archivo = (
            f"{numero_orden}_FICHA-TECNICA.pdf"
        )

    if not nombre_archivo.lower().endswith(
        ".pdf"
    ):
        nombre_archivo += ".pdf"

    # ======================================================
    # CONFIGURACIÓN
    # ======================================================

    (
        base_url,
        token,
        timeout,
    ) = _obtener_configuracion()

    # ======================================================
    # ENDPOINT DEL ASISTENTE
    # ======================================================

    url = (
        f"{base_url}"
        "/integraciones/mao-erp/"
        "whatsapp/documento/"
    )

    # ======================================================
    # HEADERS
    # ======================================================

    headers = {
        "Authorization":
            f"Bearer {token}",

        "Accept":
            "application/json",
    }

    # ======================================================
    # DATOS
    # ======================================================

    data = {
        "telefono":
            telefono,

        "numero_orden":
            numero_orden,

        "sucursal":
            sucursal,

        "usuario_erp":
            usuario_erp,
    }

    if caption:
        data[
            "caption"
        ] = caption

    # ======================================================
    # PDF
    # ======================================================

    files = {
        "archivo": (
            nombre_archivo,
            pdf_bytes,
            "application/pdf",
        ),
    }

    # ======================================================
    # REQUEST
    # ======================================================

    try:
        response = requests.post(
            url,
            headers=headers,
            data=data,
            files=files,
            timeout=(
                5.0,
                timeout,
            ),
        )

    except requests.Timeout as exc:

        logger.warning(
            "Timeout enviando ficha %s "
            "a MAO Asistente.",
            numero_orden,
        )

        raise MAOAsistenteNoDisponible(
            "MAO Asistente tardó demasiado "
            "en responder."
        ) from exc

    except requests.RequestException as exc:

        logger.warning(
            "Error de red comunicándose con "
            "MAO Asistente para OT %s.",
            numero_orden,
        )

        raise MAOAsistenteNoDisponible(
            "No fue posible comunicarse "
            "con MAO Asistente."
        ) from exc

    # ======================================================
    # RESPUESTA JSON
    # ======================================================

    try:
        resultado = response.json()

    except ValueError as exc:

        logger.error(
            "MAO Asistente devolvió una respuesta "
            "no JSON para OT %s. HTTP=%s",
            numero_orden,
            response.status_code,
        )

        raise MAOAsistenteNoDisponible(
            "MAO Asistente devolvió "
            "una respuesta inválida."
        ) from exc

    # ======================================================
    # AUTENTICACIÓN RECHAZADA
    # ======================================================

    if response.status_code in (
        401,
        403,
    ):

        logger.error(
            "MAO Asistente rechazó la autenticación "
            "servidor-a-servidor."
        )

        raise MAOAsistenteNoAutorizado(
            "MAO Asistente rechazó "
            "la autenticación del ERP."
        )

    # ======================================================
    # SOLICITUD INVÁLIDA
    # ======================================================

    if response.status_code in (
        400,
        413,
    ):

        mensaje = (
            resultado.get(
                "error"
            )
            or
            "MAO Asistente rechazó "
            "la ficha técnica."
        )

        raise MAOAsistenteSolicitudInvalida(
            mensaje
        )

    # ======================================================
    # OTROS ERRORES
    # ======================================================

    if not response.ok:

        logger.error(
            "MAO Asistente devolvió HTTP %s "
            "al enviar ficha de OT %s.",
            response.status_code,
            numero_orden,
        )

        raise MAOAsistenteNoDisponible(
            resultado.get(
                "error"
            )
            or
            "MAO Asistente no pudo "
            "procesar el envío."
        )

    # ======================================================
    # VALIDAR CONTRATO
    # ======================================================

    if resultado.get(
        "ok"
    ) is not True:

        raise MAOAsistenteNoDisponible(
            resultado.get(
                "error"
            )
            or
            "MAO Asistente no confirmó el envío."
        )

    # ======================================================
    # ÉXITO
    # ======================================================

    logger.info(
        "MAO Asistente aceptó ficha técnica. "
        "OT=%s wamid=%s media_id=%s",
        numero_orden,
        resultado.get(
            "wamid"
        ),
        resultado.get(
            "media_id"
        ),
    )

    return resultado