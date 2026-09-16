# Plano de Governança de Drivers, Inversão de Dependência e Zero Código Teórico

## 1. Visão Geral e Contexto
O projeto OLTAPI possuía drivers adicionados teoricamente por IA sem validação em bancada física (Huawei, ZTE, Intelbras 8820, Intelbras GSeries), violando as diretrizes de "Zero Dados Falsos / Sem Encher Linguiça" e gerando acoplamentos rígidos (`hasattr(driver, ...)`, condicionais de fabricante na camada de serviço).
A Fiberhome AN5516 é o único vendor homologado com 100% de sucesso em bancada física (onboard, backup, provisionar, suspender, reativar, deletar).
A VSOL V1600 está conectada fisicamente na bancada de desenvolvimento pronta para validação.

## 2. Decisões Arquiteturais Aprovadas
1. **Remoção Radical de Fabricantes Teóricos:**
   - Remoção de todos os adaptadores de drivers não testados em bancada física (`Huawei`, `ZTE`, `Intelbras 8820`, `Intelbras GSeries`).
   - Política: drivers só entram na árvore após teste de bancada física aprovado.
2. **Inversão de Dependência & Dynamic Registry:**
   - Criação de `DriverRegistry` em `app/drivers/registry.py` com decorator `@DriverRegistry.register`.
   - `DriverFactory` delega exclusivamente ao registry sem `if/elif` hardcoded.
   - Camada de serviço conversa 100% via métodos polimórficos de `BaseOLTDriver`.
   - Extirpação de qualquer `hasattr(driver, ...)` ou fallback com regex de marca no Core.
3. **Padrão Canônico de Backup:**
   - Prioridade 1: Envio prioritário nativo para servidor FTP (`driver.handles_primary_ftp_upload`).
   - Prioridade 2 (fallback gracioso): Captura do `running-config` pelo terminal display (SSH/Telnet) e persistência segura com criptografia Fernet (AES-128).
4. **Desacoplamento API-First:**
   - Remoção de `app/static/` e rotas estáticas.
   - Backend 100% REST JSON. O frontend será um client desacoplado em Flutter.
5. **Suíte de Conformidade Obrigatória:**
   - Criação do teste de conformidade `BaseDriverComplianceTest` em `tests/unit/test_driver_compliance.py`.
