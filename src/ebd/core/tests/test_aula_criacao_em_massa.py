"""Testes da criação de aulas em massa para todas as classes.

Ao criar uma nova aula informando apenas data/lição/observações, o sistema
deve gerar uma aula para cada classe que ainda não possui aula naquela data.
"""
from datetime import date

import pytest
from django.urls import reverse

from ebd.core.models import Aula, Auditoria, Classe, Professor

pytestmark = pytest.mark.django_db


@pytest.fixture
def professor(db):
    return Professor.objects.create(nome='Prof. Teste')


@pytest.fixture
def classes(db, professor):
    return [
        Classe.objects.create(nome=f'Classe {n}', faixa_etaria=f'Faixa {n}')
        for n in (1, 2, 3)
    ]


def test_form_nova_aula_sem_campo_classe(cliente_com_permissoes):
    client = cliente_com_permissoes('add_aula')

    resp = client.get(reverse('core:aula_create'))

    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'id_classe' not in html
    assert 'todas as classes' in html


def _post_aula(client, **kwargs):
    payload = {
        'data': kwargs.get('data', '2026-08-23'),
        'licao': kwargs.get('licao', 'Lição 10'),
        'observacoes': kwargs.get('observacoes', ''),
    }
    return client.post(reverse('core:aula_create'), payload)


def test_cria_aula_para_todas_as_classes(classes, cliente_com_permissoes):
    client = cliente_com_permissoes('add_aula')

    resp = _post_aula(client, licao='Lição 10', observacoes='Revisão')

    assert resp.status_code == 302
    assert Aula.objects.count() == 3
    for classe in classes:
        aula = Aula.objects.get(classe=classe, data=date(2026, 8, 23))
        assert aula.licao == 'Lição 10'
        assert aula.observacoes == 'Revisão'


def test_nao_duplica_aula_em_classe_que_ja_tem(classes, cliente_com_permissoes):
    client = cliente_com_permissoes('add_aula')
    Aula.objects.create(data='2026-08-23', classe=classes[0], licao='Existente')

    _post_aula(client)

    assert Aula.objects.filter(data='2026-08-23').count() == 3
    assert Aula.objects.get(classe=classes[0], data='2026-08-23').licao == 'Existente'
    for classe in classes[1:]:
        assert Aula.objects.get(classe=classe, data='2026-08-23').licao == 'Lição 10'


def test_sem_classes_nao_cria_aula(cliente_com_permissoes):
    client = cliente_com_permissoes('add_aula')

    resp = _post_aula(client)

    assert resp.status_code == 302
    assert Aula.objects.count() == 0


def test_aula_criada_registra_auditoria_e_responsavel(classes, cliente_com_permissoes):
    client = cliente_com_permissoes('add_aula')

    _post_aula(client)

    assert Aula.objects.count() == 3
    assert Aula.objects.filter(criado_por__isnull=False).count() == 3
    assert Auditoria.objects.filter(modelo='Aula', acao='criar').count() == 3