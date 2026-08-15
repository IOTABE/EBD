"""Registro dos modelos no Django Admin."""
from django.contrib import admin

from .models import Aula, Aluno, Classe, Presenca, Professor


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ('nome', 'email', 'telefone')
    search_fields = ('nome', 'email')


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ('nome', 'faixa_etaria', 'lista_professores')
    filter_horizontal = ('professores',)
    search_fields = ('nome',)

    @admin.display(description='Professores')
    def lista_professores(self, obj):
        return ', '.join(p.nome for p in obj.professores.all()) or '—'


@admin.register(Aluno)
class AlunoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'classe', 'status', 'telefone')
    list_filter = ('status', 'classe')
    search_fields = ('nome',)
    list_editable = ('status',)


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ('data', 'classe', 'licao')
    list_filter = ('classe', 'data')
    search_fields = ('licao',)


@admin.register(Presenca)
class PresencaAdmin(admin.ModelAdmin):
    list_display = ('aluno', 'aula', 'presente')
    list_filter = ('presente', 'aula__data', 'aula__classe')
