"""Comando de gerenciamento para importar alunos a partir de planilha (.xlsx ou .csv)."""
import os
from django.core.management.base import BaseCommand, CommandError
from ebd.core.utils import read_xlsx_rows_from_file, read_csv_rows_from_file, process_alunos_import


class Command(BaseCommand):
    help = 'Importa alunos e carrega turmas a partir de uma planilha (.xlsx ou .csv).'

    def add_arguments(self, parser):
        parser.add_argument(
            'caminho_arquivo',
            nargs='?',
            default='/home/iotabe/Downloads/Matrícula EBD 2026 (respostas).xlsx',
            help='Caminho do arquivo de planilha (.xlsx ou .csv)'
        )

    def handle(self, *args, **options):
        filepath = options['caminho_arquivo']
        if not os.path.exists(filepath):
            raise CommandError(f'Arquivo não encontrado: {filepath}')

        self.stdout.write(f'Iniciando importação do arquivo: {filepath}')
        if filepath.endswith('.xlsx'):
            alunos_data = read_xlsx_rows_from_file(filepath)
        elif filepath.endswith('.csv'):
            alunos_data = read_csv_rows_from_file(filepath)
        else:
            raise CommandError('Formato de arquivo não suportado. Utilize .xlsx ou .csv.')

        criados, atualizados = process_alunos_import(alunos_data)

        self.stdout.write(
            self.style.SUCCESS(
                f'Importação concluída com sucesso! '
                f'Novos alunos: {criados}, Alunos atualizados: {atualizados}, Total: {len(alunos_data)}'
            )
        )

