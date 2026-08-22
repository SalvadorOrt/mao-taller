# ordenes_de_trabajo/views/whatsapp.py

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from integraciones.mao_asistente.client import (
    MAOAsistenteNoAutorizado,
    MAOAsistenteNoConfigurado,
    MAOAsistenteNoDisponible,
    MAOAsistenteSolicitudInvalida,
    enviar_ficha_whatsapp_asistente,
)

from ..models import OrdenTrabajo
from ..services.pdf_ficha import generar_pdf_desde_html

from .impresion import (
    obtener_contexto_ficha_tecnica,
)


logger = logging.getLogger(__name__)


# ==========================================================
# UTILIDADES
# ==========================================================

def _obtener_telefono_cliente(orden):
    """
    Obtiene el teléfono principal directamente desde
    el cliente asociado a la Orden de Trabajo.

    IMPORTANTE:

    El teléfono NO viene del navegador.
    El teléfono NO viene de MAO Asistente.

    Siempre se vuelve a consultar desde la OT en el ERP:

        orden.cliente.telefono
    """

    cliente = getattr(
        orden,
        "cliente",
        None,
    )

    if not cliente:
        return ""

    telefono = getattr(
        cliente,
        "telefono",
        "",
    )

    return str(
        telefono
        or ""
    ).strip()


def _obtener_nombre_sucursal(orden):
    """
    Obtiene una representación segura de la sucursal
    responsable de la orden.

    Este valor se envía únicamente como contexto/auditoría
    hacia MAO Asistente.
    """

    sucursal = getattr(
        orden,
        "sucursal",
        None,
    )

    if not sucursal:
        return ""

    return str(
        sucursal
    ).strip()


def _obtener_usuario_erp(request):
    """
    Obtiene el usuario autenticado que ejecutó manualmente
    la acción de envío.
    """

    usuario = getattr(
        request,
        "user",
        None,
    )

    if not usuario:
        return ""

    username = getattr(
        usuario,
        "username",
        "",
    )

    return str(
        username
        or ""
    ).strip()


# ==========================================================
# ENVIAR FICHA TÉCNICA POR WHATSAPP
# ==========================================================

@login_required
@require_POST
def enviar_ficha_whatsapp(
    request,
    pk,
):
    """
    Envía manualmente por WhatsApp la ficha técnica
    FRONTAL de una Orden de Trabajo.

    Flujo:

        1. Buscar OT.
        2. Obtener teléfono desde orden.cliente.telefono.
        3. Renderizar imprimir_tecnico.html.
        4. Forzar incluir_trasera=False.
        5. Forzar modo_pdf=True.
        6. Generar PDF.
        7. Enviar PDF al MAO Asistente.
        8. MAO Asistente realiza el envío mediante Meta.

    Esta vista NO contiene credenciales de Meta.
    """

    # ======================================================
    # 1. OBTENER ORDEN
    # ======================================================

    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "cliente",
            "sucursal",
            "sucursal__empresa",
            "expediente",
        ),
        pk=pk,
    )

    # ======================================================
    # 2. TELÉFONO DEL CLIENTE
    # ======================================================
    #
    # IMPORTANTE:
    #
    # No aceptamos un teléfono enviado desde JavaScript.
    #
    # Siempre obtenemos nuevamente el teléfono desde
    # la base de datos del ERP.
    #
    # ======================================================

    telefono = _obtener_telefono_cliente(
        orden
    )

    if not telefono:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El cliente de esta orden no tiene "
                    "un teléfono principal registrado."
                ),
            },
            status=400,
        )

    # ======================================================
    # 3. NÚMERO DE ORDEN
    # ======================================================

    numero_orden = str(
        orden.numero_orden
        or ""
    ).strip()

    if not numero_orden:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La orden no tiene un número "
                    "de orden válido."
                ),
            },
            status=400,
        )

    # ======================================================
    # 4. CONTEXTO DE FICHA TÉCNICA
    # ======================================================
    #
    # REGLA DEL ENVÍO POR WHATSAPP:
    #
    # incluir_trasera=False
    #
    # Esto garantiza que:
    #
    # imprimir_tecnico_trasera.html
    #
    # NO participe en este PDF.
    #
    # modo_pdf=True evita que el HTML ejecute:
    #
    # window.print()
    #
    # ======================================================

    contexto = obtener_contexto_ficha_tecnica(
        orden,
        incluir_trasera=False,
        modo_pdf=True,
    )

    # ======================================================
    # 5. RENDERIZAR HTML
    # ======================================================

    try:
        html = render_to_string(
            "impresion/imprimir_tecnico.html",
            contexto,
            request=request,
        )

    except Exception:
        logger.exception(
            "Error renderizando la ficha técnica "
            "para WhatsApp. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible preparar "
                    "la ficha técnica."
                ),
            },
            status=500,
        )

    # ======================================================
    # 6. URL BASE
    # ======================================================
    #
    # Chromium necesita una URL base para resolver:
    #
    # /static/
    # /media/
    #
    # ======================================================

    base_url = (
        request.build_absolute_uri("/")
    )

    # ======================================================
    # 7. GENERAR PDF
    # ======================================================

    try:
        pdf_bytes = generar_pdf_desde_html(
            html=html,
            base_url=base_url,
        )

    except Exception:
        logger.exception(
            "Error generando PDF frontal "
            "para WhatsApp. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible generar "
                    "el PDF de la ficha técnica."
                ),
            },
            status=500,
        )

    # ======================================================
    # 8. VALIDAR PDF GENERADO
    # ======================================================

    if not pdf_bytes:
        logger.error(
            "La generación de PDF devolvió contenido vacío. "
            "OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La ficha técnica se generó vacía."
                ),
            },
            status=500,
        )

    if not pdf_bytes.startswith(
        b"%PDF"
    ):
        logger.error(
            "El archivo generado no tiene firma PDF. "
            "OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El documento generado no es "
                    "un PDF válido."
                ),
            },
            status=500,
        )

    # ======================================================
    # 9. NOMBRE DEL ARCHIVO
    # ======================================================

    nombre_archivo = str(
        contexto.get(
            "nombre_archivo",
            "",
        )
        or ""
    ).strip()

    if not nombre_archivo:
        nombre_archivo = (
            f"{numero_orden}_FICHA-TECNICA"
        )

    if not nombre_archivo.lower().endswith(
        ".pdf"
    ):
        nombre_archivo += ".pdf"

    # ======================================================
    # 10. SUCURSAL / USUARIO
    # ======================================================

    sucursal = _obtener_nombre_sucursal(
        orden
    )

    usuario_erp = _obtener_usuario_erp(
        request
    )

    # ======================================================
    # 11. TEXTO DEL DOCUMENTO
    # ======================================================

    caption = (
        f"Ficha técnica {numero_orden}"
    )

    # ======================================================
    # 12. ERP -> MAO ASISTENTE
    # ======================================================

    try:
        resultado = (
            enviar_ficha_whatsapp_asistente(
                telefono=telefono,
                numero_orden=numero_orden,
                pdf_bytes=pdf_bytes,
                nombre_archivo=nombre_archivo,
                sucursal=sucursal,
                usuario_erp=usuario_erp,
                caption=caption,
            )
        )

    # ======================================================
    # CONFIGURACIÓN FALTANTE
    # ======================================================

    except MAOAsistenteNoConfigurado as exc:

        logger.error(
            "Integración con MAO Asistente "
            "no configurada. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La integración con MAO Asistente "
                    "no está configurada."
                ),
            },
            status=503,
        )

    # ======================================================
    # TOKEN INCORRECTO
    # ======================================================

    except MAOAsistenteNoAutorizado as exc:

        logger.error(
            "MAO Asistente rechazó la autenticación "
            "del ERP. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "MAO Asistente rechazó "
                    "la autenticación del ERP."
                ),
            },
            status=502,
        )

    # ======================================================
    # SOLICITUD INVÁLIDA
    # ======================================================

    except MAOAsistenteSolicitudInvalida as exc:

        logger.warning(
            "MAO Asistente rechazó los datos "
            "de la ficha. OT=%s Error=%s",
            numero_orden,
            exc,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status=400,
        )

    # ======================================================
    # ASISTENTE NO DISPONIBLE
    # ======================================================

    except MAOAsistenteNoDisponible as exc:

        logger.error(
            "MAO Asistente no disponible "
            "durante envío. OT=%s Error=%s",
            numero_orden,
            exc,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible comunicarse "
                    "con MAO Asistente."
                ),
            },
            status=503,
        )

    # ======================================================
    # ERROR NO CONTROLADO
    # ======================================================

    except Exception:

        logger.exception(
            "Error inesperado enviando ficha "
            "por WhatsApp. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ocurrió un error inesperado "
                    "durante el envío."
                ),
            },
            status=500,
        )

    # ======================================================
    # 13. VALIDAR RESPUESTA
    # ======================================================

    if resultado.get(
        "ok"
    ) is not True:

        logger.error(
            "Respuesta inesperada de MAO Asistente. "
            "OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "MAO Asistente no confirmó "
                    "el envío del documento."
                ),
            },
            status=502,
        )

    # ======================================================
    # 14. IDENTIFICADORES META
    # ======================================================

    wamid = resultado.get(
        "wamid"
    )

    media_id = resultado.get(
        "media_id"
    )

    # ======================================================
    # 15. LOG
    # ======================================================
    #
    # No registramos el teléfono del cliente.
    #
    # ======================================================

    logger.info(
        "Ficha técnica enviada a MAO Asistente. "
        "OT=%s Usuario=%s Sucursal=%s "
        "wamid=%s media_id=%s",
        numero_orden,
        usuario_erp or "-",
        sucursal or "-",
        wamid or "-",
        media_id or "-",
    )

    # ======================================================
    # 16. RESPUESTA AL NAVEGADOR
    # ======================================================

    return JsonResponse(
        {
            "ok": True,

            "mensaje": (
                "La ficha técnica fue enviada "
                "por WhatsApp."
            ),

            "numero_orden":
                numero_orden,

            "wamid":
                wamid,
        },
        status=200,
    )# ordenes_de_trabajo/views/whatsapp.py

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from integraciones.mao_asistente.client import (
    MAOAsistenteNoAutorizado,
    MAOAsistenteNoConfigurado,
    MAOAsistenteNoDisponible,
    MAOAsistenteSolicitudInvalida,
    enviar_ficha_whatsapp_asistente,
)

from ..models import OrdenTrabajo
from ..services.pdf_ficha import generar_pdf_desde_html

from .impresion import (
    obtener_contexto_ficha_tecnica,
)


logger = logging.getLogger(__name__)


# ==========================================================
# OPCIONES IMPLEMENTADAS ACTUALMENTE
# ==========================================================

DOCUMENTO_FICHA_TECNICA = "FICHA_TECNICA"
MEDIO_WHATSAPP = "WHATSAPP"


# ==========================================================
# UTILIDADES
# ==========================================================

def _obtener_telefono_cliente(orden):
    """
    Obtiene el teléfono principal directamente desde
    el cliente asociado a la Orden de Trabajo.

    IMPORTANTE:

    El teléfono NO viene del navegador.
    El teléfono NO viene de MAO Asistente.

    Siempre se vuelve a consultar desde la OT en el ERP:

        orden.cliente.telefono
    """

    cliente = getattr(
        orden,
        "cliente",
        None,
    )

    if not cliente:
        return ""

    telefono = getattr(
        cliente,
        "telefono",
        "",
    )

    return str(
        telefono
        or ""
    ).strip()


def _obtener_nombre_sucursal(orden):
    """
    Obtiene una representación segura de la sucursal
    responsable de la orden.

    Este valor se envía únicamente como contexto/auditoría
    hacia MAO Asistente.
    """

    sucursal = getattr(
        orden,
        "sucursal",
        None,
    )

    if not sucursal:
        return ""

    return str(
        sucursal
    ).strip()


def _obtener_usuario_erp(request):
    """
    Obtiene el usuario autenticado que ejecutó manualmente
    la acción de envío.
    """

    usuario = getattr(
        request,
        "user",
        None,
    )

    if not usuario:
        return ""

    username = getattr(
        usuario,
        "username",
        "",
    )

    return str(
        username
        or ""
    ).strip()


def _obtener_valor_post(
    request,
    nombre,
):
    """
    Obtiene y normaliza un valor enviado por POST.

    Se utiliza únicamente para seleccionar la operación.

    No se utiliza para determinar teléfonos, correos
    ni otros datos sensibles del destinatario.
    """

    valor = request.POST.get(
        nombre,
        "",
    )

    return str(
        valor
        or ""
    ).strip().upper()


def _validar_tipo_envio(
    documento,
    medio,
):
    """
    Valida las combinaciones soportadas actualmente.

    Hoy solo está implementado:

        FICHA_TECNICA + WHATSAPP

    Esta validación permite que el modal sea genérico
    sin que el backend acepte opciones todavía no
    implementadas.
    """

    if not documento:
        return (
            False,
            "Debe seleccionar un documento para enviar.",
        )

    if not medio:
        return (
            False,
            "Debe seleccionar un medio de envío.",
        )

    if documento != DOCUMENTO_FICHA_TECNICA:
        return (
            False,
            "El documento seleccionado todavía no está disponible para envío.",
        )

    if medio != MEDIO_WHATSAPP:
        return (
            False,
            "El medio de envío seleccionado todavía no está disponible.",
        )

    return (
        True,
        "",
    )


# ==========================================================
# ENVIAR FICHA TÉCNICA POR WHATSAPP
# ==========================================================

@login_required
@require_POST
def enviar_ficha_whatsapp(
    request,
    pk,
):
    """
    Envía manualmente por WhatsApp la ficha técnica
    FRONTAL de una Orden de Trabajo.

    Flujo:

        1. Validar documento y medio solicitados.
        2. Buscar OT.
        3. Obtener teléfono desde orden.cliente.telefono.
        4. Renderizar imprimir_tecnico.html.
        5. Forzar incluir_trasera=False.
        6. Forzar modo_pdf=True.
        7. Generar PDF.
        8. Enviar PDF al MAO Asistente.
        9. MAO Asistente realiza el envío mediante Meta.

    Esta vista NO contiene credenciales de Meta.
    """

    # ======================================================
    # 1. OPCIONES SOLICITADAS DESDE EL MODAL
    # ======================================================
    #
    # El navegador puede indicar QUÉ quiere hacer:
    #
    # documento = FICHA_TECNICA
    # medio     = WHATSAPP
    #
    # Pero nunca puede decidir el destinatario real.
    #
    # ======================================================

    documento = _obtener_valor_post(
        request,
        "documento",
    )

    medio = _obtener_valor_post(
        request,
        "medio",
    )


    # ======================================================
    # 2. VALIDAR COMBINACIÓN
    # ======================================================

    envio_valido, error_envio = (
        _validar_tipo_envio(
            documento=documento,
            medio=medio,
        )
    )

    if not envio_valido:
        return JsonResponse(
            {
                "ok": False,
                "error": error_envio,
            },
            status=400,
        )


    # ======================================================
    # 3. OBTENER ORDEN
    # ======================================================

    orden = get_object_or_404(
        OrdenTrabajo.objects.select_related(
            "cliente",
            "sucursal",
            "sucursal__empresa",
            "expediente",
        ),
        pk=pk,
    )


    # ======================================================
    # 4. TELÉFONO DEL CLIENTE
    # ======================================================
    #
    # IMPORTANTE:
    #
    # No aceptamos un teléfono enviado desde JavaScript.
    #
    # Siempre obtenemos nuevamente el teléfono desde
    # la base de datos del ERP.
    #
    # ======================================================

    telefono = _obtener_telefono_cliente(
        orden
    )

    if not telefono:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El cliente de esta orden no tiene "
                    "un teléfono principal registrado."
                ),
            },
            status=400,
        )


    # ======================================================
    # 5. NÚMERO DE ORDEN
    # ======================================================

    numero_orden = str(
        orden.numero_orden
        or ""
    ).strip()

    if not numero_orden:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La orden no tiene un número "
                    "de orden válido."
                ),
            },
            status=400,
        )


    # ======================================================
    # 6. CONTEXTO DE FICHA TÉCNICA
    # ======================================================
    #
    # REGLA DEL ENVÍO POR WHATSAPP:
    #
    # incluir_trasera=False
    #
    # Esto garantiza que:
    #
    # imprimir_tecnico_trasera.html
    #
    # NO participe en este PDF.
    #
    # modo_pdf=True evita que el HTML ejecute:
    #
    # window.print()
    #
    # ======================================================

    contexto = obtener_contexto_ficha_tecnica(
        orden,
        incluir_trasera=False,
        modo_pdf=True,
    )


    # ======================================================
    # 7. RENDERIZAR HTML
    # ======================================================

    try:
        html = render_to_string(
            "impresion/imprimir_tecnico.html",
            contexto,
            request=request,
        )

    except Exception:
        logger.exception(
            "Error renderizando la ficha técnica "
            "para WhatsApp. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible preparar "
                    "la ficha técnica."
                ),
            },
            status=500,
        )


    # ======================================================
    # 8. URL BASE
    # ======================================================
    #
    # Chromium necesita una URL base para resolver:
    #
    # /static/
    # /media/
    #
    # ======================================================

    base_url = (
        request.build_absolute_uri("/")
    )


    # ======================================================
    # 9. GENERAR PDF
    # ======================================================

    try:
        pdf_bytes = generar_pdf_desde_html(
            html=html,
            base_url=base_url,
        )

    except Exception:
        logger.exception(
            "Error generando PDF frontal "
            "para WhatsApp. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible generar "
                    "el PDF de la ficha técnica."
                ),
            },
            status=500,
        )


    # ======================================================
    # 10. VALIDAR PDF GENERADO
    # ======================================================

    if not pdf_bytes:
        logger.error(
            "La generación de PDF devolvió contenido vacío. "
            "OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La ficha técnica se generó vacía."
                ),
            },
            status=500,
        )


    if not pdf_bytes.startswith(
        b"%PDF"
    ):
        logger.error(
            "El archivo generado no tiene firma PDF. "
            "OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El documento generado no es "
                    "un PDF válido."
                ),
            },
            status=500,
        )


    # ======================================================
    # 11. NOMBRE DEL ARCHIVO
    # ======================================================

    nombre_archivo = str(
        contexto.get(
            "nombre_archivo",
            "",
        )
        or ""
    ).strip()

    if not nombre_archivo:
        nombre_archivo = (
            f"{numero_orden}_FICHA-TECNICA"
        )

    if not nombre_archivo.lower().endswith(
        ".pdf"
    ):
        nombre_archivo += ".pdf"


    # ======================================================
    # 12. SUCURSAL / USUARIO
    # ======================================================

    sucursal = _obtener_nombre_sucursal(
        orden
    )

    usuario_erp = _obtener_usuario_erp(
        request
    )


    # ======================================================
    # 13. TEXTO DEL DOCUMENTO
    # ======================================================

    caption = (
        f"Ficha técnica {numero_orden}"
    )


    # ======================================================
    # 14. ERP -> MAO ASISTENTE
    # ======================================================

    try:
        resultado = (
            enviar_ficha_whatsapp_asistente(
                telefono=telefono,
                numero_orden=numero_orden,
                pdf_bytes=pdf_bytes,
                nombre_archivo=nombre_archivo,
                sucursal=sucursal,
                usuario_erp=usuario_erp,
                caption=caption,
            )
        )


    # ======================================================
    # CONFIGURACIÓN FALTANTE
    # ======================================================

    except MAOAsistenteNoConfigurado:

        logger.error(
            "Integración con MAO Asistente "
            "no configurada. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "La integración con MAO Asistente "
                    "no está configurada."
                ),
            },
            status=503,
        )


    # ======================================================
    # TOKEN INCORRECTO
    # ======================================================

    except MAOAsistenteNoAutorizado:

        logger.error(
            "MAO Asistente rechazó la autenticación "
            "del ERP. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "MAO Asistente rechazó "
                    "la autenticación del ERP."
                ),
            },
            status=502,
        )


    # ======================================================
    # SOLICITUD INVÁLIDA
    # ======================================================

    except MAOAsistenteSolicitudInvalida as exc:

        logger.warning(
            "MAO Asistente rechazó los datos "
            "de la ficha. OT=%s Error=%s",
            numero_orden,
            exc,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": str(exc),
            },
            status=400,
        )


    # ======================================================
    # ASISTENTE NO DISPONIBLE
    # ======================================================

    except MAOAsistenteNoDisponible as exc:

        logger.error(
            "MAO Asistente no disponible "
            "durante envío. OT=%s Error=%s",
            numero_orden,
            exc,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "No fue posible comunicarse "
                    "con MAO Asistente."
                ),
            },
            status=503,
        )


    # ======================================================
    # ERROR NO CONTROLADO
    # ======================================================

    except Exception:

        logger.exception(
            "Error inesperado enviando ficha "
            "por WhatsApp. OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Ocurrió un error inesperado "
                    "durante el envío."
                ),
            },
            status=500,
        )


    # ======================================================
    # 15. VALIDAR RESPUESTA
    # ======================================================

    if resultado.get(
        "ok"
    ) is not True:

        logger.error(
            "Respuesta inesperada de MAO Asistente. "
            "OT=%s",
            numero_orden,
        )

        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "MAO Asistente no confirmó "
                    "el envío del documento."
                ),
            },
            status=502,
        )


    # ======================================================
    # 16. IDENTIFICADORES META
    # ======================================================

    wamid = resultado.get(
        "wamid"
    )

    media_id = resultado.get(
        "media_id"
    )


    # ======================================================
    # 17. LOG
    # ======================================================
    #
    # No registramos el teléfono del cliente.
    #
    # ======================================================

    logger.info(
        "Documento enviado a MAO Asistente. "
        "OT=%s Documento=%s Medio=%s "
        "Usuario=%s Sucursal=%s "
        "wamid=%s media_id=%s",
        numero_orden,
        documento,
        medio,
        usuario_erp or "-",
        sucursal or "-",
        wamid or "-",
        media_id or "-",
    )


    # ======================================================
    # 18. RESPUESTA AL NAVEGADOR
    # ======================================================

    return JsonResponse(
        {
            "ok": True,

            "mensaje": (
                "La ficha técnica fue enviada "
                "por WhatsApp."
            ),

            "numero_orden":
                numero_orden,

            "documento":
                documento,

            "medio":
                medio,

            "wamid":
                wamid,
        },
        status=200,
    )