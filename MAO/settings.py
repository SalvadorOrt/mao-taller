from pathlib import Path
import os

from dotenv import load_dotenv


# =========================================================
# BASE DEL PROYECTO
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga las variables locales desde .env.
# En producción también se utilizan variables de entorno.
load_dotenv(BASE_DIR / ".env")


# =========================================================
# HELPERS DE CONFIGURACIÓN
# =========================================================


def env_bool(nombre, default=False):
    """
    Lee una variable de entorno como booleano.

    Valores considerados True:
    1, true, yes, on

    Cualquier otro valor se considera False.
    """

    valor_default = "True" if default else "False"

    return (
        os.getenv(
            nombre,
            valor_default,
        )
        .strip()
        .lower()
        in {
            "1",
            "true",
            "yes",
            "on",
        }
    )


# =========================================================
# SEGURIDAD
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-local-development-only",
)


# ---------------------------------------------------------
# DEBUG
# ---------------------------------------------------------
#
# LOCAL:
# si DEBUG no existe en .env -> True
#
# PRODUCCIÓN:
# DEBUG=False
# ---------------------------------------------------------

DEBUG = env_bool(
    "DEBUG",
    default=True,
)


ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "192.81.213.119",
    "maotaller.com",
    "www.maotaller.com",
]


CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://maotaller.com",
    "https://www.maotaller.com",
]


# =========================================================
# APPS INSTALADAS
# =========================================================

INSTALLED_APPS = [

    # -----------------------------------------------------
    # DJANGO
    # -----------------------------------------------------

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # -----------------------------------------------------
    # APLICACIONES MAO
    # -----------------------------------------------------

    "inventario",
    "ordenes_de_trabajo",
    "compras",
    "empresa",
    "facturacion",
    "servicios",
    "cotizaciones",
    "avaluos",
    "accesos",
    "integraciones",
]


# =========================================================
# MIDDLEWARE
# =========================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =========================================================
# URLS / WSGI
# =========================================================

ROOT_URLCONF = "MAO.urls"

WSGI_APPLICATION = "MAO.wsgi.application"


# =========================================================
# TEMPLATES
# =========================================================

TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [

                "django.template.context_processors.debug",

                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages."
                "context_processors.messages",

                # Menú lateral global MAO.
                "empresa.context_processors.menu_lateral",
            ],
        },
    },
]


# =========================================================
# BASE DE DATOS
# =========================================================
#
# LOCAL:
#
# DB_NAME=mao_local
# DB_USER=postgres
# DB_PASSWORD=...
# DB_HOST=localhost
# DB_PORT=5432
#
# PRODUCCIÓN:
# Los valores deben venir del .env del servidor.
# =========================================================

DATABASES = {
    "default": {

        "ENGINE": (
            "django.db.backends.postgresql"
        ),

        "NAME": os.getenv(
            "DB_NAME",
            "mao_local",
        ),

        "USER": os.getenv(
            "DB_USER",
            "postgres",
        ),

        "PASSWORD": os.getenv(
            "DB_PASSWORD",
            "",
        ),

        "HOST": os.getenv(
            "DB_HOST",
            "localhost",
        ),

        "PORT": os.getenv(
            "DB_PORT",
            "5432",
        ),
    }
}


# =========================================================
# VALIDADORES DE CONTRASEÑAS
# =========================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =========================================================
# INTERNACIONALIZACIÓN
# =========================================================

LANGUAGE_CODE = "es-ec"

TIME_ZONE = "America/Guayaquil"

USE_I18N = True

USE_TZ = True


# =========================================================
# ARCHIVOS ESTÁTICOS
# =========================================================

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# En producción Nginx sirve esta carpeta.
STATIC_ROOT = BASE_DIR / "staticfiles"


# =========================================================
# ARCHIVOS MEDIA
# =========================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =========================================================
# USUARIO PERSONALIZADO
# =========================================================

AUTH_USER_MODEL = "inventario.Usuario"


# =========================================================
# LOGIN / LOGOUT
# =========================================================

LOGIN_REDIRECT_URL = "dashboard"

LOGOUT_REDIRECT_URL = "login"

LOGIN_URL = "login"


# =========================================================
# PRIMARY KEY POR DEFECTO
# =========================================================

DEFAULT_AUTO_FIELD = (
    "django.db.models.BigAutoField"
)


# =========================================================
# API KEYS
# =========================================================

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

PLACA_API_USERNAME = os.getenv(
    "PLACA_API_USERNAME"
)

CEDULA_API_TOKEN = os.getenv(
    "CEDULA_API_TOKEN"
)


# =========================================================
# MAO ASISTENTE - ACTIVACIÓN
# =========================================================
#
# Esta bandera permite conservar toda la integración
# del Asistente dentro del ERP sin mostrarla mientras
# todavía está en desarrollo.
#
#
# MAO_ASISTENTE_HABILITADO=False
#
#     ERP funciona normalmente.
#     El Asistente no aparece en el menú.
#
#
# MAO_ASISTENTE_HABILITADO=True
#
#     Aparece el acceso al Asistente.
#     Se habilita el flujo SSO.
#
#
# En producción puede permanecer False hasta que
# MAO Asistente esté listo.
# =========================================================

MAO_ASISTENTE_HABILITADO = env_bool(
    "MAO_ASISTENTE_HABILITADO",
    default=False,
)


# =========================================================
# MAO ASISTENTE - SSO
# =========================================================
#
# Estas variables permanecen configuradas aunque el
# Asistente esté deshabilitado.
#
# No es necesario borrar la integración ni sus secretos
# cada vez que MAO_ASISTENTE_HABILITADO=False.
# =========================================================

ASISTENTE_SSO_CALLBACK_URL = os.getenv(
    "ASISTENTE_SSO_CALLBACK_URL",
    (
        "http://127.0.0.1:8001/"
        "integraciones/mao-erp/sso/entrada/"
    ),
)


ASISTENTE_SSO_EXCHANGE_SECRET = os.getenv(
    "ASISTENTE_SSO_EXCHANGE_SECRET",
    "",
)


ASISTENTE_SSO_TTL_SECONDS = int(
    os.getenv(
        "ASISTENTE_SSO_TTL_SECONDS",
        "60",
    )
)
# =========================================================
# MAO ASISTENTE - API SERVIDOR A SERVIDOR
# =========================================================
#
# Esta configuración se utiliza para que el ERP pueda
# realizar llamadas privadas hacia MAO Asistente.
#
# Ejemplo actual:
#
# ERP
#   |
#   | PDF frontal + teléfono de la OT
#   |
#   v
# MAO Asistente
#   |
#   v
# Meta / WhatsApp
#
#
# LOCAL:
#
# MAO_ASISTENTE_BASE_URL=http://127.0.0.1:8001
#
#
# PRODUCCIÓN:
#
# MAO_ASISTENTE_BASE_URL=https://asistente.maotaller.com
#
#
# MAO_ASISTENTE_SERVICE_TOKEN debe contener exactamente
# el mismo secreto que MAO_ERP_SERVICE_TOKEN en el
# .env de MAO Asistente.
#
# IMPORTANTE:
#
# Este secreto NO es el secreto utilizado por el SSO.
#
# =========================================================

MAO_ASISTENTE_BASE_URL = (
    os.getenv(
        "MAO_ASISTENTE_BASE_URL",
        "http://127.0.0.1:8001",
    )
    .strip()
    .rstrip("/")
)


MAO_ASISTENTE_SERVICE_TOKEN = (
    os.getenv(
        "MAO_ASISTENTE_SERVICE_TOKEN",
        "",
    )
    .strip()
)


MAO_ASISTENTE_TIMEOUT_SECONDS = int(
    os.getenv(
        "MAO_ASISTENTE_TIMEOUT_SECONDS",
        "30",
    )
)

# =========================================================
# COOKIES ERP
# =========================================================
#
# El ERP y MAO Asistente corren sobre el mismo host
# durante desarrollo pero utilizan cookies diferentes.
#
# Esto evita colisiones de sesión entre:
#
# ERP        -> puerto 8000
# Asistente  -> puerto 8001
# =========================================================

SESSION_COOKIE_NAME = (
    "mao_erp_sessionid"
)

CSRF_COOKIE_NAME = (
    "mao_erp_csrftoken"
)