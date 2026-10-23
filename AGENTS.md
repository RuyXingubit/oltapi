# OLTAPI - Regras e Diretrizes do Projeto para Agentes e Desenvolvedores

## 1. Sincronização Obrigatória do OpenAPI antes de Commit & Push
Antes de qualquer commit e push, é MANDATÓRIO executar o script de exportação do contrato OpenAPI:
```bash
python -m scripts.export_openapi
```
Os contratos gerados em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json` devem ser adicionados ao commit.

## 2. Cobertura de Testes Unitários
Sempre que uma feature ou correção for criada, execute `pytest` para certificar que 100% dos testes passam e nenhuma regressão ocorreu.

## 3. Segurança em Primeiro Lugar
Toda alteração deve manter ou aumentar os padrões de segurança (sanitização de inputs, validação de tokens JWT, chaves de API com hash e RBAC multi-tenant).

## 4. Histórico de Planos Aprovados (`docs/planos/`)
Somente planos de implementação aprovados explicitamente pelo usuário (e seus respectivos walkthroughs de conclusão) devem ser arquivados em `docs/planos/` (ex: `docs/planos/YYYY-MM-DD_<tema>_plan.md` e `docs/planos/YYYY-MM-DD_<tema>_walkthrough.md`) e commitados no repositório Git. Rascunhos ou planos em debate descartados não devem poluir a pasta.

## 5. Governança de Drivers, Inversão de Dependência & Zero Código Teórico
- Toda OLT adicionada DEVE herdar de `BaseOLTDriver` e se auto-registrar no `DriverRegistry` via `@register_driver`.
- **Proibição de Fabricantes Teóricos:** É TERMINANTEMENTE PROIBIDO adicionar novos drivers de fabricantes sem acesso a hardware físico de bancada para homologação real. Drivers só entram na árvore do projeto após teste de bancada física aprovado pelo usuário.
- **Isolamento Radical (Ports & Adapters):** Um driver nunca deve importar outro driver. Proibido utilizar `hasattr(driver, ...)` ou condicionais de fabricante (`if olt.vendor == ...`) nos serviços de negócio. A camada de serviço conversa exclusivamente com métodos polimórficos da interface `BaseOLTDriver`.
- **Padrão Canônico de Backup:** Todo driver deve tentar prioritariamente o envio por FTP com a sintaxe nativa da OLT; caso nenhum FTP esteja vinculado ou o upload falhe, o driver DEVE fazer fallback automático para captura do `running-config` pelo terminal (SSH/Telnet).
- **Suíte de Conformidade (`BaseDriverComplianceTest`):** Todo driver ativo deve passar na suíte de conformidade cobrindo: `get_running_config`, `backup_config` (FTP + fallback), `get_chassis_interfaces` (sem dados inventados), `get_onu_details` (sinal óptico real), `provision_onu`, `deprovision_onu`, `suspend_onu`, `resume_onu`, `reboot_onu`, `configure_snmp`, `list_all_authorized_onus`, `inspect_management_arch` e `execute_wizard_commissioning`.

## 6. Desacoplamento API-First & Zero Hardcode
O backend é 100% REST JSON. O client e os serviços nunca presumem portas, perfis ou formatos hardcoded; todo dado operacional deve ser derivado diretamente do hardware ou da API. É proibido manter arquivos estáticos ou páginas web servidas pelo backend (`app/static/`).

## 7. Cultura Permanente de Segurança, Qualidade & Zero Duplicidade (Padrão SonarQube)
Mesmo sem o scanner ativo do SonarQube Cloud, todo código novo ou refatorado DEVE obedecer rigorosamente ao guia completo em [`docs/QUALITY_AND_SECURITY_CULTURE.md`](docs/QUALITY_AND_SECURITY_CULTURE.md):
- **SAST (Segurança de Código):**
  - **Prevenção de Log Injection (S5145):** Sempre envolver dados externos/de usuário em `sanitize_for_log(...)` (`app/core/security.py`) antes de registrar em `logger.*`.
  - **Prevenção de Path Traversal (S2083):** Validar nomes de arquivos com `SAFE_ID_RE` e confirmar confinamento com `os.path.commonpath([base_dir, target_path]) == base_dir` antes de qualquer I/O em disco.
  - **Prevenção de ReDoS (S5852):** Nunca usar quantificadores aninhados ambíguos em regex (`.*` múltiplos na mesma linha); preferir classes negadas (`[^\r\n:]+`), `str.partition()` ou `str.split()`.
  - **Zero Hardcoded Secrets/IPs (S1313 / S2068):** Nenhum IP, credencial ou token fixo no código de produção; usar variáveis de ambiente ou IPs da RFC 5737 (`192.0.2.x`, `198.51.100.x`, `203.0.113.x`) apenas em testes/exemplos.
  - **Docker Hardening:** Imagens base sempre pinadas com `@sha256:...`, execução com usuário não-root (`USER appuser`), `COPY --chown=...` explícito e instalação com lockfile (`--locked`).
- **SCA (Dependências Seguras):** Ao atualizar pacotes em `requirements.txt`, manter dependências transitivas críticas pinadas em versões livres de CVEs e rodar `pip check` para garantir zero conflitos de resolução.
- **Complexidade Cognitiva (S3776):** Nenhum método/função pode ultrapassar Complexidade Cognitiva **15**. Usar *early returns* (guard clauses) e extrair sub-rotinas privadas coesas (`_parse_*`, `_build_*`, `_validate_*`).
- **Zero Duplicidade (`< 2.0%`):**
  - Proibido copiar e colar blocos lógicos entre implementações JSON e SQL (`app/storage/` vs `app/storage/sql/`) ou entre drivers (`FiberHome`, `Huawei`, `ZTE`); extrair helpers compartilhados na camada base.
  - No Flutter (`frontend/`), extrair componentes parametrizados ou builders quando 2+ telas/modais compartilharem a mesma estrutura visual, validar `if (!mounted) return;` após `await`, usar `isExpanded: true` em `DropdownButtonFormField` e manter `flutter analyze` com **0 issues**.
- **Cobertura em Código Novo (`>= 80%`):** Toda nova classe, método, helper ou widget deve vir acompanhado de testes unitários/widget (`pytest` no backend e `flutter test` no frontend) cobrindo ao menos 80% das linhas novas.


