"""Modelos do sistema de gestão da Escola Bíblica Dominical (EBD).

Entidades:
  * Professor — professores responsáveis pelas classes.
  * Classe     — turmas, com faixa etária e professor responsável.
  * Aluno      — alunos matriculados, vinculados a uma classe.
  * Aula       — aula dominical (data, classe, lição/tema, observações).
  * Presenca   — registro de chamada (presente/ausente) por aluno e aula.
"""
from django.db import models


class Professor(models.Model):
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


class Classe(models.Model):
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


class Aluno(models.Model):
    """Aluno matriculado na EBD, vinculado a uma classe."""

    class Status(models.TextChoices):
        ATIVO = 'ativo', 'Ativo'
        INATIVO = 'inativo', 'Inativo'

    nome = models.CharField('Nome', max_length=120)
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

    def __str__(self) -> str:
        return self.nome


class Aula(models.Model):
    """Aula dominical de uma classe em uma data específica."""

    data = models.DateField('Data')
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


class Presenca(models.Model):
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
        constraints = [
            # Impede duas linhas de chamada para o mesmo aluno na mesma aula.
            models.UniqueConstraint(
                fields=['aula', 'aluno'], name='presenca_unica_por_aula_aluno'
            ),
        ]

    def __str__(self) -> str:
        estado = 'presente' if self.presente else 'ausente'
        return f'{self.aluno.nome} — {estado} em {self.aula}'
