"""Testes de permissão (L2) — garantem que cada papel acessa apenas o permitido.

Cobre:
- Acesso anônimo → redirect para login (302)
- Usuário autenticado sem permissão → 403
- Cada papel (Administrador, Secretaria, Professor) acessa o que lhe cabe.
"""
import pytest
from django.urls import reverse
from django.test import Client

from ebd.core.models import Professor, Classe, Aluno, Aula, Presenca


pytestmark = pytest.mark.django_db


class TestPermissoesAnonimas:
    """Usuário não autenticado deve ser redirecionado para login em todas as views protegidas."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.professor = Professor.objects.create(nome='Prof. Teste')
        self.classe = Classe.objects.create(nome='Juniores', faixa_etaria='9 a 12 anos')
        self.classe.professores.add(self.professor)
        self.aluno = Aluno.objects.create(
            nome='Ana Souza', classe=self.classe, status=Aluno.Status.ATIVO
        )
        self.aula = Aula.objects.create(data='2026-01-01', classe=self.classe, licao='Lição 1')

    def test_dashboard_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:dashboard'))
        assert resp.status_code == 302
        assert '/accounts/login/' in resp.url

    def test_professor_list_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:professor_list'))
        assert resp.status_code == 302

    def test_classe_list_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:classe_list'))
        assert resp.status_code == 302

    def test_aluno_list_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:aluno_list'))
        assert resp.status_code == 302

    def test_aula_list_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:aula_list'))
        assert resp.status_code == 302

    def test_aula_chamada_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:aula_chamada', args=[self.aula.pk]))
        assert resp.status_code == 302

    def test_relatorio_dominical_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:relatorio_dominical'))
        assert resp.status_code == 302

    def test_relatorio_mensal_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:relatorio_mensal'))
        assert resp.status_code == 302

    def test_relatorio_ranking_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:relatorio_ranking'))
        assert resp.status_code == 302

    def test_auditoria_list_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:auditoria_list'))
        assert resp.status_code == 302

    def test_aluno_export_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:aluno_export'))
        assert resp.status_code == 302

    def test_aluno_import_anonimo_redirect(self):
        client = Client()
        resp = client.get(reverse('core:aluno_import'))
        assert resp.status_code == 302


class TestPermissoesPorPapel:
    """Cada papel (grupo) acessa apenas as views permitidas."""

    @pytest.fixture(autouse=True)
    def _setup(self, db):
        self.professor = Professor.objects.create(nome='Prof. Teste')
        self.classe = Classe.objects.create(nome='Juniores', faixa_etaria='9 a 12 anos')
        self.classe.professores.add(self.professor)
        self.aluno = Aluno.objects.create(
            nome='Ana Souza', classe=self.classe, status=Aluno.Status.ATIVO
        )
        self.aula = Aula.objects.create(data='2026-01-01', classe=self.classe, licao='Lição 1')
        _criar_presenca = lambda a, al, presente=True: Presenca.objects.create(aula=a, aluno=al, presente=presente)
        _criar_presenca(self.aula, self.aluno, presente=True)

    def _logar(self, *perms):
        """Cria usuário com as permissões dadas e retorna Client autenticado."""
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        User = get_user_model()
        user = User.objects.create_user(username=f'user_{len(perms)}', password='x')
        if perms:
            user.user_permissions.set(Permission.objects.filter(codename__in=perms))
        client = Client()
        client.force_login(user)
        return client

    # --- Administrador (todas as permissões) ---
    def test_administrador_acessa_tudo(self, cliente_com_permissoes):
        perms_admin = [
            'view_professor', 'add_professor', 'change_professor', 'delete_professor',
            'view_classe', 'add_classe', 'change_classe', 'delete_classe',
            'view_aluno', 'add_aluno', 'change_aluno', 'delete_aluno',
            'view_aula', 'add_aula', 'change_aula', 'delete_aula',
            'view_presenca', 'add_presenca', 'change_presenca', 'delete_presenca',
            'view_auditoria',
        ]
        client = cliente_com_permissoes(*perms_admin)

        urls_ok = [
            'core:dashboard',
            'core:professor_list',
            'core:classe_list',
            'core:aluno_list',
            'core:aula_list',
            'core:aula_chamada',
            'core:relatorio_dominical',
            'core:relatorio_mensal',
            'core:relatorio_ranking',
            'core:auditoria_list',
            'core:aluno_export',
            'core:aluno_import',
        ]
        for url_name in urls_ok:
            if url_name == 'core:aula_chamada':
                resp = client.get(reverse(url_name, args=[self.aula.pk]))
            else:
                resp = client.get(reverse(url_name))
            assert resp.status_code == 200, f'{url_name} falhou com {resp.status_code}'

    # --- Secretaria (cadastros + relatórios, sem auditoria) ---
    def test_secretaria_acessa_cadastros_e_relatorios(self, cliente_com_permissoes):
        perms_sec = [
            'view_professor', 'add_professor', 'change_professor', 'delete_professor',
            'view_classe', 'add_classe', 'change_classe', 'delete_classe',
            'view_aluno', 'add_aluno', 'change_aluno', 'delete_aluno',
            'view_aula', 'add_aula', 'change_aula', 'delete_aula',
            'view_presenca',
        ]
        client = cliente_com_permissoes(*perms_sec)

        # Deve acessar cadastros
        for url_name in [
            'core:dashboard',
            'core:professor_list', 'core:classe_list', 'core:aluno_list', 'core:aula_list',
            'core:relatorio_dominical', 'core:relatorio_mensal', 'core:relatorio_ranking',
            'core:aluno_export', 'core:aluno_import',
        ]:
            resp = client.get(reverse(url_name))
            assert resp.status_code == 200, f'{url_name} falhou com {resp.status_code}'

        # NÃO deve acessar auditoria
        resp = client.get(reverse('core:auditoria_list'))
        assert resp.status_code == 403

        # NÃO deve acessar chamada (precisa add/change presenca)
        resp = client.get(reverse('core:aula_chamada', args=[self.aula.pk]))
        assert resp.status_code == 403

    # --- Professor (view cadastros + chamada, sem delete/add cadastros, sem auditoria) ---
    def test_professor_acessa_view_e_chamada(self, cliente_com_permissoes):
        perms_prof = [
            'view_professor', 'view_classe', 'view_aluno', 'view_aula', 'view_presenca',
            'add_presenca', 'change_presenca',
        ]
        client = cliente_com_permissoes(*perms_prof)

        # Deve acessar views de leitura
        for url_name in [
            'core:dashboard',
            'core:professor_list', 'core:classe_list', 'core:aluno_list', 'core:aula_list',
            'core:relatorio_dominical', 'core:relatorio_mensal', 'core:relatorio_ranking',
            'core:aula_chamada',
        ]:
            if url_name == 'core:aula_chamada':
                resp = client.get(reverse(url_name, args=[self.aula.pk]))
            else:
                resp = client.get(reverse(url_name))
            assert resp.status_code == 200, f'{url_name} falhou com {resp.status_code}'

        # NÃO deve acessar auditoria
        resp = client.get(reverse('core:auditoria_list'))
        assert resp.status_code == 403

        # NÃO deve acessar add/change/delete de cadastros (sem permissão)
        for url_name in [
            'core:professor_create', 'core:classe_create', 'core:aluno_create', 'core:aula_create',
        ]:
            resp = client.get(reverse(url_name))
            assert resp.status_code == 403, f'{url_name} deveria ser 403'

        # NÃO deve acessar import de alunos (precisa add/change aluno)
        # Export é permitido pois professor tem view_aluno
        resp = client.get(reverse('core:aluno_export'))
        assert resp.status_code == 200, 'aluno_export deveria ser 200 para professor'
        resp = client.get(reverse('core:aluno_import'))
        assert resp.status_code == 403