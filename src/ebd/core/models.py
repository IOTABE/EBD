"""Modelos do sistema de gestão da Escola Bíblica Dominical (EBD).

Entidades:
  * Professor — professores responsáveis pelas classes.
  * Classe     — turmas, com faixa etária e professor responsável.
  * Aluno      — alunos matriculados, vinculados a uma classe.
  * Aula       — aula dominical (data, classe, lição/tema, observações).
  * Presenca   — registro de chamada (presente/ausente) por aluno e aula.
"""
import re
import unicodedata

from django.conf import settings
from django.db import models

from .audit_context import get_current_user


def normalizar_nome(nome: str) -> str:
    """Normaliza um nome para identificação sem duplicatas.

    Remove acentos, colapsa espaços consecutivos e aplica ``casefold``
    (insensível a caixa e a variações de unicode).
    """
    if not nome:
        return ''
    s = unicodedata.normalize('NFKD', str(nome))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\s+', ' ', s)
    return s.strip().casefold()


class AuditMixin(models.Model):
    """Marca o responsável pela criação/atualização do registro.

    Os campos são preenchidos automaticamente pelo ``save()`` usando o
    usuário da requisição atual (definido pelo ``AuditMiddleware``).
    """

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Criado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Atualizado por',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        usuario = get_current_user()
        if self._state.adding or not self.pk:
            self.criado_por = usuario
        self.atualizado_por = usuario
        super().save(*args, **kwargs)


class Professor(AuditMixin):
    """Professor responsável por uma ou mais classes."""

    nome = models.CharField('Nome', max_length=120)
    email = models.EmailField('E-mail', max_length=150, blank=True)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    data_nascimento = models.DateField('Data de nascimento', null=True, blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Professor'
        verbose_name_plural = 'Professores'
        ordering = ['nome']

    def __str__(self) -> str:
        return self.nome


class Classe(AuditMixin):
    """Turma da EBD com faixa etária e até 4 professores."""

    MAX_PROFESSORES = 4

    nome = models.CharField('Nome da classe', max_length=120)
    faixa_etaria = models.CharField(
        'Faixa etária', max_length=100,
        help_text='Ex.: 3 a 5 anos, 13 a 17 anos, Adultos.'
    )
    professores = models.ManyToManyField(
        Professor, verbose_name='Professores',
        related_name='classes', blank=True,
        help_text=f'Selecione até {MAX_PROFESSORES} professores para a classe.',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Classe'
        verbose_name_plural = 'Classes'
        ordering = ['nome']

    def clean(self) -> None:
        """Garante que uma classe tenha no máximo ``MAX_PROFESSORES`` professores."""
        super().clean()
        if self.pk and self.professores.count() > self.MAX_PROFESSORES:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'professores': (
                    f'Uma classe pode ter no máximo {self.MAX_PROFESSORES} '
                    'professores.'
                ),
            })

    def __str__(self) -> str:
        return self.nome


class Aluno(AuditMixin):
    """Aluno matriculado na EBD, vinculado a uma classe."""

    class Status(models.TextChoices):
        ATIVO = 'ativo', 'Ativo'
        INATIVO = 'inativo', 'Inativo'

    nome = models.CharField('Nome', max_length=120)
    nome_normalizado = models.CharField(
        'Nome normalizado', max_length=120,
        editable=False, db_index=True,
        help_text='Nome sem acentos/caixa, usado para impedir duplicatas '
                  'na mesma classe.',
    )
    data_nascimento = models.DateField('Data de nascimento', null=True, blank=True)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    status = models.CharField(
        'Status', max_length=10, choices=Status.choices,
        default=Status.ATIVO,
        help_text='Alunos inativos não entram na chamada do dia.'
    )
    classe = models.ForeignKey(
        Classe, verbose_name='Classe', on_delete=models.PROTECT,
        related_name='alunos',
    )
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Aluno'
        verbose_name_plural = 'Alunos'
        ordering = ['nome']
        constraints = [
            # Um mesmo aluno (nome normalizado) só pode existir uma vez
            # na mesma classe — evita duplicatas em importações e cadastros.
            models.UniqueConstraint(
                fields=['nome_normalizado', 'classe'],
                name='aluno_unico_nome_normalizado_por_classe',
            ),
        ]

    def save(self, *args, **kwargs):
        self.nome_normalizado = normalizar_nome(self.nome)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.nome


class Aula(AuditMixin):
    """Aula dominical de uma classe em uma data específica."""

    data = models.DateField('Data', db_index=True)
    classe = models.ForeignKey(
        Classe, verbose_name='Classe', on_delete=models.CASCADE,
        related_name='aulas',
    )
    licao = models.CharField('Lição / Tema', max_length=200)
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Aula'
        verbose_name_plural = 'Aulas'
        ordering = ['-data']
        constraints = [
            # Uma única aula por classe e data (evita chamada duplicada).
            models.UniqueConstraint(
                fields=['data', 'classe'], name='aula_unica_por_classe_data'
            ),
        ]

    def __str__(self) -> str:
        return f'{self.classe.nome} — {self.data.strftime("%d/%m/%Y")} ({self.licao})'


class Presenca(AuditMixin):
    """Registro de chamada da aula dominical.

    REGRA DE NEGÓCIO OBRIGATÓRIA:
        Ao carregar a lista de alunos da classe para a chamada do dia,
        TODOS os alunos devem estar marcados como PRESENTES por padrão
        (``presente = True``). O usuário apenas desmarca os ausentes.
    """

    aula = models.ForeignKey(
        Aula, verbose_name='Aula', on_delete=models.CASCADE,
        related_name='presencas',
    )
    aluno = models.ForeignKey(
        Aluno, verbose_name='Aluno', on_delete=models.CASCADE,
        related_name='presencas',
    )
    presente = models.BooleanField('Presente', default=True)
    registrado_em = models.DateTimeField('Registrado em', auto_now=True)

    class Meta:
        verbose_name = 'Presença'
        verbose_name_plural = 'Presenças'
        ordering = ['aluno__nome']
        indexes = [
            # Relatórios filtram presenças por aula/data e presente/ausente.
            models.Index(fields=['aula', 'presente'], name='idx_presenca_aula_presente'),
        ]
        constraints = [
            # Impede duas linhas de chamada para o mesmo aluno na mesma aula.
            models.UniqueConstraint(
                fields=['aula', 'aluno'], name='presenca_unica_por_aula_aluno'
            ),
        ]

    def __str__(self) -> str:
        estado = 'presente' if self.presente else 'ausente'
        return f'{self.aluno.nome} — {estado} em {self.aula}'


class Auditoria(models.Model):
    """Registro da trilha de auditoria do sistema.

    Cada evento (criar/editar/excluir/login/logout/falha de login) gera um
    registro com descrição legível e, quando aplicável, um diff dos campos
    alterados em ``dados``.
    """

    class Acao(models.TextChoices):
        CRIAR = 'criar', 'Criar'
        EDITAR = 'editar', 'Editar'
        EXCLUIR = 'excluir', 'Excluir'
        LOGIN = 'login', 'Login'
        LOGOUT = 'logout', 'Logout'
        FALHA_LOGIN = 'falha_login', 'Falha de login'

    modelo = models.CharField('Modelo', max_length=100)
    objeto_id = models.PositiveBigIntegerField('ID do objeto', null=True, blank=True)
    acao = models.CharField(
        'Ação', max_length=20, choices=Acao.choices, default=Acao.EDITAR,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='Usuário',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    descricao = models.CharField('Descrição', max_length=255)
    dados = models.JSONField('Dados', default=dict)
    criado_em = models.DateTimeField('Criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'Registro de auditoria'
        verbose_name_plural = 'Registros de auditoria'
        ordering = ['-criado_em']

    def __str__(self) -> str:
        usuario = self.usuario.username if self.usuario else 'Sistema'
        return f'{self.criado_em:%d/%m/%Y %H:%M} — {self.acao} {self.modelo} — {usuario}'

    def resumo(self) -> str:
        """Texto legível dos dados capturados para exibição no template."""
        if self.acao == self.Acao.LOGIN:
            return f'Usuário {self.dados.get("usuario", self.usuario)} acessou o sistema.'
        if self.acao == self.Acao.LOGOUT:
            return f'Usuário {self.dados.get("usuario", self.usuario)} saiu do sistema.'
        if self.acao == self.Acao.FALHA_LOGIN:
            return f'Tentativa de login com usuário {self.dados.get("usuario", "desconhecido")} sem sucesso.'

        rotulo = f' {self.objeto_id}' if self.objeto_id else ''

        if self.acao == self.Acao.EXCLUIR:
            partes = self.dados.get('antes') or {}
            detalhe = ', '.join(
                f'{campo}: {valor}' for campo, valor in list(partes.items())[:5]
            )
            return f'{self.modelo}{rotulo} excluído(a){f" ({detalhe})" if detalhe else ""}.'

        if self.acao == self.Acao.CRIAR:
            partes = self.dados.get('depois') or {}
            detalhe = ', '.join(
                f'{campo}: {valor}' for campo, valor in list(partes.items())[:5]
            )
            return f'{self.modelo}{rotulo} criado(a){f" ({detalhe})" if detalhe else ""}.'

        if self.acao == self.Acao.EDITAR and self.modelo == 'Classe':
            professores = self.dados.get('professores') or []
            if professores:
                return f'Professores da classe atualizados: {", ".join(professores)}.'
            return f'Professores da classe removidos.'

        if self.acao == self.Acao.EDITAR:
            alteracoes = self.dados.get('antes') or {}
            partes = []
            for campo, (antes, depois) in list(alteracoes.items())[:5]:
                partes.append(f'{campo}: {antes} → {depois}')
            return f'{self.modelo}{rotulo} alterado(a){f" ({"; ".join(partes)})" if partes else ""}.'

        return self.descricao
