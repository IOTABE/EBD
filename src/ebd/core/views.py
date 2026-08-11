"""Views do sistema de gestão da EBD.

Inclui:
  * CRUD de Professores, Alunos, Classes e Aulas.
  * Chamada (regra de negócio de presença).
  * Relatório Geral Dominical e Relatório Mensal.
  * Dashboard com gráficos (Chart.js).
"""
import calendar
import json
from datetime import date

from django.contrib import messages
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from .forms import AulaForm, AlunoForm, ClasseForm, PresencaForm, ProfessorForm
from .models import Aula, Aluno, Classe, Presenca, Professor

# =====================================================================
# DASHBOARD
# =====================================================================


def dashboard(request):
    """Página inicial com gráficos de evolução mensal e assiduidade."""

    # -- Evolução da frequência mensal (todos os meses registrados) ------
    evolucao = (
        Presenca.objects
        .annotate(mes=TruncMonth('aula__data'))
        .values('mes')
        .annotate(
            presentes=Count('id', filter=Q(presente=True)),
            ausentes=Count('id', filter=Q(presente=False)),
        )
        .order_by('mes')
    )
    meses = [e['mes'].strftime('%m/%Y') for e in evolucao]
    presentes_mes = [e['presentes'] for e in evolucao]
    ausentes_mes = [e['ausentes'] for e in evolucao]

    # -- Percentual de assiduidade por classe ----------------------------
    por_classe = (
        Presenca.objects
        .values('aula__classe__nome')
        .annotate(total=Count('id'), presentes=Count('id', filter=Q(presente=True)))
        .order_by('aula__classe__nome')
    )
    classes_nomes = [c['aula__classe__nome'] for c in por_classe]
    percentuais = [
        round(c['presentes'] / c['total'] * 100, 1) if c['total'] else 0
        for c in por_classe
    ]

    context = {
        'meses': json.dumps(meses, ensure_ascii=False),
        'presentes_mes': json.dumps(presentes_mes),
        'ausentes_mes': json.dumps(ausentes_mes),
        'classes_nomes': json.dumps(classes_nomes, ensure_ascii=False),
        'percentuais': json.dumps(percentuais),
        'total_presencas': sum(presentes_mes),
        'total_ausencias': sum(ausentes_mes),
        'total_classes': Classe.objects.count(),
        'total_alunos_ativos': Aluno.objects.filter(status=Aluno.Status.ATIVO).count(),
    }
    return render(request, 'core/dashboard.html', context)


# =====================================================================
# CRUD — PROFESSORES
# =====================================================================


class ProfessorListView(ListView):
    model = Professor
    template_name = 'core/professor_list.html'
    context_object_name = 'professores'


class ProfessorCreateView(CreateView):
    model = Professor
    form_class = ProfessorForm
    template_name = 'core/professor_form.html'
    success_url = reverse_lazy('core:professor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Professor cadastrado com sucesso.')
        return super().form_valid(form)


class ProfessorUpdateView(UpdateView):
    model = Professor
    form_class = ProfessorForm
    template_name = 'core/professor_form.html'
    success_url = reverse_lazy('core:professor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Professor atualizado com sucesso.')
        return super().form_valid(form)


class ProfessorDeleteView(DeleteView):
    model = Professor
    template_name = 'core/professor_confirm_delete.html'
    success_url = reverse_lazy('core:professor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Professor removido com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CRUD — CLASSES
# =====================================================================


class ClasseListView(ListView):
    model = Classe
    template_name = 'core/classe_list.html'
    context_object_name = 'classes'
    # Número de alunos ativos por classe para exibir na listagem.
    queryset = Classe.objects.annotate(
        total_alunos=Count('alunos', filter=Q(alunos__status=Aluno.Status.ATIVO))
    )


class ClasseCreateView(CreateView):
    model = Classe
    form_class = ClasseForm
    template_name = 'core/classe_form.html'
    success_url = reverse_lazy('core:classe_list')

    def form_valid(self, form):
        messages.success(self.request, 'Classe cadastrada com sucesso.')
        return super().form_valid(form)


class ClasseUpdateView(UpdateView):
    model = Classe
    form_class = ClasseForm
    template_name = 'core/classe_form.html'
    success_url = reverse_lazy('core:classe_list')

    def form_valid(self, form):
        messages.success(self.request, 'Classe atualizada com sucesso.')
        return super().form_valid(form)


class ClasseDeleteView(DeleteView):
    model = Classe
    template_name = 'core/classe_confirm_delete.html'
    success_url = reverse_lazy('core:classe_list')

    def form_valid(self, form):
        messages.success(self.request, 'Classe removida com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CRUD — ALUNOS
# =====================================================================


class AlunoListView(ListView):
    model = Aluno
    template_name = 'core/aluno_list.html'
    context_object_name = 'alunos'
    queryset = Aluno.objects.select_related('classe')


class AlunoCreateView(CreateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'core/aluno_form.html'
    success_url = reverse_lazy('core:aluno_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aluno matriculado com sucesso.')
        return super().form_valid(form)


class AlunoUpdateView(UpdateView):
    model = Aluno
    form_class = AlunoForm
    template_name = 'core/aluno_form.html'
    success_url = reverse_lazy('core:aluno_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aluno atualizado com sucesso.')
        return super().form_valid(form)


class AlunoDeleteView(DeleteView):
    model = Aluno
    template_name = 'core/aluno_confirm_delete.html'
    success_url = reverse_lazy('core:aluno_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aluno removido com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CRUD — AULAS DOMINICAIS
# =====================================================================


class AulaListView(ListView):
    model = Aula
    template_name = 'core/aula_list.html'
    context_object_name = 'aulas'
    queryset = Aula.objects.select_related('classe').prefetch_related('presencas')


class AulaCreateView(CreateView):
    model = Aula
    form_class = AulaForm
    template_name = 'core/aula_form.html'
    success_url = reverse_lazy('core:aula_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aula registrada com sucesso.')
        return super().form_valid(form)


class AulaUpdateView(UpdateView):
    model = Aula
    form_class = AulaForm
    template_name = 'core/aula_form.html'
    success_url = reverse_lazy('core:aula_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aula atualizada com sucesso.')
        return super().form_valid(form)


class AulaDeleteView(DeleteView):
    model = Aula
    template_name = 'core/aula_confirm_delete.html'
    success_url = reverse_lazy('core:aula_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aula removida com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CHAMADA — REGRA DE NEGÓCIO DE PRESENÇA
# =====================================================================


def aula_chamada(request, pk):
    """Registra a chamada (presença) da aula dominical.

    REGRA OBRIGATÓRIA:
        Ao abrir a chamada, os registros de presença de TODOS os alunos
        ATIVOS da classe são criados/garantidos com ``presente=True``.
        A tela exibe todos os alunos marcados como PRESENTES; o usuário
        apenas desmarca os ausentes e salva.
    """
    aula = get_object_or_404(Aula.objects.select_related('classe'), pk=pk)

    # Garante uma linha de chamada para cada aluno ativo (padrão: presente).
    for aluno in aula.classe.alunos.filter(status=Aluno.Status.ATIVO):
        Presenca.objects.get_or_create(
            aula=aula, aluno=aluno, defaults={'presente': True}
        )

    presencas = aula.presencas.select_related('aluno').order_by('aluno__nome')

    ChamadaFormSet = inlineformset_factory(
        Aula, Presenca,
        form=PresencaForm,
        extra=0,          # sem linhas extras (a linha já existe por aluno)
        can_delete=False, # não permitir excluir linhas na chamada
    )

    if request.method == 'POST':
        formset = ChamadaFormSet(
            request.POST, instance=aula, queryset=presencas
        )
        if formset.is_valid():
            formset.save()
            presentes = sum(1 for f in formset.forms if f.instance.presente)
            messages.success(
                request,
                f'Chamada salva: {presentes} presente(s) e '
                f'{formset.total_form_count() - presentes} ausente(s).',
            )
            return redirect('core:aula_list')
    else:
        formset = ChamadaFormSet(instance=aula, queryset=presencas)

    context = {'aula': aula, 'formset': formset}
    return render(request, 'core/aula_chamada.html', context)


# =====================================================================
# RELATÓRIO GERAL DOMINICAL
# =====================================================================


def _parse_data(param):
    """Converte 'YYYY-MM-DD' em date; retorna hoje se inválido/vazio."""
    try:
        return date.fromisoformat(param) if param else date.today()
    except ValueError:
        return date.today()


def relatorio_dominical(request):
    """Soma de presenças e ausências por classe em um domingo selecionado."""
    data = _parse_data(request.GET.get('data'))

    aulas = (
        Aula.objects.filter(data=data)
        .select_related('classe')
        .annotate(
            total=Count('presencas'),
            presentes=Count('presencas', filter=Q(presencas__presente=True)),
            ausentes=Count('presencas', filter=Q(presencas__presente=False)),
            matriculados=Count(
                'classe__alunos',
                filter=Q(classe__alunos__status=Aluno.Status.ATIVO),
                distinct=True,
            ),
        )
        .order_by('classe__nome')
    )

    consolidado = Presenca.objects.filter(aula__data=data).aggregate(
        total=Count('id'),
        presentes=Count('id', filter=Q(presente=True)),
        ausentes=Count('id', filter=Q(presente=False)),
    )
    # Total de matriculados (ativos) das classes com aula no dia.
    consolidado['matriculados'] = sum(aula.matriculados for aula in aulas)

    context = {
        'data': data,
        'aulas': aulas,
        'consolidado': consolidado,
    }
    return render(request, 'core/relatorio_dominical.html', context)


# =====================================================================
# RELATÓRIO MENSAL
# =====================================================================


def _parse_ano_mes(request):
    """Retorna tupla (ano, mes) a partir da query string ou do mês atual."""
    hoje = date.today()
    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
    except ValueError:
        ano, mes = hoje.year, hoje.month
    if not 1 <= mes <= 12:
        mes = hoje.month
    return ano, mes


def relatorio_mensal(request):
    """Tabela dos 4/5 domingos do mês com totais de presença por classe.

    Linhas = domingos do mês; Colunas = classes + total do domingo.
    Rodapé = consolidado de cada classe no mês + total geral.
    """
    ano, mes = _parse_ano_mes(request)

    # Lista de todos os domingos do mês (normalmente 4 ou 5).
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    domingos = [
        date(ano, mes, dia)
        for dia in range(1, ultimo_dia + 1)
        if date(ano, mes, dia).weekday() == 6  # 6 = domingo
    ]

    classes = list(
        Classe.objects.order_by('nome').annotate(
            matriculados=Count('alunos', filter=Q(alunos__status=Aluno.Status.ATIVO))
        )
    )

    # Estruturas: dados[domingo][classe_id] = total de presentes.
    dados = {d: {c.id: 0 for c in classes} for d in domingos}
    totais_por_domingo = {d: 0 for d in domingos}
    totais_por_classe = {c.id: 0 for c in classes}

    presencas = Presenca.objects.filter(
        aula__data__year=ano, aula__data__month=mes, presente=True
    ).select_related('aula', 'aluno')

    for p in presencas:
        d = p.aula.data
        if d in dados and p.aula.classe_id in dados[d]:
            dados[d][p.aula.classe_id] += 1
            totais_por_domingo[d] += 1
            totais_por_classe[p.aula.classe_id] += 1

    total_geral = sum(totais_por_classe.values())
    total_matriculados = sum(c.matriculados for c in classes)

    # Estruturas alinhadas para iteração simples no template:
    # Tabela transposta: CLASSES nas linhas (vertical) e DOMINGOS nas colunas.
    # linhas_por_classe[classe] = {nome, matriculados, valores[por domingo], total}
    linhas_por_classe = [
        {
            'nome': c.nome,
            'matriculados': c.matriculados,
            'valores': [dados[d][c.id] for d in domingos],
            'total': totais_por_classe[c.id],
        }
        for c in classes
    ]
    totais_por_domingo_lista = [totais_por_domingo[d] for d in domingos]

    context = {
        'ano': ano,
        'mes': mes,
        'meses': [(m, calendar.month_name[m]) for m in range(1, 13)],
        'nome_mes': calendar.month_name[mes],
        'domingos': domingos,
        'linhas_por_classe': linhas_por_classe,
        'totais_por_domingo_lista': totais_por_domingo_lista,
        'total_geral': total_geral,
        'total_matriculados': total_matriculados,
    }
    return render(request, 'core/relatorio_mensal.html', context)
