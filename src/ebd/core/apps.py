"""Configuração do app core (módulo principal da EBD)."""
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ebd.core'
    verbose_name = 'EBD — Escola Bíblica Dominical'
