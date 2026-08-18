"""Fixtures comuns da suíte de testes da EBD."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client


@pytest.fixture(autouse=True)
def _limpar_cache():
    """Limpa o cache entre testes para evitar respostas obsoletas.

    As views de relatório usam ``@cache_page`` (LocMemCache em memória);
    sem a limpeza, um teste poderia receber o HTML/JSON em cache de um
    teste anterior com a mesma URL.
    """
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def cliente_com_permissoes(db):
    """Factory que retorna um Client autenticado com as permissões indicadas.

    Exemplo de uso:
        client = cliente_com_permissoes('view_presenca', 'add_presenca')
        resp = client.get(reverse('core:relatorio_dominical'))
    """

    def _factory(*codenames):
        User = get_user_model()
        user = User.objects.create_user(
            username='test_user', password='testpass123'
        )
        if codenames:
            user.user_permissions.set(
                Permission.objects.filter(codename__in=codenames)
            )
        client = Client()
        client.force_login(user)
        return client

    return _factory