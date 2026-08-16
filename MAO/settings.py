from pathlib import Path
import os

from dotenv import load_dotenv


# =========================================================
# BASE DEL PROYECTO
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Carga el archivo .env si existe.
# En local puede no existir y se usarán los valores por defecto.
# En producción DigitalOcean usa las variables configuradas en su .env.
load_dotenv(BASE_DIR / ".env")


# =========================================================
# SEGURIDAD
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-83a5(at0*fukqun1r%s7*c2kla=aqyzhf7s^29(-snzawc)i8t",
)

# Local:
#   si no existe DEBUG en .env -> True
#
# Producción:
#   DEBUG=False en el .env del servidor
DEBUG = os.getenv("DEBUG", "True").lower() == "true"


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
    # Django
    # -----------------------------------------------------
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",

    # -----------------------------------------------------
    # Aplicaciones MAO
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
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",

                # Menú lateral global.
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
# ---------------------------------------------------------
# NAME     = mao_local
# USER     = postgres
# PASSWORD = 12345
# HOST     = localhost
# PORT     = 5432
#
# PRODUCCIÓN:
# ---------------------------------------------------------
# DigitalOcean usa automáticamente las variables DB_NAME,
# DB_USER, DB_PASSWORD, DB_HOST y DB_PORT de su .env.
#
# Por eso este mismo settings.py sirve en ambos entornos.
# =========================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",

        # Valores locales por defecto
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
            "12345",
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


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