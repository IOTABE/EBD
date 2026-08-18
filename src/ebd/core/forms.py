"""Formulários do sistema de gestão da EBD."""
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Aula, Aluno, Classe, Presenca, Professor, normalizar_nome


class LoginForm(AuthenticationForm):
    """Login com estilo Bootstrap (usado na tela de acesso restrito)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'autofocus': True,
            'placeholder': 'Usuário',
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Senha',
        })


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
        fields = ['nome', 'faixa_etaria', 'professores']
        widgets = {
            'nome': forms.TextInput(attrs={'placeholder': 'Ex.: Juniores'}),
            'faixa_etaria': forms.TextInput(
                attrs={'placeholder': 'Ex.: 9 a 12 anos'}
            ),
            'professores': forms.SelectMultiple(
                attrs={'class': 'form-select', 'size': 8}
            ),
        }

    def clean_professores(self):
        professores = self.cleaned_data.get('professores')
        if len(professores) > Classe.MAX_PROFESSORES:
            raise forms.ValidationError(
                f'Uma classe pode ter no máximo {Classe.MAX_PROFESSORES} '
                'professores.'
            )
        return professores


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

    def clean(self):
        cleaned_data = super().clean()
        nome = cleaned_data.get('nome')
        classe = cleaned_data.get('classe')
        if nome and classe:
            duplicado = (
                Aluno.objects
                .filter(nome_normalizado=normalizar_nome(nome), classe=classe)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if duplicado:
                raise forms.ValidationError(
                    f'Já existe um aluno com o nome "{nome}" nesta classe.'
                )
        return cleaned_data


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
