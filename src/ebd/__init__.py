"""Ponto de entrada do pacote EBD.

Permite executar os comandos do Django via CLI: `ebd runserver`.
"""
import os
import sys


def main() -> None:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebd.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
