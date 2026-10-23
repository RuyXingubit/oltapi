# Plano de Ação — Blindagem SonarQube Cloud (Zero Issues, Zero SCA Risks & Desduplicação < 2%)

**Data:** 2026-10-22  
**Status:** Aprovado e Concluído  

---

## 1. Objetivos
1. Eliminar todas as issues de **Security**, **Reliability** e **Maintainability** (`bugs`, `vulnerabilities`, `code_smells` = `0`) apontadas pelo SonarQube Cloud no Backend (Python/FastAPI), Frontend (Flutter/Dart) e Infraestrutura (`Dockerfile` / `docker-compose.yml` / GitHub Actions).
2. Eliminar todos os **Dependency Risks (SCA)** (`sca_count_any_issue = 0`, `Rating A`) atualizando pacotes transitivos e diretos com CVEs conhecidas em `requirements.txt`.
3. Reduzir a densidade de código duplicado (`duplicated_lines_density`) de `4.3%` (`1.631` linhas) para `< 2.0%` (`1.0%`), aplicando herança polimórfica e helpers reutilizáveis sem gambiarras.
4. Garantir **Quality Gate: `OK`** com cobertura de testes unitários em código novo `>= 80%` e desativação do *Automatic Analysis* em favor da pipeline CI com `coverage.xml` e `lcov.info`.

---

## 2. Escopo Técnico Aprovado
- **Segurança & Sanitização (`app/`):**
  - Sanitização contra Log Injection (`sanitize_for_log`) nos repositórios e middlewares.
  - Remoção de IPs/redes hardcoded em código de produção, parametrizando via `app/core/config.py`.
  - Reforço de expressões regulares contra ReDoS/backtracking (`python:S5852`) nos drivers CLI/TL1.
  - Verificação estrita de chaves SSH (`RejectPolicy` / `load_system_host_keys` configurável via `OLT_SSH_STRICT_HOST_KEY`) em todos os drivers OLT.
- **Infraestrutura & Dependências (`Dockerfile`, `requirements.txt`, `.github/workflows/ci.yml`):**
  - Pinagem de imagens base Docker por digest SHA-256 (`docker:S6596`) e execução com usuário não-root (`USER appuser`).
  - Substituição de `flutter upgrade` por checkout determinístico da tag `3.47.4` (`docker:S8550`) com `flutter pub get --enforce-lockfile`.
  - Atualização de `certifi==2026.10.19`, `urllib3==2.8.0`, `PyJWT==2.15.1`, `Mako==1.4.3`, `pytest==9.1.1`, `pytest-asyncio==1.4.0`, `paramiko==5.1.0` e `invoke==3.0.3`.
- **Desduplicação Estrutural (Opção A):**
  - Herança de `BackupStorage` em `SQLBackupStorage` para compartilhar validação de Path Traversal, diff e auditoria.
  - Extração de `build_optical_history_response` e `build_degraded_onus_report` em `ONUInventoryRepository`.
  - Extração de `_execute_onu_lifecycle_action` em `FiberhomeTL1Driver`.
  - Extração de `_resolve_profiles_and_traffic_tables`, `_resolve_router_profiles` e `_resolve_bridge_profiles` em `HuaweiVRPDriver`.
  - Extração de `_connect_fingerprint_and_create_olt`, `_finalize_onboarding_pipeline` e `_build_onboard_response` em `OLTOnboardingService`.
  - Extração de `_buildSectionCard`, `_showConfirmFormDialog` e `_buildMultiSelectChipGroup` em `governance_screen.dart`.
