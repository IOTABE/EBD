"""Comando de gerenciamento para criar/sincronizar os grupos (papéis) do sistema."""
from django.core.management.base import BaseCommand

from ebd.core.roles import GRUPOS, sincronizar_grupos


class Command(BaseCommand):
    help = 'Cria/sincroniza os grupos (Administrador, Secretaria, Professor) com suas permissões.'

    def handle(self, *args, **options):
        sincronizar_grupos()
        for grupo_def in GRUPOS:
            grupo = grupo_def['nome']
            qtd = grupo_def['permissoes'].__len__()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Grupo "{grupo}" sincronizado com {qtd} permissão(ões).'
                )
            )