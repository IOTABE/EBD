"""Views do sistema de gestão da EBD.

Inclui:
  * CRUD de Professores, Alunos, Classes e Aulas.
  * Chamada (regra de negócio de presença).
  * Relatório Geral Dominical e Relatório Mensal.
  * Dashboard com gráficos (Chart.js).
"""
import calendar
import json
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import cache_page
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from .audit import registrar_manual
from .audit_context import auditoria_suprimida, get_current_user
from .forms import (
    AulaCreateForm, AulaForm, AlunoForm, ClasseForm, PresencaForm, ProfessorForm,
)
from .models import Aula, Aluno, Auditoria, Classe, Presenca, Professor

# =====================================================================
# PAGINAÇÃO REUTILIZÁVEL
# =====================================================================


def _opcoes_por_pagina(total, base=10):
    """Opções de registros por página: de ``base`` em ``base`` até o total."""
    if total <= 0:
        return [base]
    opcoes = list(range(base, total + 1, base))
    if not opcoes or opcoes[-1] < total:
        opcoes.append(total)
    return opcoes


def _por_pagina_selecionada(request, total, base=10):
    """Valida o valor do parâmetro ``por_pagina`` contra as opções disponíveis."""
    opcoes = _opcoes_por_pagina(total, base)
    try:
        valor = int(request.GET.get('por_pagina', opcoes[0]))
    except (TypeError, ValueError):
        return opcoes[0]
    return valor if valor in opcoes else opcoes[0]


class PaginacaoMixin:
    """ListView com paginação e seletor de itens por página.

    ``paginate_base`` define o tamanho inicial de cada página
    (padrão 10); pode ser sobrescrito nas views que usam o mixin.
    """

    paginate_base = 10

    def get_paginate_by(self, queryset):
        return _por_pagina_selecionada(
            self.request, queryset.count(), self.paginate_base
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paginator = context.get('paginator')
        total = paginator.count if paginator else 0
        context['por_pagina'] = _por_pagina_selecionada(
            self.request, total, self.paginate_base
        )
        context['opcoes_por_pagina'] = _opcoes_por_pagina(total, self.paginate_base)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['params'] = params.urlencode()
        return context


# =====================================================================
# DASHBOARD
# =====================================================================


@login_required
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


class ProfessorListView(PermissionRequiredMixin, PaginacaoMixin, ListView):
    permission_required = 'core.view_professor'
    model = Professor
    template_name = 'core/professor_list.html'
    context_object_name = 'professores'

    def get_queryset(self):
        qs = Professor.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(email__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        return context


class ProfessorCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'core.add_professor'
    model = Professor
    form_class = ProfessorForm
    template_name = 'core/professor_form.html'
    success_url = reverse_lazy('core:professor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Professor cadastrado com sucesso.')
        return super().form_valid(form)


class ProfessorUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'core.change_professor'
    model = Professor
    form_class = ProfessorForm
    template_name = 'core/professor_form.html'
    success_url = reverse_lazy('core:professor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Professor atualizado com sucesso.')
        return super().form_valid(form)


class ProfessorDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'core.delete_professor'
    model = Professor
    template_name = 'core/professor_confirm_delete.html'
    success_url = reverse_lazy('core:professor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Professor removido com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CRUD — CLASSES
# =====================================================================


class ClasseListView(PermissionRequiredMixin, PaginacaoMixin, ListView):
    permission_required = 'core.view_classe'
    model = Classe
    template_name = 'core/classe_list.html'
    context_object_name = 'classes'
    # Número de alunos ativos por classe para exibir na listagem.
    queryset = Classe.objects.prefetch_related('professores').order_by('nome').annotate(
        total_alunos=Count('alunos', filter=Q(alunos__status=Aluno.Status.ATIVO))
    )


class ClasseCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'core.add_classe'
    model = Classe
    form_class = ClasseForm
    template_name = 'core/classe_form.html'
    success_url = reverse_lazy('core:classe_list')

    def form_valid(self, form):
        messages.success(self.request, 'Classe cadastrada com sucesso.')
        return super().form_valid(form)


class ClasseUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'core.change_classe'
    model = Classe
    form_class = ClasseForm
    template_name = 'core/classe_form.html'
    success_url = reverse_lazy('core:classe_list')

    def form_valid(self, form):
        messages.success(self.request, 'Classe atualizada com sucesso.')
        return super().form_valid(form)


class ClasseDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'core.delete_classe'
    model = Classe
    template_name = 'core/classe_confirm_delete.html'
    success_url = reverse_lazy('core:classe_list')

    def form_valid(self, form):
        messages.success(self.request, 'Classe removida com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CRUD — ALUNOS
# =====================================================================


class AlunoListView(PermissionRequiredMixin, PaginacaoMixin, ListView):
    permission_required = 'core.view_aluno'
    model = Aluno
    template_name = 'core/aluno_list.html'
    context_object_name = 'alunos'

    def get_queryset(self):
        qs = Aluno.objects.select_related('classe')
        q = self.request.GET.get('q', '').strip()
        classe_id = self.request.GET.get('classe', '').strip()
        if q:
            qs = qs.filter(nome__icontains=q)
        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        context['classe_atual'] = self.request.GET.get('classe', '').strip()
        context['lista_classes'] = Classe.objects.order_by('nome')
        return context


class AlunoCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'core.add_aluno'
    model = Aluno
    form_class = AlunoForm
    template_name = 'core/aluno_form.html'
    success_url = reverse_lazy('core:aluno_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aluno matriculado com sucesso.')
        return super().form_valid(form)


class AlunoUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'core.change_aluno'
    model = Aluno
    form_class = AlunoForm
    template_name = 'core/aluno_form.html'
    success_url = reverse_lazy('core:aluno_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aluno atualizado com sucesso.')
        return super().form_valid(form)


class AlunoDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'core.delete_aluno'
    model = Aluno
    template_name = 'core/aluno_confirm_delete.html'
    success_url = reverse_lazy('core:aluno_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aluno removido com sucesso.')
        return super().form_valid(form)


import csv
from django.http import HttpResponse
from .utils import read_xlsx_rows_from_file, read_csv_rows_from_file, process_alunos_import


@login_required
@permission_required('core.view_aluno', raise_exception=True)
def aluno_export_view(request):
    """Exporta a lista completa de alunos para um arquivo CSV."""
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="alunos_ebd.csv"'

    writer = csv.writer(response)
    writer.writerow(['Nome', 'Classe', 'Telefone', 'Data de Nascimento', 'Status'])

    alunos = Aluno.objects.select_related('classe').order_by('nome')
    for aluno in alunos:
        nasc = aluno.data_nascimento.strftime('%d/%m/%Y') if aluno.data_nascimento else ''
        writer.writerow([
            aluno.nome,
            aluno.classe.nome if aluno.classe else '',
            aluno.telefone,
            nasc,
            aluno.get_status_display()
        ])

    return response


@login_required
@permission_required(['core.add_aluno', 'core.change_aluno'], raise_exception=True)
def aluno_import_view(request):
    """Permite o upload e importação de alunos via planilha (.xlsx ou .csv)."""
    if request.method == 'POST':
        arquivo = request.FILES.get('arquivo')
        if not arquivo:
            messages.error(request, 'Por favor, selecione um arquivo para importar.')
            return redirect('core:aluno_import')

        filename = arquivo.name.lower()
        try:
            if filename.endswith('.xlsx'):
                alunos_data, erros = read_xlsx_rows_from_file(arquivo)
            elif filename.endswith('.csv'):
                alunos_data, erros = read_csv_rows_from_file(arquivo)
            else:
                messages.error(request, 'Formato inválido. Por favor envie um arquivo .xlsx ou .csv.')
                return redirect('core:aluno_import')

            criados, atualizados, erros_processamento = process_alunos_import(alunos_data)
            erros = erros + erros_processamento

            if erros:
                return render(request, 'core/aluno_import.html', {
                    'criados': criados,
                    'atualizados': atualizados,
                    'total': len(alunos_data),
                    'erros': erros,
                })

            messages.success(
                request,
                f'Importação realizada com sucesso! Novos alunos: {criados}, Atualizados: {atualizados}, Total: {len(alunos_data)}'
            )
            return redirect('core:aluno_list')
        except Exception as e:
            messages.error(request, f'Erro ao processar planilha: {e}')
            return redirect('core:aluno_import')

    return render(request, 'core/aluno_import.html')



# =====================================================================
# CRUD — AULAS DOMINICAIS
# =====================================================================


class AulaListView(PermissionRequiredMixin, PaginacaoMixin, ListView):
    permission_required = 'core.view_aula'
    model = Aula
    template_name = 'core/aula_list.html'
    context_object_name = 'aulas'
    paginate_base = 6

    def get_queryset(self):
        qs = Aula.objects.select_related('classe').prefetch_related('presencas')
        data = self.request.GET.get('data', '').strip()
        classe_id = self.request.GET.get('classe', '').strip()
        if data:
            qs = qs.filter(data=data)
        if classe_id:
            qs = qs.filter(classe_id=classe_id)
        return qs.order_by('-data')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['data_atual'] = self.request.GET.get('data', '').strip()
        context['classe_atual'] = self.request.GET.get('classe', '').strip()
        context['lista_classes'] = Classe.objects.order_by('nome')
        return context


class AulaCreateView(PermissionRequiredMixin, CreateView):
    permission_required = 'core.add_aula'
    model = Aula
    form_class = AulaCreateForm
    template_name = 'core/aula_form.html'
    success_url = reverse_lazy('core:aula_list')

    def form_valid(self, form):
        data = form.cleaned_data['data']
        licao = form.cleaned_data['licao']
        observacoes = form.cleaned_data['observacoes']

        classes_com_aula = set(
            Aula.objects.filter(data=data).values_list('classe_id', flat=True)
        )
        criadas = 0
        ignoradas = 0
        for classe in Classe.objects.all():
            if classe.pk in classes_com_aula:
                ignoradas += 1
                continue
            Aula.objects.create(
                data=data, classe=classe, licao=licao, observacoes=observacoes,
            )
            criadas += 1

        if criadas:
            messages.success(
                self.request,
                f'{criadas} aula(s) criada(s) para {criadas} classe(s) em '
                f'{data.strftime("%d/%m/%Y")}.',
            )
        if ignoradas:
            messages.warning(
                self.request,
                f'{ignoradas} classe(s) já possuíam aula nesta data e foram '
                'ignoradas.',
            )
        if not criadas and not ignoradas:
            messages.warning(
                self.request, 'Nenhuma classe cadastrada para criar a aula.'
            )
        return redirect('core:aula_list')


class AulaUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = 'core.change_aula'
    model = Aula
    form_class = AulaForm
    template_name = 'core/aula_form.html'
    success_url = reverse_lazy('core:aula_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aula atualizada com sucesso.')
        return super().form_valid(form)


class AulaDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = 'core.delete_aula'
    model = Aula
    template_name = 'core/aula_confirm_delete.html'
    success_url = reverse_lazy('core:aula_list')

    def form_valid(self, form):
        messages.success(self.request, 'Aula removida com sucesso.')
        return super().form_valid(form)


# =====================================================================
# CHAMADA — REGRA DE NEGÓCIO DE PRESENÇA
# =====================================================================


@login_required
@permission_required(['core.add_presenca', 'core.change_presenca'], raise_exception=True)
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
    # Sinais de auditoria suprimidos: abrir a chamada apenas "garante" as
    # linhas; a edição consciente de dados é registrada uma única vez no save.
    with auditoria_suprimida():
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
            # Sinais de auditoria suprimidos: as linhas da chamada são
            # salvas em lote; um único resumo é registrado abaixo.
            with auditoria_suprimida():
                formset.save()
            presentes = sum(1 for f in formset.forms if f.instance.presente)
            ausentes = formset.total_form_count() - presentes
            registrar_manual(
                modelo='presenca',
                objeto_id=aula.pk,
                acao=Auditoria.Acao.EDITAR,
                usuario=get_current_user(),
                descricao=f'Chamada salva: {presentes} presente(s) e '
                          f'{ausentes} ausente(s).',
                dados={
                    'aula': str(aula),
                    'presentes': presentes,
                    'ausentes': ausentes,
                },
            )
            messages.success(
                request,
                f'Chamada salva: {presentes} presente(s) e '
                f'{ausentes} ausente(s).',
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


@login_required
@permission_required('core.view_presenca', raise_exception=True)
@cache_page(300)
def relatorio_dominical(request):
    """Soma de presenças e ausências por classe em um domingo selecionado."""
    data = _parse_data(request.GET.get('data'))

    aulas = (
        Aula.objects.filter(data=data)
        .select_related('classe')
        .prefetch_related('classe__professores')
        .annotate(
            total=Count('presencas', distinct=True),
            presentes=Count(
                'presencas', filter=Q(presencas__presente=True), distinct=True
            ),
            ausentes=Count(
                'presencas', filter=Q(presencas__presente=False), distinct=True
            ),
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
    # Percentual de presentes em relação ao total de matriculados.
    consolidado['percentual'] = (
        round(consolidado['presentes'] / consolidado['matriculados'] * 100, 1)
        if consolidado['matriculados'] else 0
    )

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


@login_required
@permission_required('core.view_presenca', raise_exception=True)
@cache_page(300)
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
    # Percentual de presentes por domingo em relação ao total de matriculados.
    percentuais_por_domingo = [
        round(t / total_matriculados * 100, 1) if total_matriculados else 0
        for t in totais_por_domingo_lista
    ]

    context = {
        'ano': ano,
        'mes': mes,
        'meses': [(m, calendar.month_name[m]) for m in range(1, 13)],
        'nome_mes': calendar.month_name[mes],
        'domingos': domingos,
        'linhas_por_classe': linhas_por_classe,
        'totais_por_domingo_lista': totais_por_domingo_lista,
        'percentuais_por_domingo': percentuais_por_domingo,
        'total_geral': total_geral,
        'total_matriculados': total_matriculados,
    }
    return render(request, 'core/relatorio_mensal.html', context)


# =====================================================================
# RANKING DE FREQUÊNCIA
# =====================================================================


@login_required
@permission_required('core.view_presenca', raise_exception=True)
@cache_page(300)
def relatorio_ranking(request):
    """Ranking geral e por classe do percentual de frequência.

    O período pode ser definido de duas formas:
      * `?ano=YYYY` — do início do ano até hoje (ou 31/12 em anos passados);
      * `?inicio=YYYY-MM-DD&fim=YYYY-MM-DD` — intervalo arbitrário.
    A frequência de cada aluno é calculada como o percentual de chamadas
    em que esteve presente em relação ao total de chamadas registradas
    para ele no período.
    """
    hoje = date.today()
    ano = hoje.year

    def _parse_data(raw):
        try:
            return datetime.strptime(raw, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    inicio_raw = request.GET.get('inicio')
    fim_raw = request.GET.get('fim')
    inicio = _parse_data(inicio_raw)
    fim = _parse_data(fim_raw)

    erro_periodo = None
    periodo_personalizado = False
    if inicio is not None or fim is not None:
        if inicio is None or fim is None or fim < inicio:
            erro_periodo = 'Intervalo de datas inválido — informe início e fim (início ≤ fim).'
            inicio = fim = None
        else:
            periodo_personalizado = True

    if inicio is None or fim is None:
        try:
            ano = int(request.GET.get('ano', hoje.year))
        except ValueError:
            ano = hoje.year
        inicio = date(ano, 1, 1)
        fim = min(hoje, date(ano, 12, 31))
        rotulo_periodo = str(ano)
    else:
        rotulo_periodo = f'{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}'

    presencas = (
        Presenca.objects.filter(aula__data__range=[inicio, fim])
        .values('aluno_id', 'aluno__nome', 'aluno__classe_id', 'aluno__classe__nome')
        .annotate(
            total=Count('id'),
            presentes=Count('id', filter=Q(presente=True)),
        )
    )

    ranking = []
    for p in presencas:
        total = p['total']
        presentes = p['presentes']
        ranking.append(
            {
                'aluno_id': p['aluno_id'],
                'nome': p['aluno__nome'],
                'classe_id': p['aluno__classe_id'],
                'classe': p['aluno__classe__nome'],
                'total': total,
                'presentes': presentes,
                'ausentes': total - presentes,
                'percentual': round(presentes / total * 100, 1) if total else 0,
            }
        )

    # Ranking geral: maior frequência primeiro; desempate por nome.
    ranking.sort(key=lambda item: (-item['percentual'], item['nome'].lower()))
    for posicao, item in enumerate(ranking, start=1):
        item['posicao'] = posicao

    # Ranking por classe: agrupa os mesmos itens, ordenados por frequência.
    por_classe = {}
    for item in ranking:
        por_classe.setdefault(item['classe'], []).append(item)
    ranking_por_classe = []
    for nome_classe in sorted(por_classe):
        alunos = por_classe[nome_classe]
        for posicao, item in enumerate(alunos, start=1):
            item['posicao_classe'] = posicao
        ranking_por_classe.append({'classe': nome_classe, 'alunos': alunos})

    context = {
        'ano': ano,
        'inicio': inicio,
        'fim': fim,
        'rotulo_periodo': rotulo_periodo,
        'erro_periodo': erro_periodo,
        'periodo_personalizado': periodo_personalizado,
        'ranking_geral': ranking,
        'ranking_por_classe': ranking_por_classe,
    }
    return render(request, 'core/relatorio_ranking.html', context)


# =====================================================================
# AUDITORIA
# =====================================================================


class AuditoriaListView(PermissionRequiredMixin, PaginacaoMixin, ListView):
    """Lista os registros da trilha de auditoria com filtros."""

    permission_required = 'core.view_auditoria'
    model = Auditoria
    template_name = 'core/auditoria_list.html'
    context_object_name = 'registros'

    def get_queryset(self):
        qs = Auditoria.objects.select_related('usuario')
        q = self.request.GET.get('q', '').strip()
        modelo = self.request.GET.get('modelo', '').strip()
        acao = self.request.GET.get('acao', '').strip()
        usuario_id = self.request.GET.get('usuario', '').strip()
        data_inicio = self.request.GET.get('data_inicio', '').strip()
        data_fim = self.request.GET.get('data_fim', '').strip()

        if q:
            qs = qs.filter(descricao__icontains=q)
        if modelo:
            qs = qs.filter(modelo=modelo)
        if acao:
            qs = qs.filter(acao=acao)
        if usuario_id:
            qs = qs.filter(usuario_id=usuario_id)
        if data_inicio:
            qs = qs.filter(criado_em__date__gte=data_inicio)
        if data_fim:
            qs = qs.filter(criado_em__date__lte=data_fim)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contexto = {
            c: self.request.GET.get(c, '').strip()
            for c in ('q', 'modelo', 'acao', 'usuario', 'data_inicio', 'data_fim')
        }
        context.update(contexto)
        context['acoes'] = Auditoria.Acao.choices
        context['modelos'] = (
            Auditoria.objects.order_by('modelo')
            .values_list('modelo', flat=True)
            .distinct()
        )
        context['lista_usuarios'] = get_user_model().objects.order_by('username')
        return context
