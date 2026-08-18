"""Gravação de trilha de auditoria (audit log) para os modelos da EBD.

Conecta sinais do Django aos modelos auditados e fornece ``registrar_manual``
para operações que não passam pelos sinais (ex.: chamada, importação).
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed,
)
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save

from .audit_context import auditoria_ativa, get_current_user
from .models import Aluno, Aula, Classe, Presenca, Professor


_MODELOS_AUDITADOS = (Professor, Classe, Aluno, Aula, Presenca)

# Campos gerenciados pelo próprio sistema e que não devem aparecer no diff.
_CAMPOS_IGNORADOS = {
    'id',
    'criado_por_id',
    'atualizado_por_id',
    'criado_em',
    'atualizado_em',
    'registrado_em',
}


def _serializar(valor):
    """Converte valores não serializáveis (datas, decimais, UUID) para str."""
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, (Decimal, UUID)):
        return str(valor)
    return valor


def _snapshot(instancia) -> dict:
    """Captura o estado atual de uma instância como dict de campos legíveis."""
    dados = {}
    for campo in instancia._meta.fields:
        if campo.auto_created or campo.attname in _CAMPOS_IGNORADOS:
            continue
        valor = getattr(instancia, campo.attname, None)
        dados[campo.attname] = _serializar(valor)
    return dados


def _snapshot_anterior(instancia) -> dict:
    """Recupera do banco o estado anterior da instância (usado no pre_save)."""
    if not instancia.pk:
        return {}
    try:
        anterior = type(instancia).objects.get(pk=instancia.pk)
    except type(instancia).DoesNotExist:
        return {}
    return _snapshot(anterior)


def _registrar(*, modelo, objeto_id=None, acao, usuario=None,
               descricao='', dados=None) -> None:
    """Grava um registro de auditoria se a auditoria estiver ativa."""
    if not auditoria_ativa():
        return
    from .models import Auditoria
    Auditoria.objects.create(
        modelo=modelo,
        objeto_id=objeto_id,
        acao=acao,
        usuario=usuario,
        descricao=descricao,
        dados=dados or {},
    )


def registrar_manual(*, modelo, objeto_id=None, acao='editar', usuario=None,
                     descricao='', dados=None) -> None:
    """Registra manualmente um evento de auditoria (operações em lote)."""
    _registrar(
        modelo=modelo, objeto_id=objeto_id, acao=acao,
        usuario=usuario, descricao=descricao, dados=dados,
    )


def _pre_save(sender, instance, **kwargs):
    instance._estado_anterior = _snapshot_anterior(instance)


def _post_save(sender, instance, created, **kwargs):
    if not auditoria_ativa():
        return
    nome = type(instance).__name__
    usuario = get_current_user()
    if created:
        _registrar(
            modelo=nome, objeto_id=instance.pk, acao='criar',
            usuario=usuario, descricao=f'{nome} criado(a)',
            dados={'depois': _snapshot(instance)},
        )
        return
    antes = getattr(instance, '_estado_anterior', {})
    depois = _snapshot(instance)
    alteracoes = {
        campo: (antes.get(campo), depois.get(campo))
        for campo in depois
        if antes.get(campo) != depois.get(campo)
    }
    if alteracoes:
        _registrar(
            modelo=nome, objeto_id=instance.pk, acao='editar',
            usuario=usuario, descricao=f'{nome} alterado(a)',
            dados={'antes': alteracoes},
        )


def _post_delete(sender, instance, **kwargs):
    if not auditoria_ativa():
        return
    nome = type(instance).__name__
    _registrar(
        modelo=nome, objeto_id=instance.pk, acao='excluir',
        usuario=get_current_user(), descricao=f'{nome} excluído(a)',
        dados={'antes': _snapshot(instance)},
    )


def _m2m_professores(sender, instance, action, **kwargs):
    if not auditoria_ativa():
        return
    if action in ('post_add', 'post_remove', 'post_clear'):
        _registrar(
            modelo='Classe', objeto_id=instance.pk, acao='editar',
            usuario=get_current_user(),
            descricao='Professores atualizados na classe',
            dados={'professores': list(instance.professores.values_list('nome', flat=True))},
        )


def _registro_login(sender, user, request, **kwargs):
    _registrar(
        modelo='User', acao='login', usuario=user,
        descricao=f'Login de {user.username}',
        dados={'usuario': user.username},
    )


def _registro_logout(sender, user, request, **kwargs):
    _registrar(
        modelo='User', acao='logout', usuario=user,
        descricao=f'Logout de {user.username}',
        dados={'usuario': user.username},
    )


def _registro_falha_login(sender, credentials, request, **kwargs):
    _registrar(
        modelo='User', acao='falha_login',
        descricao='Tentativa de login sem sucesso',
        dados={'usuario': credentials.get('username', '')},
    )


def conectar_sinais() -> None:
    """Conecta os sinais de auditoria (chamado pelo ``ready()`` do app)."""
    for modelo in _MODELOS_AUDITADOS:
        nome = modelo.__name__
        pre_save.connect(_pre_save, sender=modelo, dispatch_uid=f'auditoria_pre_save_{nome}')
        post_save.connect(_post_save, sender=modelo, dispatch_uid=f'auditoria_post_save_{nome}')
        post_delete.connect(_post_delete, sender=modelo, dispatch_uid=f'auditoria_post_delete_{nome}')

    m2m_changed.connect(
        _m2m_professores, sender=Classe.professores.through,
        dispatch_uid='auditoria_m2m_professores',
    )

    User = get_user_model()
    user_logged_in.connect(_registro_login, sender=User,
                           dispatch_uid='auditoria_user_logged_in')
    user_logged_out.connect(_registro_logout, sender=User,
                            dispatch_uid='auditoria_user_logged_out')
    user_login_failed.connect(_registro_falha_login, dispatch_uid='auditoria_user_login_failed')