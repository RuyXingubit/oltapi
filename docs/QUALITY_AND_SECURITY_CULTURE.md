# Cultura Permanente de Segurança, Qualidade de Código e Zero Duplicidade (OLTAPI)

Este documento consolida os padrões de engenharia, segurança ofensiva/defensiva e qualidade de código estabelecidos durante a auditoria e blindagem completa no **SonarQube Cloud** (onde atingimos **0 Bugs**, **0 Vulnerabilities**, **0 Code Smells**, **0 Dependency Risks — Rating A**, **Duplicação de 1.0%** e **>90% de cobertura em código novo**).

Mesmo sem dependência de licença externa de análise estática, **estas diretrizes são mandatórias e permanentes** para qualquer evolução no Backend (`app/`), Frontend (`frontend/`), Infraestrutura (`Dockerfile`, `docker-compose.yml`, `.github/workflows/`) e Testes (`tests/`).

---

## 1. Segurança de Aplicação e Infraestrutura (SAST & Hardening)

### 1.1 Prevenção contra Log Injection (`S5145`)
- **Regra:** Nunca interpolar entradas controladas pelo usuário, payloads HTTP, caminhos de arquivo ou mensagens de exceção brutas diretamente em `logger.info()`, `logger.warning()` ou `logger.error()` sem sanitizar quebras de linha (`\r`, `\n`).
- **Como aplicar:** Utilizar sempre o utilitário [`sanitize_for_log()`](file:///Volumes/240/Code/oltapi/app/core/security.py) antes de registrar dados externos em logs:
  ```python
  from app.core.security import sanitize_for_log

  logger.warning("Falha ao processar serial %s: %s", sanitize_for_log(serial), sanitize_for_log(exc))
  ```

### 1.2 Proteção contra Path Traversal (`S2083`)
- **Regra:** Toda manipulação de arquivos em disco (backups `.cfg`, inventários `.json`, logs) deve validar que o caminho resolvido (`Path.resolve()`) permanece estritamente dentro do diretório base permitido.
- **Como aplicar:** Utilizar validação com `os.path.commonpath` ou `_resolve_safe_file`:
  ```python
  resolved = target_path.resolve()
  base_resolved = self.base_dir.resolve()
  if os.path.commonpath([str(base_resolved), str(resolved)]) != str(base_resolved):
      raise ValueError("Caminho de arquivo fora do diretório permitido.")
  ```

### 1.3 Expressões Regulares Seguras contra ReDoS / Backtracking Catastrófico (`S5852`)
- **Regra:** Parsers de CLI/TL1 de OLTs processam saídas extensas e não confiáveis de terminal. É proibido usar quantificadores ambíguos aninhados ou adjacentes como `.*?:`, `\s*([^\r\n]+)` com trailing spaces variáveis ou múltiplos `.*?` na mesma linha.
- **Como aplicar:**
  - Preferir classes de caracteres negadas explícitas (`[^\r\n:]+`, `[^\s/]+`, `\S+`) em vez de `.+` ou `.*?`.
  - Evitar combinar `\s*` com grupos que também casam espaços no final; fazer `.strip()` em Python após capturar o grupo.

### 1.4 Zero IPs, Credenciais ou Topologias Hardcoded (`S1313` / `S2068`)
- **Regra:** Nenhum endereço IP, sub-rede de gerência, gateway default ou senha/community SNMP pode ficar hardcoded em drivers, serviços ou modelos.
- **Como aplicar:** Centralizar qualquer constante default de protocolo/rede em [`app/core/config.py`](file:///Volumes/240/Code/oltapi/app/core/config.py) (`Settings`) para permitir sobrescrita por variável de ambiente (`.env`), e nos testes unitários usar constantes nomeadas claras ou fixtures.

### 1.5 Política de Chaves SSH (`S4830`)
- **Regra:** Conexões `paramiko.SSHClient` nos drivers OLT devem respeitar a configuração `settings.OLT_SSH_STRICT_HOST_KEY`:
  - Quando `True`, carregar `load_system_host_keys()` e aplicar `paramiko.RejectPolicy()`.
  - Quando `False` (redes isoladas de gerência L2 de bancada/ISP), aplicar a política configurada de forma explícita e centralizada no helper `_create_ssh_client()`.

### 1.6 Blindagem de Containers Docker (`S6596`, `S6470`, `S8550`)
- **Regra:**
  1. **Pinagem por Digest SHA-256:** Toda instrução `FROM` nos `Dockerfile`s deve fixar o digest imutável (`image:tag@sha256:...`), impedindo ataques de *supply-chain* por mutação de tag.
  2. **Imutabilidade de SDK e Lockfile no Build:** Nunca executar `flutter upgrade` ou `pip install` sem versão fixada durante o build da imagem. No Flutter, fazer checkout determinístico da tag exata do SDK e rodar `flutter pub get --enforce-lockfile`.
  3. **Execução Não-Root:** O estágio final de runtime deve sempre criar e operar sob usuário sem privilégios (`USER appuser`).
  4. **Segredos Fora da Imagem:** `.dockerignore` deve bloquear `.env`, `*.cfg`, `data/`, `backups/` e `.git/`.

---

## 2. Gestão de Riscos de Dependências (SCA — Software Composition Analysis)

- **Regra:** Manter **0 vulnerabilidades conhecidas (CVEs)** nas dependências diretas e transitivas.
- **Práticas obrigatórias ao atualizar pacotes:**
  1. Fixar versões exatas (`==`) em [`requirements.txt`](file:///Volumes/240/Code/oltapi/requirements.txt), incluindo pacotes transitivos sensíveis a segurança (`urllib3`, `certifi`, `PyJWT`, `cryptography`, `paramiko`, `Mako`, `invoke`).
  2. Sempre validar a árvore de dependências após qualquer alteração executando:
     ```bash
     .venv/bin/pip check
     ```
  3. No Flutter (`frontend/pubspec.lock`), manter o lockfile versionado e sincronizado com `flutter pub get --enforce-lockfile`.

---

## 3. Qualidade de Código e Manutenibilidade (Clean Code)

### 3.1 Limite Estrito de Complexidade Cognitiva (`S3776` — Máximo `<= 15`)
- **Regra:** Nenhuma função ou método (Python ou Dart) deve ultrapassar **15 pontos de Complexidade Cognitiva**.
- **Como manter a complexidade baixa:**
  - Aplicar *early returns* (guard clauses) no início da função em vez de aninhar múltiplos `if/else`.
  - Extrair sub-tarefas coesas em métodos privados auxiliares (`_parse_row`, `_resolve_router_profiles`, `_validate_vlan_scope`).
  - Substituir cascatas longas de `if/elif` por dicionários de despacho ou pequenos helpers especializados.

### 3.2 Confiabilidade Assíncrona, Exceções e Resiliência de Rede (`S7483`, `B006`, `S5754`)
- **Zero Bloqueio do Event Loop (`S7483`):** É proibido chamar funções síncronas bloqueantes (`time.sleep()`, `requests.get()`) dentro de funções `async def`. Utilizar sempre `await asyncio.sleep()`, `httpx.AsyncClient` ou delegar I/O bloqueante legado via `await asyncio.to_thread(...)`.
- **Zero Argumentos Default Mutáveis (`B006`):** Nunca declarar `def metodo(itens=[])` ou `def metodo(mapa={})`. Utilizar `Optional[List[...]] = None` e inicializar dentro do corpo da função.
- **Tratamento Estrito de Exceções (`S5754`):** Proibido usar `except:` sem tipo ou capturar `BaseException` sem relançar (`raise`), pois isso impede o encerramento gracioso do processo (`SystemExit` / `KeyboardInterrupt`).
- **Timeouts Obrigatórios em Equipamentos:** Toda conexão SSH, Telnet, TL1, SNMP, FTP ou HTTP (ex: GenieACS NBI) deve configurar `timeout` explícito para evitar exaustão de workers quando uma OLT perde gerência.

### 3.3 Segurança de Banco de Dados e OWASP API Top 10 (`S3649`)
- **Zero SQL Interpolado (`S3649`):** Toda consulta SQL em `app/storage/sql/` deve utilizar SQLAlchemy ORM ou *bind parameters* parametrizados; é terminantemente proibido passar f-strings (`f"SELECT ... {var}"`) para `.execute()`.
- **Prevenção de BOLA / IDOR Multi-Tenant (OWASP API1):** Endpoints que operam sobre OLTs, ONUs, VLANs ou backups por ID devem sempre validar o escopo do `SecurityContext` (`verify_olt_access`, `allowed_olt_ids`, `allowed_vlans`) antes de ler ou alterar dados.
- **Prevenção de Mass Assignment e Exposição Excessiva (OWASP API3):** Todo endpoint FastAPI deve declarar `response_model` explícito (nunca retornar models internos do banco com hashes/segredos) e restringir tamanhos de entrada com `Field(min_length=..., max_length=...)`.

### 3.4 Higienização Estática Contínua (Zero Warnings)
- **Backend (Python):**
  - Proibido deixar variáveis locais não utilizadas (`S1481`), parâmetros mortos (`S1172`), blocos `except` genéricos sem tratamento ou re-raise, ou literais de string repetidos 3+ vezes (`S1192` — extrair para constante).
- **Frontend (Flutter/Dart):**
  - Todo código deve passar com **0 issues** em:
    ```bash
    cd frontend && flutter analyze --no-fatal-infos
    ```
  - Sempre verificar `if (!mounted) return;` imediatamente após qualquer `await` antes de acessar `context` (`use_build_context_synchronously`).
  - Sempre usar `withValues(alpha: ...)` em vez de `.withOpacity(...)` depreciado.
  - Sempre adicionar `isExpanded: true` em `DropdownButtonFormField` dentro de modais/colunas com largura fixa e aplicar `Flexible`/`Expanded`/`Wrap` para **Tolerância Zero a Overflow**.

---

## 4. Cultura de Zero Duplicidade (`< 2.0%` Duplicated Lines)

A duplicação de código é o principal vetor de regressão silenciosa (quando um bug é corrigido em um lugar e esquecido na cópia). Nossa meta permanente é manter a duplicação global **abaixo de `2.0%`** (atualmente em **`0.85%` no scanner nativo / `1.0%` no SonarQube**).

### 4.1 Padrão para Repositórios Dual-Storage (JSON + SQL)
- Quando existir uma implementação em memória/JSON (`app/storage/<modulo>.py`) e uma implementação SQL (`app/storage/sql/<modulo>.py`):
  - **Nunca copiar e colar** regras de negócio, relatórios, cálculos de agregação, diff ou validações de caminho entre os dois arquivos.
  - A classe SQL deve **herdar da classe base** ou invocar métodos `@staticmethod` / polimórficos na classe base (ex: `SQLBackupStorage(BackupStorage)` reutilizando `compare_backups`, `audit_olt`, `get_backup_content`; `ONUInventoryRepository.build_optical_history_response` e `build_degraded_onus_report`).

### 4.2 Padrão para Drivers de OLT (`app/drivers/`)
- **Ações de Ciclo de Vida ONU (`deprovision`, `reboot`, `suspend`, `resume`):**
  - Quando o fluxo de localização da ONU, abertura de sessão (Telnet/SSH/TL1) e montagem da resposta `ONUActionResponse` for comum às 4 operações, centralizar em um único método parametrizado (ex: `_execute_onu_lifecycle_action` no driver Fiberhome).
- **Provisionamento e Atualização de Serviço (`provision_onu` e `update_onu_service`):**
  - Centralizar a descoberta e criação de Line Profiles, Service Profiles e Traffic Tables em helpers compartilhados (`_resolve_profiles_and_traffic_tables`), evitando duplicar a lógica entre autorização inicial e alteração de plano/VLAN.

### 4.3 Padrão para Serviços com Múltiplos Modos de Execução (`app/services/`)
- Quando um serviço possuir variante síncrona, wizard e streaming SSE (ex: `execute_onboarding`, `execute_wizard_onboarding`, `stream_onboarding` em [`olt_onboarding_service.py`](file:///Volumes/240/Code/oltapi/app/services/olt_onboarding_service.py)):
  - Extrair cada etapa do pipeline em métodos atômicos reutilizados por todos os fluxos (`_connect_fingerprint_and_create_olt`, `_finalize_onboarding_pipeline`, `_build_onboard_response`).

### 4.4 Padrão para Telas e Modais no Flutter (`frontend/lib/screens/`)
- **Cards de Seção:** Se uma tela possui 2 ou mais cards com o mesmo container, borda e cabeçalho (`Icon` + `Título` + `Badge` + `Ações`), extrair um builder `_buildSectionCard(...)`.
- **Modais de Formulário:** Se uma tela possui múltiplos `showDialog<bool>` com `StatefulBuilder` + `AlertDialog` + botões `Cancelar`/`Confirmar`, extrair um helper `_showConfirmFormDialog(...)` e widgets reutilizáveis para grupos de chips (`_buildMultiSelectChipGroup`).

---

## 5. Portão Automático Nativo e Gratuito (`scripts/quality_gate.py` & `pyproject.toml`)

Para garantir que o projeto **nunca dependa de licença paga do SonarQube** após o período de avaliação, o repositório conta com um **Portão Automático Nativo** ([`scripts/quality_gate.py`](file:///Volumes/240/Code/oltapi/scripts/quality_gate.py)) integrado ao hook de `git push` e ao GitHub Actions ([`.github/workflows/ci.yml`](file:///Volumes/240/Code/oltapi/.github/workflows/ci.yml)), além da configuração padronizada em [`pyproject.toml`](file:///Volumes/240/Code/oltapi/pyproject.toml):

1. **Portão de Qualidade, SAST, SCA, Complexidade e Duplicidade (< 1s, zero dependências externas):**
   ```bash
   .venv/bin/python -m scripts.quality_gate
   ```
   O script bloqueia automaticamente qualquer push ou PR se detectar:
   - Densidade de duplicação `>= 2.0%` entre `app/` e `frontend/lib/` (`CPD`);
   - Funções novas ou modificadas com Complexidade Cognitiva `> 15` (`S3776`);
   - Argumentos default mutáveis (`B006`), `time.sleep`/`requests` síncronos em `async def` (`S7483`), `except:` sem tipo ou `BaseException` sem re-raise (`S5754`);
   - Interpolação de f-string SQL em `.execute()` (`S3649`) ou IPs operacionais hardcoded (`S1313`);
   - Regressão no hardening dos `Dockerfile`s (`S6470` / `S6596`) ou conflitos no `pip check` (`SCA-PIP`).
2. **Sincronização do Contrato OpenAPI:**
   ```bash
   .venv/bin/python -m scripts.export_openapi
   ```
3. **Suíte de Testes e Cobertura Mínima Obrigatória do Backend (`--cov-fail-under=60`, `>= 80%` em código novo):**
   ```bash
   .venv/bin/pytest --cov=app --cov-report=term-missing --cov-fail-under=60 -q
   ```
4. **Análise Estática Estrita e Testes de Widget do Frontend Flutter:**
   ```bash
   cd frontend && flutter analyze --no-fatal-infos && flutter test --coverage
   ```
