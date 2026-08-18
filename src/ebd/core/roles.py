"""Definição de papéis (grupos) e permissões do sistema EBD."""
from django.contrib.auth.models import Permission, Group

MODELOS = ('professor', 'classe', 'aluno', 'aula', 'presenca', 'auditoria')
MODELOS_CADASTRO = ('professor', 'classe', 'aluno', 'aula', 'presenca')
ACOES_CRUD = ('view', 'add', 'change', 'delete')

GRUPO_ADMINISTRADOR = 'Administrador'
GRUPO_SECRETARIA = 'Secretaria'
GRUPO_PROFESSOR = 'Professor'


def _perms(acoes, modelos):
    """Gera conjunto de codenames de permissão (ex.: 'view_professor')."""
    return {f'{acao}_{modelo}' for acao in acoes for modelo in modelos}


PERMISSOES_ADMINISTRADOR = _perms(ACOES_CRUD, MODELOS)
PERMISSOES_SECRETARIA = _perms(ACOES_CRUD, MODELOS_CADASTRO)
PERMISSOES_PROFESSOR = _perms(('view',), MODELOS_CADASTRO) | {
    'add_presenca',
    'change_presenca',
}

GRUPOS = [
    {'nome': GRUPO_ADMINISTRADOR, 'permissoes': PERMISSOES_ADMINISTRADOR},
    {'nome': GRUPO_SECRETARIA, 'permissoes': PERMISSOES_SECRETARIA},
    {'nome': GRUPO_PROFESSOR, 'permissoes': PERMISSOES_PROFESSOR},
]


def sincronizar_grupos():
    """Cria/atualiza os grupos com suas permissões de forma idempotente."""
    for grupo_def in GRUPOS:
        grupo, _ = Group.objects.get_or_create(name=grupo_def['nome'])
        permissoes = Permission.objects.filter(codename__in=grupo_def['permissoes'])
        grupo.permissions.set(permissoes)