"""Utilitários para importação e exportação de planilhas de alunos."""
import csv
import io
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from .audit import registrar_manual
from .audit_context import auditoria_suprimida, get_current_user
from .models import Aluno, Auditoria, Classe, normalizar_nome


CLASS_NAME_MAP = {
    'herois da fe': 'Heróis da fé',
    'heróis da fé': 'Heróis da fé',
    'herois da fé': 'Heróis da fé',
    'discipulos mirins': 'Discípulos Mirins',
    'discípulos mirins': 'Discípulos Mirins',
    'conectados': 'Conectados',
    'influenciadores': 'Influenciadores',
    'raios de luz': 'Raios de Luz',
    'jardim do eden': 'Jardim do Éden',
    'jardim do éden': 'Jardim do Éden',
}


def parse_excel_date(val) -> Optional[datetime.date]:
    """Converte valor serial do Excel ou string de data para datetime.date."""
    if not val:
        return None
    if isinstance(val, (int, float)):
        try:
            return (datetime(1899, 12, 30) + timedelta(days=float(val))).date()
        except Exception:
            return None
    s = str(val).strip()
    try:
        f = float(s)
        if 1 <= f <= 60000:
            return (datetime(1899, 12, 30) + timedelta(days=f)).date()
    except ValueError:
        pass
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def clean_phone(val) -> str:
    """Formata string de telefone para formato legível."""
    if not val:
        return ''
    s = str(val).strip()
    try:
        f = float(s)
        s = str(int(f))
    except ValueError:
        pass
    digits = re.sub(r'\D', '', s)
    if len(digits) == 11:
        return f'({digits[:2]}) {digits[2:7]}-{digits[7:]}'
    elif len(digits) == 10:
        return f'({digits[:2]}) {digits[2:6]}-{digits[6:]}'
    elif len(digits) > 0:
        return s
    return ''


def normalize_class_name(raw_name: str) -> str:
    """Padroniza nome da classe com acentuação correta."""
    name = raw_name.strip()
    key = name.lower()
    return CLASS_NAME_MAP.get(key, name)


def read_xlsx_rows_from_file(file_obj):
    """Lê linhas de um arquivo Excel .xlsx em memória ou disco.

    Retorna ``(alunos, erros)`` — ``erros`` é uma lista de dicionários
    ``{'linha': n, 'valor': ..., 'erro': ...}`` com problemas encontrados
    linha a linha (ex.: nome vazio, data inválida).
    """
    with zipfile.ZipFile(file_obj) as z:
        wb_tree = ET.fromstring(z.read('xl/workbook.xml'))
        sst = []
        if 'xl/sharedStrings.xml' in z.namelist():
            sst_tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in sst_tree.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                text = ''.join([t.text or '' for t in si.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')])
                sst.append(text)

        sheet_xml = z.read('xl/worksheets/sheet1.xml')
        sheet_tree = ET.fromstring(sheet_xml)
        rows = sheet_tree.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')

        def col_idx(col_str):
            col_name = ''.join([ch for ch in col_str if ch.isalpha()])
            idx = 0
            for ch in col_name:
                idx = idx * 26 + (ord(ch) - ord('A') + 1)
            return idx - 1

        alunos = []
        erros = []
        for r_idx, r in enumerate(rows):
            if r_idx == 0:
                continue
            row_dict = {}
            for c in r.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c'):
                r_ref = c.attrib['r']
                col = col_idx(r_ref)
                t = c.attrib.get('t')
                v_elem = c.find('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                v = v_elem.text if v_elem is not None else ''
                if t == 's' and v != '':
                    v = sst[int(v)]
                row_dict[col] = v

            max_c = max(row_dict.keys()) if row_dict else -1
            row_list = [row_dict.get(i, '') for i in range(max_c + 1)]
            linha = r_idx + 1

            nome = str(row_list[1]).strip() if len(row_list) > 1 else ''
            if not nome:
                erros.append({'linha': linha, 'valor': '', 'erro': 'Nome vazio'})
                continue

            nasc_raw = row_list[3] if len(row_list) > 3 else ''
            nasc = parse_excel_date(nasc_raw)
            if not nasc and str(nasc_raw).strip():
                erros.append({
                    'linha': linha,
                    'valor': str(nasc_raw).strip(),
                    'erro': 'Data de nascimento inválida (ignorada)',
                })
            tel_raw = row_list[4] if len(row_list) > 4 else ''
            tel = clean_phone(tel_raw)
            classe_raw = str(row_list[5]).strip() if len(row_list) > 5 else 'Sem Classe'
            classe = normalize_class_name(classe_raw)

            alunos.append((nome, nasc, tel, classe))
        return alunos, erros


def read_csv_rows_from_file(file_obj):
    """Lê linhas de um arquivo CSV.

    Retorna ``(alunos, erros)`` — ``erros`` é uma lista de dicionários
    ``{'linha': n, 'valor': ..., 'erro': ...}`` com problemas encontrados
    linha a linha (ex.: nome vazio, data inválida).
    """
    if isinstance(file_obj, bytes):
        file_obj = io.StringIO(file_obj.decode('utf-8-sig'))
    elif hasattr(file_obj, 'read') and not isinstance(file_obj, io.TextIOBase):
        content = file_obj.read()
        if isinstance(content, bytes):
            file_obj = io.StringIO(content.decode('utf-8-sig'))
        else:
            file_obj = io.StringIO(content)

    alunos = []
    erros = []
    reader = csv.reader(file_obj)
    header = next(reader, None)
    linha = 1
    for row in reader:
        linha += 1
        if not row or not any(row):
            continue
        nome = row[1].strip() if len(row) > 1 else (row[0].strip() if len(row) > 0 else '')
        if nome.lower() in ('nome', 'carimbo de data/hora'):
            continue
        if not nome:
            erros.append({'linha': linha, 'valor': '', 'erro': 'Nome vazio'})
            continue
        nasc_raw = row[3] if len(row) > 3 else ''
        nasc = parse_excel_date(nasc_raw)
        if not nasc and str(nasc_raw).strip():
            erros.append({
                'linha': linha,
                'valor': str(nasc_raw).strip(),
                'erro': 'Data de nascimento inválida (ignorada)',
            })
        tel_raw = row[4] if len(row) > 4 else ''
        tel = clean_phone(tel_raw)
        classe_raw = row[5].strip() if len(row) > 5 else 'Sem Classe'
        classe = normalize_class_name(classe_raw)
        alunos.append((nome, nasc, tel, classe))
    return alunos, erros


def process_alunos_import(alunos_data: List[Tuple[str, Optional[datetime.date], str, str]]):
    """Processa e salva uma lista de alunos no banco de dados.

    Sinais de auditoria suprimidos por aluno: a importação em lote
    registra um único resumo da operação ao final.

    Retorna ``(criados, atualizados, erros)`` — ``erros`` é uma lista de
    dicionários ``{'linha': n, 'valor': ..., 'erro': ...}`` com falhas
    de processamento detectadas linha a linha.
    """
    criados = 0
    atualizados = 0
    erros = []
    with auditoria_suprimida():
        for numero, (nome, nasc, tel, nome_classe) in enumerate(alunos_data, start=1):
            try:
                classe, _ = Classe.objects.get_or_create(
                    nome=nome_classe,
                    defaults={'faixa_etaria': 'A definir'}
                )

                aluno = Aluno.objects.filter(
                    nome_normalizado=normalizar_nome(nome),
                    classe=classe,
                ).first()
                if aluno:
                    # Atualiza os dados mantendo o nome de exibição original.
                    aluno.data_nascimento = nasc
                    aluno.telefone = tel
                    aluno.status = Aluno.Status.ATIVO
                    aluno.save()
                    atualizados += 1
                else:
                    Aluno.objects.create(
                        nome=nome,
                        classe=classe,
                        data_nascimento=nasc,
                        telefone=tel,
                        status=Aluno.Status.ATIVO,
                    )
                    criados += 1
            except Exception as e:
                erros.append({
                    'linha': numero,
                    'valor': nome,
                    'erro': f'Falha ao processar: {e}',
                })

    registrar_manual(
        modelo='aluno',
        acao=Auditoria.Acao.EDITAR,
        usuario=get_current_user(),
        descricao=f'Importação de planilha: {criados} criado(s), '
                  f'{atualizados} atualizado(s), {len(erros)} erro(s).',
        dados={'criados': criados, 'atualizados': atualizados, 'erros': len(erros)},
    )

    return criados, atualizados, erros
