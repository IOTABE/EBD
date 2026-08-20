#!/usr/bin/env python
"""Utilitário de linha de comando do Django para o projeto EBD.

Uso: python manage.py runserver | makemigrations | migrate | createsuperuser
"""
import os
import sys
from pathlib import Path


def main() -> None:
    # Projeto em layout "src/": garante que o código do checkout atual seja
    # usado (e não uma cópia instalada em site-packages).
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ebd.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            'Não foi possível importar o Django. '
            'Confirme se ele está instalado e o ambiente virtual ativado.'
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
