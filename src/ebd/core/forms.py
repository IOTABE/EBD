"""Formulários do sistema de gestão da EBD."""
from django import forms

from .models import Aula, Aluno, Classe, Presenca, Professor


class ProfessorForm(forms.ModelForm):
    class Meta:
        model = Professor
        fields = ['nome', 'email', 'telefone', 'data_nascimento']
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Nome completo'}),
            'email': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
            'telefone': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'data_nascimento': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
        }


class ClasseForm(forms.ModelForm):
    class Meta:
        model = Classe
        fields = ['nome', 'faixa_etaria', 'professor']
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Ex.: Juniores'}),
            'faixa_etaria': forms.TextInput(
                attrs={'placeholder': 'Ex.: 9 a 12 anos'}
            ),
        }


class AlunoForm(forms.ModelForm):
    class Meta:
        model = Aluno
        fields = ['nome', 'data_nascimento', 'telefone', 'status', 'classe']
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Nome completo'}),
            'telefone': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'data_nascimento': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
        }


class AulaForm(forms.ModelForm):
    class Meta:
        model = Aula
        fields = ['data', 'classe', 'licao', 'observacoes']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'licao': forms.TextInput(attrs={'placeholder': 'Ex.: Lição 10 — ...'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class PresencaForm(forms.ModelForm):
    """Formulário de uma linha de chamada (usado dentro do formset)."""

    class Meta:
        model = Presenca
        fields = ['presente']
        widgets = {
            # Caixa marcada por padrão = aluno presente. Desmarcar = ausente.
            'presente': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
