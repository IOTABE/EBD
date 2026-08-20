"""Configurações do projeto EBD — Escola Bíblica Dominical.

Banco de dados:
  * DEBUG=True  -> SQLite3 (desenvolvimento)
  * DEBUG=False -> PostgreSQL (produção) via DATABASE_URL
"""
from pathlib import Path

from decouple import AutoConfig, Config, RepositoryEnv
import dj_database_url

# ---------------------------------------------------------------- Base
BASE_DIR = Path(__file__).resolve().parent.parent


def _carregar_config():
    """Carrega o .env do projeto independentemente do diretório de execução.

    O gunicorn de produção é iniciado sem ``--chdir``/``--pythonpath``, então o
    CWD não é o do projeto. Buscamos o ``.env`` primeiro na raiz do código
    (BASE_DIR/../) e depois no diretório do settings; caso contrário usamos os
    padrões (desenvolvimento).
    """
    for caminho in (BASE_DIR, BASE_DIR.parent):
        env = caminho / '.env'
        if env.exists():
            return Config(RepositoryEnv(str(env)))
    return AutoConfig(search_path=str(BASE_DIR))


config = _carregar_config()

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-only-change-me')

DEBUG = config('DEBUG', default=True, cast=bool)

# Domínios canônicos do site. Fonte única para ALLOWED_HOSTS e
# CSRF_TRUSTED_ORIGINS — garante que "www" nunca seja esquecido em produção.
DOMINIOS = ['ibnj.top', 'www.ibnj.top']

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=lambda v: [h.strip() for h in v.split(',') if h.strip()],
)
# Sempre aceita os domínios do site, mesmo que faltem no .env de produção.
ALLOWED_HOSTS = list(dict.fromkeys(ALLOWED_HOSTS + DOMINIOS))

# ------------------------------------------------------------ Aplicações
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # App principal da EBD
    'ebd.core.apps.CoreConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'ebd.core.audit_context.AuditMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ebd.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ebd.wsgi.application'

# ------------------------------------------------------------ Banco de dados
# REGRA DE ARQUITETURA:
#   * DEBUG=True  -> SQLite3 (simples, sem configuração)
#   * DEBUG=False -> PostgreSQL (via DATABASE_URL no .env / ambiente)
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': dj_database_url.config(
            default=config('DATABASE_URL'),
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

# ------------------------------------------------------------ Senhas e i18n
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------ Cache
# Cache em memória para as consultas de agregação dos relatórios
# (relatorio_dominical, relatorio_mensal, relatorio_ranking).
# Em produção, pode ser trocado por Redis/Memcached.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'ebd-cache',
        'TIMEOUT': 300,  # 5 minutos
    }
}

#
# ------------------------------------------------------------ Autenticação
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'login'

# ------------------------------------------------------------ Arquivos estáticos
STATIC_URL = '/static/'
# STATIC_ROOT pode ser fixado via env (ex.: STATIC_ROOT=/www/wwwroot/ibnj.top/staticfiles)
# caso o web server sirva os estáticos por um caminho específico.
STATIC_ROOT = Path(config('STATIC_ROOT', default=str(BASE_DIR / 'staticfiles')))
# Os estáticos do app ficam dentro do pacote (ebd/core/static) e são
# encontrados pelos finders; não há diretório externo "static/".
# Storage dos estáticos (o antigo STATICFILES_STORAGE foi removido no Django 5.1).
# Manifest + compressão do WhiteNoise: gera nomes com hash e cache-busting.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# ------------------------------------------------------------ HTTPS (produção)
# Aplicável apenas com DEBUG=False (servidor por trás de proxy reverso que
# encerra o TLS, ex.: Nginx/Caddy). Em desenvolvimento mantém HTTP simples.
if not DEBUG:
    # Confia no cabeçalho X-Forwarded-Proto enviado pelo proxy reverso.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    CSRF_TRUSTED_ORIGINS = [f'https://{d}' for d in DOMINIOS]

    # Redireciona todo o tráfego HTTP para HTTPS.
    SECURE_SSL_REDIRECT = True

    # Cookies somente via HTTPS.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # HSTS (HTTP Strict Transport Security) — forçar HTTPS no navegador.
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Headers de segurança adicionais.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    X_FRAME_OPTIONS = 'DENY'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

