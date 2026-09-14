# Plano de Implementação: Portal de Documentação Pública (MkDocs Material + ReDoc) no GitHub Pages

Este plano define a criação de um portal de documentação de padrão open-source enterprise para o **OLTAPI**, utilizando **MkDocs Material** com renderização interativa do contrato OpenAPI via **ReDoc**, deploy automatizado via **GitHub Actions** no **GitHub Pages**, adição de badges ao `README.md` e guia de configuração do repositório no GitHub (About e Topics).

---

## User Review Required

> [!IMPORTANT]
> **Habilitação do GitHub Pages no Repositório:**  
> Após o push deste workflow, você precisará ir nas configurações do repositório no GitHub:  
> **Settings -> Pages -> Build and deployment -> Source** e selecionar **GitHub Actions**. O workflow fará o resto de forma 100% autônoma.

---

## Open Questions

Nenhuma dúvida bloqueante no momento. A estrutura proposta aproveita 100% dos manuais técnicos já homologados no projeto (`MANUAL_OPERACIONAL.md`, `MANUAL_DESENVOLVEDOR.md`, `ARCHITECTURE.md`, `SECURITY_BASELINE.md`, `ROADMAP.md`) sem duplicar conteúdo.

---

## Proposed Changes

### 1. Configuração do MkDocs Material

#### [NEW] [mkdocs.yml](file:///Volumes/240/Code/oltapi/mkdocs.yml)
- Configuração do site `OLTAPI`:
  - Tema: `material` com suporte a Dark/Light mode comutável, abas superiores (`navigation.tabs`), busca em tempo real (`search.suggest`, `search.highlight`), cópia de blocos de código (`content.code.copy`).
  - Idioma: Português do Brasil (`language: pt-BR`).
  - Extensões Markdown: tabelas, admonitions (avisos em destaque), formatação de código com realce de sintaxe e tabs.
  - Estrutura de Navegação (`nav`):
    - 🚀 **Início**: `index.md`
    - 🐳 **Instalação & Setup**: `instalacao.md`
    - 📡 **Manual Operacional (ERPs)**: `MANUAL_OPERACIONAL.md`
    - 🛠️ **Manual do Desenvolvedor**: `MANUAL_DESENVOLVEDOR.md`
    - 🏛️ **Arquitetura & Padrões**: `ARCHITECTURE.md`
    - 🔒 **Segurança & Hardening**: `SECURITY_BASELINE.md`
    - 📖 **Referência da API (ReDoc)**: `referencia-api.md`
    - 🗺️ **Roadmap & Homologação**: `ROADMAP.md`
  - Exclusão seletiva de pastas internas de trabalho (`exclude_docs: "brainstorming/**\nplanos/**"`).

---

### 2. Páginas e Assets do Portal

#### [NEW] [docs/index.md](file:///Volumes/240/Code/oltapi/docs/index.md)
- Landing page oficial do portal de documentação com apresentação da arquitetura agnóstica, concentradores homologados, links de acesso rápido e callouts explicativos.

#### [NEW] [docs/instalacao.md](file:///Volumes/240/Code/oltapi/docs/instalacao.md)
- Guia consolidado de instalação com **Docker Compose + PostgreSQL 16**, variáveis essenciais do `.env`, execução com hot-reload local e verificação do healthcheck.

#### [NEW] [docs/referencia-api.md](file:///Volumes/240/Code/oltapi/docs/referencia-api.md)
- Página integrada no portal contendo o container ReDoc embutido com visualização elegante dos 66 endpoints, botão para tela cheia e link para download do `openapi.json`.

#### [NEW] [docs/api/redoc.html](file:///Volumes/240/Code/oltapi/docs/api/redoc.html)
- Visualizador ReDoc autônomo (standalone) carregando `docs/api_contracts/openapi.json`, permitindo visualização direta em tela cheia sem a barra de navegação do MkDocs quando o desenvolvedor desejar foco exclusivo na API.

---

### 3. Pipeline CI/CD GitHub Actions (GitHub Pages)

#### [NEW] [.github/workflows/docs.yml](file:///Volumes/240/Code/oltapi/.github/workflows/docs.yml)
- Segue rigorosamente os **5 Pilares de Economia do GitHub Actions**:
  1. **Concurrency com cancel-in-progress**: Cancela execuções redundantes.
  2. **Path filtering**: Dispara estritamente em pushes na `master` que toquem em `docs/**`, `mkdocs.yml`, `README.md` ou no próprio workflow (além de `workflow_dispatch` manual).
  3. **Timeout curto**: `timeout-minutes: 10`.
  4. **Cache granular**: `cache: 'pip'`.
  5. **Deploy Oficial GitHub Pages**: Usa `actions/upload-pages-artifact@v3` e `actions/deploy-pages@v4` com permissões mínimas (`pages: write`, `id-token: write`).

---

### 4. Apresentação do Repositório (Badges & Configurações)

#### [MODIFY] [README.md](file:///Volumes/240/Code/oltapi/README.md)
- Adição dos badges no topo do documento:
  - ![Tests](https://img.shields.io/badge/tests-220%20passing-brightgreen)
  - ![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blueviolet)
  - ![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)
  - ![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)
  - ![License](https://img.shields.io/badge/license-AGPL--3.0-orange.svg)
- Link em destaque para o portal de documentação publicado.

#### [Guia de Configuração do GitHub (About & Topics)]
- Recomendações e textos prontos para preenchimento manual nas configurações do repositório no GitHub.

---

## Verification Plan

### Automated Tests
- Testar build local do MkDocs:
  ```bash
  ./.venv/bin/pip install mkdocs-material
  ./.venv/bin/mkdocs build --strict
  ```
- Executar os testes unitários do projeto para garantir zero regressões:
  ```bash
  ./.venv/bin/pytest tests/unit
  ```
- Validar sincronismo OpenAPI:
  ```bash
  ./.venv/bin/python -m scripts.export_openapi
  ```

### Manual Verification
- Inspecionar a pasta gerada `site/` para certificar que `site/api_contracts/openapi.json` e `site/api/redoc.html` foram copiados com sucesso e renderizam o ReDoc.
