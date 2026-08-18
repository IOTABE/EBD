"""Testes das regras de negócio (RN-01 a RN-10) descritas no PRD.md.

Cada classe/`test_` cobre uma regra de negócio específica:

  * RN-01 — abrir a chamada cria/garante presença de TODOS os ativos;
  * RN-02 — alunos inativos não aparecem na chamada;
  * RN-03 — matriculados nos relatórios contam apenas alunos ativos;
  * RN-04 — aula única por classe + data (IntegrityError);
  * RN-05 — presença única por aluno + aula (IntegrityError);
  * RN-06 — classe aceita no máximo 4 professores;
  * RN-07 — classe com alunos não pode ser excluída (ProtectedError);
  * RN-08 — importação cria novos e atualiza registros iguais;
  * RN-09 — percentuais: presentes/matriculados (relatórios) e
            presentes/chamadas (ranking);
  * RN-10 — período do ranking: 01/01 até hoje (ou 31/12) do ano.
"""
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.urls import reverse

from ebd.core.forms import ClasseForm
from ebd.core.models import Aluno, Aula, Classe, Presenca, Professor
from ebd.core.utils import process_alunos_import

pytestmark = pytest.mark.django_db


# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def professor(db):
    return Professor.objects.create(nome='Prof. Teste')


@pytest.fixture
def classe(db, professor):
    c = Classe.objects.create(nome='Juniores', faixa_etaria='9 a 12 anos')
    c.professores.add(professor)
    return c


@pytest.fixture
def aluno_ativo(db, classe):
    return Aluno.objects.create(
        nome='Ana Souza',
        classe=classe,
        data_nascimento=date(2012, 1, 1),
        status=Aluno.Status.ATIVO,
    )


@pytest.fixture
def aluno_inativo(db, classe):
    return Aluno.objects.create(
        nome='Bruno Silva',
        classe=classe,
        status=Aluno.Status.INATIVO,
    )


@pytest.fixture
def aula(db, classe):
    return Aula.objects.create(data=date.today(), classe=classe, licao='Lição 1')


def _criar_presenca(aula, aluno, presente=True):
    return Presenca.objects.create(aula=aula, aluno=aluno, presente=presente)


# =====================================================================
# RN-01 / RN-02 — Chamada
# =====================================================================


class TestChamada:
    def test_rn01_todos_ativos_presentes_por_padrao(
        self, aula, aluno_ativo, aluno_inativo, cliente_com_permissoes
    ):
        Aluno.objects.create(
            nome='Carla Dias', classe=aula.classe, status=Aluno.Status.ATIVO
        )
        client = cliente_com_permissoes('add_presenca', 'change_presenca')
        resp = client.get(reverse('core:aula_chamada', args=[aula.pk]))
        assert resp.status_code == 200
        presencas = Presenca.objects.filter(aula=aula)
        assert presencas.count() == 2
        assert all(p.presente for p in presencas)

    def test_rn02_inativos_fora_da_chamada(
        self, aula, aluno_ativo, aluno_inativo, cliente_com_permissoes
    ):
        client = cliente_com_permissoes('add_presenca', 'change_presenca')
        client.get(reverse('core:aula_chamada', args=[aula.pk]))
        assert not Presenca.objects.filter(aula=aula, aluno=aluno_inativo).exists()
        assert Presenca.objects.filter(aula=aula, aluno=aluno_ativo).exists()

    def test_rn01_abrir_novamente_nao_duplica_presencas(
        self, aula, aluno_ativo, cliente_com_permissoes
    ):
        client = cliente_com_permissoes('add_presenca', 'change_presenca')
        client.get(reverse('core:aula_chamada', args=[aula.pk]))
        client.get(reverse('core:aula_chamada', args=[aula.pk]))
        assert Presenca.objects.filter(aula=aula).count() == 1


# =====================================================================
# RN-03 / RN-09 (relatório dominical)
# =====================================================================


class TestRelatorioDominical:
    def test_rn03_matriculados_contam_apenas_ativos(
        self, aula, aluno_ativo, aluno_inativo, cliente_com_permissoes
    ):
        _criar_presenca(aula, aluno_ativo, presente=True)
        carla = Aluno.objects.create(
            nome='Carla Dias', classe=aula.classe, status=Aluno.Status.ATIVO
        )
        _criar_presenca(aula, carla, presente=True)

        client = cliente_com_permissoes('view_presenca')
        resp = client.get(
            reverse('core:relatorio_dominical'),
            {'data': aula.data.isoformat()},
        )
        c = resp.context['consolidado']
        assert c['matriculados'] == 2
        assert c['presentes'] == 2
        assert c['ausentes'] == 0
        assert c['total'] == 2
        assert c['percentual'] == 100.0

    def test_rn09_percentual_presentes_sobre_matriculados(
        self, aula, aluno_ativo, aluno_inativo, cliente_com_permissoes
    ):
        _criar_presenca(aula, aluno_ativo, presente=False)

        client = cliente_com_permissoes('view_presenca')
        resp = client.get(
            reverse('core:relatorio_dominical'),
            {'data': aula.data.isoformat()},
        )
        c = resp.context['consolidado']
        assert c['matriculados'] == 1
        assert c['presentes'] == 0
        assert c['ausentes'] == 1
        assert c['percentual'] == 0.0


# =====================================================================
# RN-04 / RN-05 — Unicidade
# =====================================================================


class TestUnicidade:
    def test_rn04_aula_unica_por_classe_e_data(self, aula):
        with pytest.raises(IntegrityError), transaction.atomic():
            Aula.objects.create(
                data=aula.data, classe=aula.classe, licao='Lição 2'
            )

    def test_rn05_presenca_unica_por_aula_e_aluno(self, aula, aluno_ativo):
        _criar_presenca(aula, aluno_ativo, presente=True)
        with pytest.raises(IntegrityError), transaction.atomic():
            _criar_presenca(aula, aluno_ativo, presente=False)


# =====================================================================
# RN-06 / RN-07 — Classe
# =====================================================================


class TestClasse:
    def test_rn06_classe_aceita_no_maximo_4_professores(self, classe):
        profs = [Professor.objects.create(nome=f'P{i}') for i in range(5)]
        form = ClasseForm(
            data={
                'nome': classe.nome,
                'faixa_etaria': classe.faixa_etaria,
                'professores': [p.pk for p in profs],
            },
            instance=classe,
        )
        assert form.is_valid() is False
        assert 'professores' in form.errors

    def test_rn06_classe_com_ate_4_professores_ok(self, classe):
        profs = [Professor.objects.create(nome=f'P{i}') for i in range(4)]
        form = ClasseForm(
            data={
                'nome': classe.nome,
                'faixa_etaria': classe.faixa_etaria,
                'professores': [p.pk for p in profs],
            },
            instance=classe,
        )
        assert form.is_valid() is True

    def test_rn07_classe_com_alunos_nao_pode_ser_excluida(
        self, classe, aluno_ativo
    ):
        with pytest.raises(ProtectedError):
            classe.delete()


# =====================================================================
# RN-08 — Importação de alunos
# =====================================================================


class TestImportacao:
    def test_rn08_mesmo_nome_e_classe_atualiza(self):
        dados = [('Ana Souza', date(2012, 1, 1), '11999999999', 'Juniores')]

        criados, atualizados, erros = process_alunos_import(dados)
        assert (criados, atualizados, erros) == (1, 0, [])

        criados, atualizados, erros = process_alunos_import(dados)
        assert (criados, atualizados, erros) == (0, 1, [])
        assert Aluno.objects.filter(nome_normalizado='ana souza').count() == 1
        assert Classe.objects.filter(nome='Juniores').count() == 1

    def test_rn08_nomes_ou_classes_diferentes_criam(self):
        dados = [
            ('Ana Souza', date(2012, 1, 1), '', 'Juniores'),
            ('Bruno Silva', date(2013, 2, 2), '', 'Juniores'),
            ('Carla Dias', date(2011, 3, 3), '', 'Adultos'),
        ]
        criados, atualizados, erros = process_alunos_import(dados)
        assert (criados, atualizados, erros) == (3, 0, [])
        assert Aluno.objects.count() == 3
        assert Classe.objects.count() == 2

    def test_rn08_caixa_e_espacos_nao_geram_duplicata(self):
        dados = [
            ('Ana Souza', date(2012, 1, 1), '', 'Juniores'),
            ('ana   SOUZA', date(2012, 1, 1), '', 'Juniores'),
        ]
        criados, atualizados, erros = process_alunos_import(dados)
        assert (criados, atualizados, erros) == (1, 1, [])


# =====================================================================
# RN-09 / RN-10 — Ranking
# =====================================================================


class TestRanking:
    def test_rn09_percentual_presentes_sobre_chamadas(
        self, classe, aluno_ativo, cliente_com_permissoes
    ):
        a1 = Aula.objects.create(
            data=date.today(), classe=classe, licao='L1'
        )
        a2 = Aula.objects.create(
            data=date.today() + timedelta(days=7), classe=classe, licao='L2'
        )
        _criar_presenca(a1, aluno_ativo, presente=True)
        _criar_presenca(a2, aluno_ativo, presente=False)

        client = cliente_com_permissoes('view_presenca')
        resp = client.get(
            reverse('core:relatorio_ranking'),
            {'inicio': a1.data.isoformat(), 'fim': a2.data.isoformat()},
        )
        [item] = resp.context['ranking_geral']
        assert item['total'] == 2
        assert item['presentes'] == 1
        assert item['ausentes'] == 1
        assert item['percentual'] == 50.0

    def test_rn10_periodo_janeiro_ate_hoje(self, classe, aluno_ativo, cliente_com_permissoes):
        hoje = date.today()
        _criar_presenca(
            Aula.objects.create(data=hoje, classe=classe, licao='L1'),
            aluno_ativo,
        )
        _criar_presenca(
            Aula.objects.create(
                data=date(hoje.year - 1, 7, 13), classe=classe, licao='L0'
            ),
            aluno_ativo,
        )

        client = cliente_com_permissoes('view_presenca')
        resp = client.get(
            reverse('core:relatorio_ranking'), {'ano': hoje.year}
        )
        assert len(resp.context['ranking_geral']) == 1
        assert resp.context['fim'] == hoje

        resp = client.get(
            reverse('core:relatorio_ranking'), {'ano': hoje.year - 1}
        )
        assert len(resp.context['ranking_geral']) == 1
        assert resp.context['fim'] == date(hoje.year - 1, 12, 31)

    def test_rn10_aula_futura_do_mesmo_ano_fica_fora(
        self, classe, aluno_ativo, cliente_com_permissoes
    ):
        hoje = date.today()
        futuro = date(hoje.year, 12, 28)
        if hoje >= futuro:
            pytest.skip('Hoje é dezembro; sem data futura útil no ano.')

        _criar_presenca(
            Aula.objects.create(data=futuro, classe=classe, licao='L futura'),
            aluno_ativo,
        )
        client = cliente_com_permissoes('view_presenca')
        resp = client.get(
            reverse('core:relatorio_ranking'), {'ano': hoje.year}
        )
        assert resp.context['ranking_geral'] == []

    def test_rn10_intervalo_invalido_fallback_para_ano(self, cliente_com_permissoes):
        client = cliente_com_permissoes('view_presenca')
        resp = client.get(
            reverse('core:relatorio_ranking'), {'inicio': '2026-01-01'}
        )
        assert resp.context['erro_periodo']
        assert resp.context['rotulo_periodo'] == str(resp.context['ano'])