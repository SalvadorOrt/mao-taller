import json
import secrets

from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .services import (
    CodigoSSOInvalido,
    generar_codigo_sso,
    canjear_codigo_sso,
)


# =========================================================
# MAO ASISTENTE HABILITADO
# =========================================================


def _asistente_habilitado():
    """
    Indica si la integración con MAO Asistente
    está habilitada en este entorno.

    Si la variable no existe, permanece deshabilitada.
    """

    return bool(
        getattr(
            settings,
            "MAO_ASISTENTE_HABILITADO",
            False,
        )
    )


def asistente_habilitado_required(view_func):
    """
    Impide exponer endpoints relacionados con MAO Asistente
    cuando la integración está deshabilitada.

    Se responde 404 para que el ERP se comporte como si
    esa funcionalidad no estuviera disponible.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):

        if not _asistente_habilitado():
            raise Http404

        return view_func(
            request,
            *args,
            **kwargs,
        )

    return wrapper


# =========================================================
# SEGURIDAD SERVIDOR A SERVIDOR
# =========================================================


def _servicio_asistente_autorizado(request):
    """
    Comprueba el secreto compartido entre ERP MAO
    y MAO Asistente.

    Este secreto nunca viaja en el navegador.
    """

    esperado = getattr(
        settings,
        "ASISTENTE_SSO_EXCHANGE_SECRET",
        "",
    )

    if not esperado:
        return False

    authorization = request.headers.get(
        "Authorization",
        "",
    )

    prefijo = "Bearer "

    if not authorization.startswith(
        prefijo
    ):
        return False

    recibido = authorization[
        len(prefijo):
    ].strip()

    if not recibido:
        return False

    return secrets.compare_digest(
        recibido,
        esperado,
    )


# =========================================================
# ENTRAR A MAO ASISTENTE
# =========================================================


@asistente_habilitado_required
@login_required
@require_GET
def entrar_asistente(request):
    """
    Punto de entrada visible desde el ERP.

    El empleado ya debe tener una sesión ERP válida.

    Este endpoint no existe funcionalmente cuando
    MAO_ASISTENTE_HABILITADO=False.
    """

    if not request.user.is_active:
        return JsonResponse(
            {
                "ok": False,
                "error": "Usuario ERP inactivo.",
            },
            status=403,
        )

    callback_url = getattr(
        settings,
        "ASISTENTE_SSO_CALLBACK_URL",
        "",
    ).strip()

    if not callback_url:
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

    # En producción el callback debe utilizar HTTPS.
    if (
        not settings.DEBUG
        and not callback_url.startswith(
            "https://"
        )
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "El callback de MAO Asistente "
                    "debe utilizar HTTPS."
                ),
            },
            status=503,
        )

    codigo, _ = generar_codigo_sso(
        request.user
    )

    parametros = urlencode(
        {
            "code": codigo,
        }
    )

    separador = (
        "&"
        if "?" in callback_url
        else "?"
    )

    return redirect(
        f"{callback_url}{separador}{parametros}"
    )


# =========================================================
# CANJEAR CÓDIGO
# =========================================================


@asistente_habilitado_required
@csrf_exempt
@require_POST
def canjear_codigo_asistente(request):
    """
    Endpoint interno utilizado por el servidor
    de MAO Asistente.

    No necesita sesión ERP ni CSRF porque utiliza
    autenticación servidor-a-servidor mediante
    un secreto compartido.

    Cuando MAO Asistente está deshabilitado,
    este endpoint responde 404.
    """

    if not _servicio_asistente_autorizado(
        request
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "No autorizado.",
            },
            status=401,
        )

    try:
        payload = json.loads(
            request.body.decode(
                "utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        UnicodeDecodeError,
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Solicitud inválida.",
            },
            status=400,
        )

    if not isinstance(
        payload,
        dict,
    ):
        return JsonResponse(
            {
                "ok": False,
                "error": "Solicitud inválida.",
            },
            status=400,
        )

    codigo = payload.get(
        "code",
        "",
    )

    try:
        identidad = canjear_codigo_sso(
            codigo
        )

    except CodigoSSOInvalido:
        # No revelamos si el código:
        # - no existe;
        # - expiró;
        # - ya fue utilizado.
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Código inválido o vencido."
                ),
            },
            status=400,
        )

    return JsonResponse(
        {
            "ok": True,
            "identidad": identidad,
        }
    )