"""Contexto de auditoria por thread (usuário atual e supressão).

Este módulo NÃO importa modelos do app ``core`` para evitar importação
circular: ``audit.py`` e ``models.py`` dependem dele.
"""
import contextlib
import threading

_thread = threading.local()


def set_current_user(user) -> None:
    """Define o usuário atual da thread (None quando anônimo/fora de request)."""
    _thread.current_user = user


def get_current_user():
    """Retorna o usuário atual da thread, ou None quando não definido."""
    return getattr(_thread, 'current_user', None)


@contextlib.contextmanager
def auditoria_suprimida():
    """Suprime temporariamente a gravação de registros de auditoria.

    Usado em operações em lote (ex.: importação de planilha, chamada) para
    registrar um único resumo manual em vez de centenas de registros.
    """
    _thread.suprimida = True
    try:
        yield
    finally:
        _thread.suprimida = False


def auditoria_ativa() -> bool:
    """Retorna True quando a gravação de auditoria está habilitada."""
    return not getattr(_thread, 'suprimida', False)


class AuditMiddleware:
    """Define o usuário atual da thread a partir da requisição HTTP.

    Deve ser registrado no ``MIDDLEWARE`` depois de
    ``django.contrib.auth.middleware.AuthenticationMiddleware`` para que
    ``request.user`` já esteja populado.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        set_current_user(
            user if user is not None and user.is_authenticated else None
        )
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)