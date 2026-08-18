"""Rotas do app core (módulo principal da EBD)."""
from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Professores
    path('professores/', views.ProfessorListView.as_view(), name='professor_list'),
    path('professores/novo/', views.ProfessorCreateView.as_view(), name='professor_create'),
    path('professores/<int:pk>/editar/', views.ProfessorUpdateView.as_view(), name='professor_update'),
    path('professores/<int:pk>/excluir/', views.ProfessorDeleteView.as_view(), name='professor_delete'),

    # Classes
    path('classes/', views.ClasseListView.as_view(), name='classe_list'),
    path('classes/nova/', views.ClasseCreateView.as_view(), name='classe_create'),
    path('classes/<int:pk>/editar/', views.ClasseUpdateView.as_view(), name='classe_update'),
    path('classes/<int:pk>/excluir/', views.ClasseDeleteView.as_view(), name='classe_delete'),

    # Alunos
    path('alunos/', views.AlunoListView.as_view(), name='aluno_list'),
    path('alunos/novo/', views.AlunoCreateView.as_view(), name='aluno_create'),
    path('alunos/importar/', views.aluno_import_view, name='aluno_import'),
    path('alunos/exportar/', views.aluno_export_view, name='aluno_export'),
    path('alunos/<int:pk>/editar/', views.AlunoUpdateView.as_view(), name='aluno_update'),
    path('alunos/<int:pk>/excluir/', views.AlunoDeleteView.as_view(), name='aluno_delete'),

    # Aulas Dominicals
    path('aulas/', views.AulaListView.as_view(), name='aula_list'),
    path('aulas/nova/', views.AulaCreateView.as_view(), name='aula_create'),
    path('aulas/<int:pk>/editar/', views.AulaUpdateView.as_view(), name='aula_update'),
    path('aulas/<int:pk>/excluir/', views.AulaDeleteView.as_view(), name='aula_delete'),
    path('aulas/<int:pk>/chamada/', views.aula_chamada, name='aula_chamada'),

    # Relatórios
    path('relatorios/dominical/', views.relatorio_dominical, name='relatorio_dominical'),
    path('relatorios/mensal/', views.relatorio_mensal, name='relatorio_mensal'),
    path('relatorios/ranking/', views.relatorio_ranking, name='relatorio_ranking'),

    # Auditoria
    path('auditoria/', views.AuditoriaListView.as_view(), name='auditoria_list'),
]
