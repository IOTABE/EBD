# EBD — Sistema de Gestão da Escola Bíblica Dominical

Aplicação web em **Django 6.1** para gerenciar a Escola Bíblica Dominical de uma igreja:
cadastro de professores, classes e alunos, chamada de presença dos domingos, relatórios
dominical e mensal, e dashboard com gráficos.

## Funcionalidades

- **Dashboard** — gráficos de evolução mensal (presentes/ausentes), assiduidade por
  classe (Chart.js) e totais gerais.
- **Professores** — cadastro, edição, exclusão e listagem.
- **Classes** — turmas com faixa etária e professor responsável; exibe o total de
  alunos ativos por classe.
- **Alunos** — cadastro com status **Ativo/Inativo**; alunos inativos **não entram** na
  chamada do dia.
- **Aulas & Chamada** — registro de aula dominical por classe/data e chamada de
  presença com a regra de negócio: **todos os alunos ativos ficam marcados como
  presentes por padrão**; o usuário apenas desmarca os ausentes.
- **Relatório Geral Dominical** — tabela por data (classe, matriculados, professor,
  presentes, ausentes, total e consolidado do dia).
- **Relatório Mensal** — tabela transposta: **classes nas linhas**, domingos do mês nas
  colunas, com coluna de matriculados, total por classe, total do dia e total geral.

## Stack

| Camada    | Tecnologia                                    |
|-----------|-----------------------------------------------|
| Backend   | Django 6.1 (Python ≥ 3.14)                     |
| Frontend  | Bootstrap 5.3.3, Chart.js 4.4.3 (via CDN)      |
| Banco     | SQLite3 (dev) / PostgreSQL (prod)              |
| Config    | `python-decouple` (.env) + `dj-database-url`   |
| Ambiente  | `uv` (gestor de dependências e virtualenv)     |

## Modelo de dados

- **Professor** — nome, e-mail, telefone, data de nascimento.
- **Classe** — nome, faixa etária, professor responsável (`SET_NULL`).
- **Aluno** — nome, data de nascimento, telefone, status (`ativo`/`inativo`), classe
  (`PROTECT`).
- **Aula** — data, classe, lição/tema, observações. Restrição:
  uma única aula por classe e data.
- **Presenca** — aula, aluno, `presente` (padrão `True`). Restrição:
  um único registro por aula e aluno.

Todos os modelos estão registrados no Django Admin.

## Estrutura do projeto

```
├── manage.py
├── pyproject.toml          # dependências (uv)
├── .env.example            # modelo das variáveis de ambiente
└── src/
    └── ebd/
        ├── settings.py     # SQLite (DEBUG=True) / PostgreSQL (DEBUG=False)
        ├── urls.py
        └── core/
            ├── models.py, views.py, forms.py, admin.py
            ├── urls.py     # rotas do app
            ├── migrations/
            ├── static/css/
            └── templates/
                ├── base.html
                └── core/   # CRUDs, chamada, dashboard e relatórios
```

## Configuração e execução (desenvolvimento)

Pré-requisitos: [uv](https://docs.astral.sh/uv/) e Python ≥ 3.14.

```bash
# 1. Instalar as dependências e criar o ambiente virtual
uv sync

# 2. Configurar as variáveis de ambiente
cp .env.example .env

# 3. Aplicar as migrações (cria o SQLite em db.sqlite3)
uv run python manage.py migrate

# 4. Criar o usuário administrador
uv run python manage.py createsuperuser

# 5. Subir o servidor de desenvolvimento
uv run python manage.py runserver
```

Acesse:

- Aplicação: <http://127.0.0.1:8000/>
- Admin: <http://127.0.0.1:8000/admin/>

> **Importante:** use sempre `uv run python manage.py ...`. Executar o `python` do
> sistema não encontra o app `ebd` (o pacote está em `src/`).

## Rotas principais

| Rota                          | Descrição                          |
|-------------------------------|------------------------------------|
| `/`                           | Dashboard                          |
| `/professores/`               | CRUD de professores                |
| `/classes/`                   | CRUD de classes                    |
| `/alunos/`                    | CRUD de alunos                     |
| `/aulas/`                     | CRUD de aulas                      |
| `/aulas/<id>/chamada/`        | Chamada de presença da aula        |
| `/relatorios/dominical/`      | Relatório geral dominical (por data) |
| `/relatorios/mensal/`         | Relatório mensal (por mês/ano)     |

## Variáveis de ambiente

| Variável        | Padrão                         | Descrição                                   |
|-----------------|--------------------------------|---------------------------------------------|
| `SECRET_KEY`    | `django-insecure-dev-only-change-me` | Chave secreta do Django (troque em produção) |
| `DEBUG`         | `True`                         | `True` usa SQLite; `False` usa PostgreSQL   |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1`          | Hosts permitidos (separados por vírgula)    |
| `DATABASE_URL`  | vazio (SQLite)                 | URL do PostgreSQL em produção               |

## Produção

1. Gere uma `SECRET_KEY` forte:
   `uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
2. Defina `DEBUG=False` e `ALLOWED_HOSTS` com o domínio real.
3. Informe `DATABASE_URL` apontando para o PostgreSQL.
4. Colete os arquivos estáticos: `uv run python manage.py collectstatic`.
5. Sirva com WSGI (`ebd.wsgi.application`), por exemplo Gunicorn atrás de um proxy
   reverso (Nginx/Caddy).

## Notas de negócio

- **Chamada**: ao abrir a chamada de uma aula, todos os alunos **ativos** da classe são
  marcados como presentes; basta desmarcar os ausentes antes de salvar.
- **Matriculados**: nos relatórios, a coluna "Matriculados" conta apenas os alunos com
  status **Ativo**.
