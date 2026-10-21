"""Isolated SQLite checks. Never imports production settings or credentials."""
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = 'local-tests-only-not-used-in-production'
DEBUG = True
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1', 'terminal.local']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
 'django.contrib.messages', 'django.contrib.staticfiles', 'django.contrib.humanize',
 'inventario', 'ordenes_de_trabajo', 'compras', 'empresa', 'facturacion', 'servicios',
 'cotizaciones', 'avaluos', 'accesos', 'contabilidad', 'asistencia']
AUTH_USER_MODEL = 'inventario.Usuario'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
ROOT_URLCONF = 'cotizaciones.test_urls'
USE_TZ = True
TIME_ZONE = 'America/Guayaquil'
LANGUAGE_CODE = 'es-ec'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
LOGIN_URL = '/login/'
MIDDLEWARE = ['django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware']
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS':[BASE_DIR/'templates'],
 'APP_DIRS': True, 'OPTIONS':{'context_processors':['django.template.context_processors.request',
 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages', 'empresa.context_processors.menu_lateral']}}]
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
