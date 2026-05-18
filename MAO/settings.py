from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# SEGURIDAD (Variables de Entorno)
# =========================
# Si no encuentra SECRET_KEY en el .env, usa una genérica (solo para local)
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-83a5(at0*fukqun1r%s7*c2kla=aqyzhf7s^29(-snzawc)i8t')

# DEBUG será True en tu PC y False en DigitalOcean (si lo pones en el .env del servidor)
DEBUG = os.getenv('DEBUG', 'True') == 'True'

# Importante: Agregamos tu dominio y la IP del servidor
ALLOWED_HOSTS = [
    '127.0.0.1', 
    'localhost', 
    '192.81.213.119', 
    'maotaller.com', 
    'www.maotaller.com'
]

# Necesario para que Cloudflare y Django se lleven bien
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'https://maotaller.com',
    'https://www.maotaller.com'
]

# =========================
# APPS INSTALADAS
# =========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    # Tus Apps
    'inventario',
    'ordenes_de_trabajo',
    'compras',
    'empresa',
    'facturacion',
    'servicios',
    'cotizaciones',

]

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'MAO.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'empresa.context_processors.menu_lateral',
            ],
        },
    },
]

WSGI_APPLICATION = 'MAO.wsgi.application'

# =========================
# BASE DE DATOS (Dinámica)
# =========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'mao_db'),
        'USER': os.getenv('DB_USER', 'mao_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''), # Se lee del .env
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# =========================
# INTERNACIONALIZACIÓN
# =========================
LANGUAGE_CODE = 'es-ec'
TIME_ZONE = 'America/Guayaquil'
USE_I18N = True
USE_TZ = True

# =========================
# ARCHIVOS ESTÁTICOS (CONFIGURACIÓN PROFESIONAL)
# =========================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# Esta carpeta es donde Nginx buscará los archivos en el servidor
STATIC_ROOT = BASE_DIR / 'staticfiles' 

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# =========================
# CONFIGURACIONES EXTRA
# =========================
AUTH_USER_MODEL = 'inventario.Usuario'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# =========================
# 🤖 GEMINI API
# =========================
GEMINI_API_KEY = "AIzaSyBMzvUKzsdX_Le2BeBjsCwo4bbcp-CJnPI"


'''
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# =========================
# 🔐 SEGURIDAD
# =========================
SECRET_KEY = 'MaoSistem@_2002_1975'
DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']


# =========================
# 📦 APPS INSTALADAS
# =========================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'inventario',
    'ordenes_de_trabajo',
    'compras',
    'empresa',
    'facturacion',
    'servicios',
    'cotizaciones',
]


# =========================
# ⚙️ MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
# =========================
# BASE DE DATOS LOCAL
# =========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mao_local',
        'USER': 'postgres',
        'PASSWORD': '12345',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# =========================
# 🌐 URLS / WSGI
# =========================
ROOT_URLCONF = 'MAO.urls'
WSGI_APPLICATION = 'MAO.wsgi.application'


# =========================
# 🎨 TEMPLATES
# =========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'empresa.context_processors.menu_lateral',
            ],
        },
    },
]


# =========================
# 🐘 BASE DE DATOS (POSTGRESQL)
# =========================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mao_local',
        'USER': 'postgres',
        'PASSWORD': '12345',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# =========================
# 🔑 VALIDADORES
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# =========================
# 🌎 INTERNACIONALIZACIÓN
# =========================
LANGUAGE_CODE = 'es-ec'
TIME_ZONE = 'America/Guayaquil'
USE_I18N = True
USE_TZ = True


# =========================
# 📁 STATIC / MEDIA
# =========================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# =========================
# 👤 USUARIO PERSONALIZADO
# =========================
AUTH_USER_MODEL = 'inventario.Usuario'


# =========================
# 🔐 LOGIN / LOGOUT
# =========================
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'
LOGIN_URL = 'login'


# =========================
# 🔢 PK DEFAULT
# =========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =========================
# 🤖 GEMINI API
# =========================
GEMINI_API_KEY = "AIzaSyBMzvUKzsdX_Le2BeBjsCwo4bbcp-CJnPI"

'''