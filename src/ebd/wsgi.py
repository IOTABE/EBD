"""Configuração WSGI para deploy em produção."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebd.settings')

application = get_wsgi_application()
