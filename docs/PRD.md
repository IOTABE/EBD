# PRD — Sistema de Gestão da Escola Bíblica Dominical (EBD)

- **Versão do documento:** 1.1
- **Status:** Documentação do sistema atual (as-built)
- **Público:** Desenvolvedores
- **Repositório:** `/home/gti/Develop/EBD`
- **Última atualização:** 2026-08-18

---

## 1. Visão geral

Aplicação web em **Django 6.1** para gerenciar a Escola Bíblica Dominical de uma
igreja. Permite o cadastro de professores, classes e alunos, o registro da chamada
de presença dos domingos, a importação/exportação de alunos via planilha, relatórios
dominical/mensal e ranking de frequência, além de um dashboard com gráficos.

O sistema opera em um fluxo anual: **matrícula → cadastro → chamada dominical →
relatórios de frequência** para acompanhamento e premiação de assiduidade.

## 2. Objetivos

| Objetivo | Descrição |
|----------|-----------|
| **O1** | Digitalizar o cadastro de alunos, classes e professores da EBD. |
| **O2** | Agilizar a chamada de presença dominical (padrão: todos presentes). |
| **O3** | Gerar relatórios de frequência (dominical, mensal e ranking anual) sem planilhas manuais. |
| **O4** | Permitir migração de dados pré-existentes via importação `.xlsx`/`.csv`. |
| **O5** | Centralizar a gestão para acesso de usuários autenticados. |

**Não objetivos (fora do escopo atual):**
- Aplicativo móvel nativo (a interface é web responsiva).
- Notificações/lembretes automáticos (e-mail, SMS ou WhatsApp).
- Pagamento de matrícula ou integração financeira.
- Multi-igreja / multi-tenant.
- Permissões granulares por papel (apenas autenticação simples).

## 3. Usuários e personas

| Persona | Perfil | Necessidades |
|---------|--------|--------------|
| **Secretário(a) da EBD** | Responsável por cadastros e relatórios | Importar matrículas, manter cadastro, gerar relatórios e ranking |
| **Superintendente** | Acompanha a frequência da escola | Dashboard, relatórios mensais e ranking |
| **Professor(a)** | Registra a chamada da sua classe | Chamada rápida por data/classe |
| **Administrador (Django Admin)** | Gestão técnica e dados | CRUD completo, correções de dados |

O acesso é feito com **autenticação por usuário/senha** (Django auth). Não há
distinção de perfil entre as personas — todas logam e enxergam as mesmas telas.

## 4. Stack técnica

| Camada | Tecnologia | Observação |
|--------|-----------|------------|
| Backend | Django 6.1 (Python ≥ 3.14) | Estrutura `src/ebd` |
| Frontend | Bootstrap 5.3.3 + Chart.js 4.4.3 | Via CDN, templates Django |
| Banco de dados | SQLite3 (dev) / PostgreSQL (prod) | Seleção via `DEBUG` |
| Configuração | `python-decouple` (`.env`) + `dj-database-url` | |
| Gerenciador de pacotes | `uv` | `pyproject.toml` + `uv.lock` |
| Servidor (prod) | Gunicorn (WSGI) | Atrás de proxy reverso (Nginx/Caddy) |
| Deploy | GitHub Actions (`deploy.yaml`) | Push na branch `main` |

## 5. Arquitetura

Arquitetura **monolítica** Django clássica (MTV) com um único app `core`:

```
├── manage.py
├── pyproject.toml / uv.lock / requirements.txt
├── .env.example
├── .github/deploy.yaml
└── src/ebd/
    ├── settings.py        # SQLite (DEBUG=True) / PostgreSQL (DEBUG=False)
    ├── urls.py            # rotas raiz: admin, login, auth, core
    ├── wsgi.py / asgi.py
    └── core/
        ├── models.py      # Professor, Classe, Aluno, Aula, Presenca, Auditoria
        ├── audit.py       # sinais de auditoria + registrar_manual
        ├── audit_context.py # usuário atual (thread-local) + AuditoriaMiddleware
        ├── views.py       # CRUDs, chamada, relatórios, dashboard, import/export, auditoria
        ├── forms.py       # formulários + LoginForm (Bootstrap)
        ├── admin.py       # registro no Django Admin
        ├── utils.py       # leitura .xlsx/.csv, parsing de data/telefone
        ├── urls.py        # rotas do app (namespace `core`)
        ├── management/commands/importar_alunos.py
        ├── migrations/
        ├── static/css/
        └── templates/
            ├── base.html
            ├── registration/login.html
            └── core/      # listas, formulários, confirmações, chamada,
                           # dashboard, relatórios, paginação
```

### Fluxos principais

```
1. Cadastro: Professor/Classe → Aluno (vínculo FK com classe)
2. Importação: planilha .xlsx/.csv → (get_or_create Classe) → update_or_create Aluno
3. Chamada: Aula (data+classe) → get_or_create Presenca (presente=True) p/ alunos ativos
           → formset de checkboxes → salvar
4. Relatórios: agregações de Presenca por data/mês/ano
```

### Padrões de código relevantes

- **Views baseadas em classe** para CRUDs (`LoginRequiredMixin`), exceto aulas.
- **`PaginacaoMixin`** reutilizável com seletor de registros por página (múltiplos de 10).
- **Busca/filtro** via query string (`q`, `classe`, `data`, `ano`, `mes`).
- **Restrições de integridade no banco** via `UniqueConstraint` (aula e presença).
- **Regras de negócio** protegidas em `model.clean()` e em `forms.clean_*`.

## 6. Modelo de dados

| Modelo | Campos principais | Relacionamentos | Restrições |
|--------|-------------------|-----------------|------------|
| **Professor** | nome, email, telefone, data_nascimento, criado_em | M2M → Classe | — |
| **Classe** | nome, faixa_etaria, professores, criado_em | M2M ← Professor; 1:N ← Aluno; 1:N ← Aula | Máx. 4 professores |
| **Aluno** | nome, data_nascimento, telefone, status (`ativo`/`inativo`), classe, criado_em | FK → Classe (`PROTECT`) | — |
| **Aula** | data, classe, licao, observacoes, criado_em | FK → Classe (`CASCADE`) | Única aula por (classe, data) |
| **Presenca** | aula, aluno, presente (`default=True`), registrado_em | FK → Aula, FK → Aluno (ambos `CASCADE`) | Único registro por (aula, aluno) |
| **Auditoria** | modelo, objeto_id, acao (`criar`/`editar`/`excluir`/`login`/`logout`/`falha_login`), usuario, descricao, dados (JSON), criado_em | FK → User (`SET_NULL`) | Read-only no Admin e na tela `/auditoria/` |

### Notas de integridade

- `Aluno.classe` usa `on_delete=PROTECT` — não é possível excluir uma classe com alunos.
- `Aula.classe` e `Presenca.*` usam `CASCADE` — excluir aula/do aluno remove as presenças.
- `Classe.MAX_PROFESSORES = 4`, validado em `Classe.clean()` e `ClasseForm.clean_professores()`.
- Todos os modelos de negócio herdam `AuditMixin` → campos `criado_por`/`atualizado_por` (FK usuário, read-only no Admin).
- Toda operação relevante gera registro em **`Auditoria`** via sinais do Django (`audit.py`); importação de planilha e chamada geram um resumo único via `registrar_manual`.

## 7. Requisitos funcionais

### RF-01 — Autenticação
- Login com usuário/senha (Django auth), template Bootstrap (`LoginForm`).
- Rotas de logout e demais `django.contrib.auth.urls` sob `/accounts/`.
- Telas dos módulos protegidas por `login_required` (via decorator ou `LoginRequiredMixin`).
  > **Inconsistência conhecida:** as views de **Aula** (listar/criar/editar/excluir) **não** exigem login, embora a chamada (`aula_chamada`) exija.

### RF-02 — Dashboard (`/`)
- Gráfico de evolução mensal de presentes/ausentes (Chart.js) — `TruncMonth` sobre `aula__data`.
- Gráfico de percentual de assiduidade por classe.
- Totais gerais: presenças, ausências, classes e alunos ativos.

### RF-03 — CRUD Professores
- Listagem com busca por nome/e-mail + paginação.
- Criar/editar/excluir (exclusão com confirmação).

### RF-04 — CRUD Classes
- Listagem com **total de alunos ativos** por classe (`annotate(Count)`).
- Criar/editar/excluir; seleção de **até 4 professores** (`SelectMultiple`).
- Exclusão bloqueada se houver alunos (`PROTECT`).

### RF-05 — CRUD Alunos
- Listagem com busca por nome + filtro por classe + paginação.
- Cadastro com status **Ativo/Inativo** (padrão Ativo).
- Exportação CSV (`alunos_ebd.csv`, charset `utf-8-sig`).
- Importação via planilha `.xlsx`/`.csv` (tela + comando CLI).

### RF-06 — CRUD Aulas
- Listagem com filtro por data e por classe + paginação (base 6).
- Criar/editar/excluir; restrição de **uma aula por classe/data**.

### RF-07 — Chamada de presença
- Ao abrir a chamada de uma aula, são criados registros `Presenca` para **todos os alunos ativos** da classe, com `presente=True`.
- Interface: checkbox marcado = presente; desmarcar = ausente.
- Salvar atualiza o formset; feedback de quantos presentes/ausentes.

### RF-08 — Relatório Geral Dominical
- Filtro por data (padrão: hoje).
- Por classe: matriculados (ativos), professores, presentes, ausentes, total.
- Consolidado do dia + **percentual de presentes sobre matriculados**.

### RF-09 — Relatório Mensal
- Filtro por mês/ano (padrão: mês corrente).
- Lista os domingos do mês (4 ou 5).
- **Tabela transposta:** classes nas linhas, domingos nas colunas.
- Rodapé: total por classe, total por domingo, percentual por domingo, total geral e total de matriculados.

### RF-10 — Ranking de frequência
- Filtro por ano (padrão: corrente); período de 01/01 até hoje (ou 31/12 em anos passados).
- **Ranking geral** e **ranking por classe** do percentual de presença.
- Desempate por nome; posição numerada.

### RF-11 — Importação/Exportação de alunos
- Formatos suportados: `.xlsx` (leitura via XML/ZipFile, sem biblioteca externa) e `.csv`.
- Colunas esperadas (índice 0-based): `[0]=timestamp, [1]=nome, [2]=?, [3]=nascimento, [4]=telefone, [5]=classe`.
- Normalizações: nome de classe com acentuação (`CLASS_NAME_MAP`), data serial do Excel ou texto, telefone formatado.
- `Classe` criada automaticamente com `faixa_etaria='A definir'` se não existir.
- `Aluno` via `update_or_create(nome, classe)` — mesmo nome+classe atualiza (status volta a Ativo).
- Comando CLI: `uv run python manage.py importar_alunos [caminho]`.

### RF-12 — Django Admin
- Todos os modelos registrados com `list_display`, `list_filter`, `search_fields`.
- `AlunoAdmin.list_editable = ('status',)` — troca rápida de status.
- Campos `criado_por`/`atualizado_por` como `readonly_fields`.

### RF-13 — Auditoria
- Registro automático (sinais) de criação, edição e exclusão de **Professor, Classe, Aluno, Aula, Presenca**, incluindo alteração de vínculo de professores da classe (M2M) — com diff `antes → depois` no `resumo()`.
- Auditoria de **login, logout e falha de login** via sinais do Django auth.
- Operações em lote (importação de planilha e chamada de presença) geram **um** registro consolidado por operação (evita ruído).
- Tela `/auditoria/` (login obrigatório) com filtros por busca na descrição, modelo, ação, usuário e intervalo de datas + paginação.
- Registro **read-only** (`AuditoriaAdmin`): sem add/change/delete.

## 8. Regras de negócio

| # | Regra | Implementação |
|---|-------|---------------|
| RN-01 | Chamada parte com **todos os ativos presentes** | `get_or_create(presente=True)` em `aula_chamada` |
| RN-02 | Alunos **inativos** não entram na chamada | Filtro `status=ATIVO` em `aula_chamada` |
| RN-03 | **Matriculados** = alunos ativos (relatórios e listagem) | `Count(..., filter=Q(status=ATIVO))` |
| RN-04 | Uma aula por classe e data | `UniqueConstraint` |
| RN-05 | Uma presença por aluno e aula | `UniqueConstraint` |
| RN-06 | Classe com no máximo 4 professores | `clean()` + validação do form |
| RN-07 | Classe não pode ser excluída com alunos | `on_delete=PROTECT` |
| RN-08 | Importação: mesma (nome, classe) atualiza; diferente, cria | `update_or_create` |
| RN-09 | Percentuais: presentes / matriculados (relatórios) e presentes / chamadas (ranking) | `views.py` |
| RN-10 | Período do ranking: 01/01 → hoje (ou 31/12) do ano selecionado | `views.relatorio_ranking` |

## 9. Requisitos não funcionais

| Categoria | Requisito |
|-----------|-----------|
| **Desempenho** | Consultas de relatórios usam `select_related`/`prefetch_related`/`annotate` para evitar N+1 |
| **Segurança** | Login obrigatório na maioria dos módulos; CSRF ativo; headers de segurança em produção |
| **HTTPS (prod)** | `SECURE_SSL_REDIRECT`, HSTS, cookies `Secure`, `X_FRAME_OPTIONS=DENY` |
| **i18n/l10n** | `pt-br`, fuso `America/Sao_Paulo` |
| **Portabilidade BD** | SQLite (dev) ↔ PostgreSQL (prod) sem dependências de engine no código |
| **Deploy** | Automático via GitHub Actions ao fazer push em `main` |
| **Responsividade** | Bootstrap 5 — interface adaptável a telas menores |

## 10. Segurança

- Validação de formulários nativa do Django (CSRF + sanitização).
- `SECRET_KEY` fora do repositório (via `.env`).
- Em produção: `DEBUG=False`, `ALLOWED_HOSTS` restrito, HTTPS forçado.
- **Riscos/limitações atuais:**
  - Views de **Aula** sem `LoginRequired` (falha de autorização).
  - A importação trata exceções de forma ampla (`except Exception`), sem log estruturado.
  - Não há rate limiting no login nem bloqueio por tentativas.
  - Não há diferenciação de permissões entre usuários (qualquer logado acessa tudo).
  - O pipeline de deploy executa `git pull` + `pip install` via SSH sem validação/rollback automatizado.

## 11. Rotas (endpoints)

| Rota | View | Nome |
|------|------|------|
| `/` | `dashboard` | `core:dashboard` |
| `/accounts/login/` | `LoginView` | `login` |
| `/accounts/...` | `django.contrib.auth.urls` | logout, password_* |
| `/admin/` | Django Admin | admin |
| `/professores/` | `ProfessorListView` | `core:professor_list` |
| `/professores/novo/` | `ProfessorCreateView` | `core:professor_create` |
| `/professores/<pk>/editar/` | `ProfessorUpdateView` | `core:professor_update` |
| `/professores/<pk>/excluir/` | `ProfessorDeleteView` | `core:professor_delete` |
| `/classes/` | `ClasseListView` | `core:classe_list` |
| `/classes/nova/` | `ClasseCreateView` | `core:classe_create` |
| `/classes/<pk>/editar/` | `ClasseUpdateView` | `core:classe_update` |
| `/classes/<pk>/excluir/` | `ClasseDeleteView` | `core:classe_delete` |
| `/alunos/` | `AlunoListView` | `core:aluno_list` |
| `/alunos/novo/` | `AlunoCreateView` | `core:aluno_create` |
| `/alunos/importar/` | `aluno_import_view` | `core:aluno_import` |
| `/alunos/exportar/` | `aluno_export_view` | `core:aluno_export` |
| `/alunos/<pk>/editar/` | `AlunoUpdateView` | `core:aluno_update` |
| `/alunos/<pk>/excluir/` | `AlunoDeleteView` | `core:aluno_delete` |
| `/aulas/` | `AulaListView` | `core:aula_list` |
| `/aulas/nova/` | `AulaCreateView` | `core:aula_create` |
| `/aulas/<pk>/editar/` | `AulaUpdateView` | `core:aula_update` |
| `/aulas/<pk>/excluir/` | `AulaDeleteView` | `core:aula_delete` |
| `/aulas/<pk>/chamada/` | `aula_chamada` | `core:aula_chamada` |
| `/relatorios/dominical/` | `relatorio_dominical` | `core:relatorio_dominical` |
| `/relatorios/mensal/` | `relatorio_mensal` | `core:relatorio_mensal` |
| `/relatorios/ranking/` | `relatorio_ranking` | `core:relatorio_ranking` |
| `/auditoria/` | `AuditoriaListView` | `core:auditoria_list` |

## 12. Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SECRET_KEY` | `django-insecure-dev-only-change-me` | Chave secreta (trocar em produção) |
| `DEBUG` | `True` | `True` → SQLite; `False` → PostgreSQL + HTTPS |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Hosts permitidos (vírgula) |
| `DATABASE_URL` | vazio | URL do PostgreSQL em produção |

## 13. Estratégia de teste/verificação

O projeto **não possui testes automatizados** (`tests.py` ausente). A verificação atual
é manual:

1. `uv sync` + `uv run python manage.py migrate`.
2. Criar usuário admin e logar.
3. Validar CRUDs de professor/classe/aluno (incl. regra de 4 professores e `PROTECT`).
4. Criar aula e executar chamada (todos presentes por padrão; desmarcar ausentes).
5. Conferir relatórios dominical/mensal/ranking com dados de referência.
6. Testar importação `.xlsx`/`.csv` e exportação CSV.

> **Recomendação:** introduzir suíte `pytest` + `django.test` cobrindo RN-01 a RN-10 antes de novas evoluções.

## 14. Limitações conhecidas e melhorias sugeridas

| # | Limitação | Impacto | Melhoria sugerida |
|---|-----------|---------|-------------------|
| L1 | Aulas sem `LoginRequired` | Dados expostos sem autenticação | Aplicar mixin/decorator nas views de aula |
| L2 | Sem perfil/papéis de usuário | Todos acessam tudo | ✅ **Implementado** — grupos `Administrador`, `Secretaria`, `Professor` com permissões via `django.contrib.auth`; comando `criar_grupos` sincroniza idempotentemente; views protegidas com `PermissionRequiredMixin` / `@permission_required`; menu condicional por `perms` no template |
| L3 | Sem auditoria de alterações | Não se sabe quem mudou dados | ✅ **Implementado** — `Auditoria` + `criado_por`/`atualizado_por`, tela `/auditoria/` e registro no Admin |
| L4 | Importação sem relatório de erros por linha | Falhas silenciosas | ✅ **Implementado** — leitores de `.xlsx`/`.csv` e `process_alunos_import` retornam `erros` por linha (nome vazio, data inválida, falha de processamento); tela de importação exibe relatório (Linha/Valor/Problema) e comando `importar_alunos` imprime os erros e falha com `CommandError` |
| L5 | Duplicação de alunos não tratada | Aluno duplicado se nome variar | ✅ **Implementado** — campo `nome_normalizado` (casefold + sem acentos), `UniqueConstraint` `aluno_unico_nome_normalizado_por_classe` no banco, validação amigável no formulário e deduplicação na importação |
| L6 | Ranking só anual (jan→hoje) | Não cobre períodos arbitrários | ✅ **Implementado** — parâmetros `inicio`/`fim` (YYYY-MM-DD) para intervalo arbitrário com rótulo "d/m/Y a d/m/Y", fallback `ano` (jan→hoje), erro amigável para intervalo inválido e fallback ao modo ano para datas malformadas |
| L7 | Sem testes automatizados | Risco de regressão | ✅ **Implementado** — suíte `pytest` + `django.test` cobrindo RN-01 a RN-10 (17 testes em `src/ebd/core/tests/test_regras_negocio.py`) |
| L8 | Sem cache/otimização de queries pesadas | Relatórios mensais com muitas classes | ✅ **Implementado** — índice em `Aula.data` e índice composto `(aula, presente)` em `Presenca` (migração `0005`), `CACHES` LocMem (300s) e `@cache_page` nos relatórios dominical/mensal/ranking |
| L9 | Dependência `mcp-ollama-python` sem uso visível | Dependência fantasma | ✅ **Implementado** — dependência e seus 36 pacotes transitivos removidos via `uv remove mcp-ollama-python` (nenhum uso no código) |continue

## 15. Critérios de aceite (conclusão da documentação)

O sistema atual atende aos objetivos **O1–O5** com a seguinte cobertura:
- ✅ CRUD completo das 4 entidades principais.
- ✅ Chamada com regra "presente por padrão".
- ✅ Relatórios dominical, mensal e ranking.
- ✅ Dashboard com gráficos.
- ✅ Importação/exportação de alunos.
- ✅ Deploy automatizado e HTTPS em produção.
- ✅ Auditoria completa (RF-13) — trilha automática + tela `/auditoria/` + Admin read-only.
- ⚠️ Acesso sem controle de permissões e sem testes automatizados (ver §13 e §14).