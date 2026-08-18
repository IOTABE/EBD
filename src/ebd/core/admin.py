"""Registro dos modelos no Django Admin."""
from django.contrib import admin

from .models import Aula, Aluno, Auditoria, Classe, Presenca, Professor


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'telefone')
    search_fields = ('nome', 'email')
    readonly_fields = ('criado_por', 'atualizado_por')


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ('nome', 'faixa_etaria', 'lista_professores')
    filter_horizontal = ('professores',)
    search_fields = ('nome',)
    readonly_fields = ('criado_por', 'atualizado_por')

    @admin.display(description='Professores')
    def lista_professores(self, obj):
        return ', '.join(p.nome for p in obj.professores.all()) or '—'


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'classe', 'status', 'telefone')
    list_filter = ('status', 'classe')
    search_fields = ('nome',)
    list_editable = ('status',)
    readonly_fields = ('criado_por', 'atualizado_por')


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ('data', 'classe', 'licao')
    list_filter = ('classe', 'data')
    search_fields = ('licao',)
    readonly_fields = ('criado_por', 'atualizado_por')


@admin.register(Presenca)
class PresencaAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'aula', 'presente')
    list_filter = ('presente', 'aula__data', 'aula__classe')
    readonly_fields = ('criado_por', 'atualizado_por')


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('criado_em', 'usuario', 'modelo', 'objeto_id', 'acao', 'descricao')
    list_filter = ('acao', 'modelo', 'criado_em', 'usuario')
    search_fields = ('descricao', 'modelo')
    date_hierarchy = 'criado_em'
    readonly_fields = (
        'modelo', 'objeto_id', 'acao', 'usuario', 'descricao', 'dados', 'criado_em',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
