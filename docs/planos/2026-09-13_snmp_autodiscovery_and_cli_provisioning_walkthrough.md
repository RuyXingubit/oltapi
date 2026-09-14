# Walkthrough: Auto-Descoberta Reversa e Provisionamento de SNMP via CLI sem Terminal Manual

## 1. O que foi Implementado

Alinhado com a visão de longo prazo de eliminar o acesso manual dos técnicos e administradores ao terminal CLI das OLTs:

### A. Auto-Descoberta Reversa no Running-Config e Backups
- Quando uma OLT é inspecionada na Telemetria de Chassi (`inspect_chassis`) e não possui comunidade SNMP ativa respondendo:
  - O sistema obtém o `running-config` vivo do chassi ou o backup mais recente do banco de dados.
  - O driver do fabricante analisa o arquivo de configuração através do método polimórfico `extract_snmp_community(config_text)`.
  - **Texto Claro (Fiberhome, ZTE, Intelbras, VSOL):** A API testa a comunidade encontrada na porta UDP 161. Se o agente SNMP responder, adota automaticamente a comunidade no cadastro da OLT e coleta o uptime em tempo real.
  - **Criptografado / Hash (Huawei VRP Cipher):** Se a Huawei estiver utilizando `snmp-server community read cipher %#%#...`, a API sinaliza o status `cipher_detected` com mensagem orientativa: o técnico pode informar a comunidade em texto plano ou o administrador pode provisionar uma nova comunidade.
  - **Não Configurado:** Sinaliza `not_configured` e orienta o provisionamento em 1 clique pelo administrador.

### B. Provisionamento CLI Automatizado e Gravação na Flash (`save` / `write`)
- Implementado `configure_snmp(olt, community, port)` em todos os 6 drivers (`HuaweiVRPDriver`, `FiberhomeTL1Driver`, `ZTEZXROSDriver`, `IntelbrasGSeriesDriver`, `Intelbras8820Driver`, `VSOLV1600Driver`).
- **Segurança Rigorosa:**
  - Sintaxe estritamente somente-leitura (`RO`) em todos os concentradores (ex: `read simple` na Huawei, `ro` na ZTE/Fiberhome/Intelbras/VSOL).
  - Sanitização com regex defensiva contra injeção de comandos CLI (`^[A-Za-z0-9_\.\-]{3,64}$`).
  - Gated com RBAC restrito a `SUPER_ADMIN`.
  - Comita as alterações na memória flash permanente da caixa (`save` + `y` na Huawei, `SAVE::DEV=ALL:1::;` na Fiberhome, `write` na ZTE/Intelbras/VSOL).
  - Executa teste imediato via socket UDP 161 e atualiza o cadastro da OLT.

### C. Endpoints REST
- `POST /api/v1/olts/{olt_id}/snmp/test`:
  - Testa qualquer comunidade (ou a cadastrada) via UDP 161, medindo latência (ms) e uptime.
  - Suporta `save_if_successful: true` para o técnico adotar a comunidade sem sair da tela.
- `POST /api/v1/olts/{olt_id}/snmp/configure`:
  - Provisiona a comunidade na OLT via CLI, grava na flash, testa UDP 161 e atualiza o banco de dados.

### D. Frontend (Web UI)
- **Visualização de Telemetria (`subview-xray`):**
  - Badge no topo indicando status operacional do SNMP (`Ativo`, `Cipher Detectado`, `Inacessível`, `Não Configurado`).
  - Card dedicado **📡 Telemetria SNMP (UDP 161) & Auto-Descoberta**:
    - Exibe diagnóstico detalhado.
    - Campos para comunidade e porta UDP.
    - Botões: `⚡ Testar Conectividade`, `💾 Salvar no Cadastro`, `🔧 Provisionar na OLT (Admin)`.
- **Modal de Cadastro (`modal-new-olt`):**
  - Campos adicionados para definir comunidade SNMP (padrão `public`) e porta UDP (padrão `161`).

### E. Mapeamento Dinâmico Multi-Slot e Normalização TR-101
- **Circuit ID TR-101:** Pré-normalização de espaços contínuos por hífen no nome da OLT (`re.sub(r"\s+", "-", olt_name.strip())`), suportando nomes como `"OLT VTX"` sem violar sanitização CLI e gerando `OLT-VTX eth <porta>:<onuid>:<vlan>`.
- **Descoberta Dinâmica de Slots Físicos (Fiberhome):** Leitura de `card_auth` (`gcob` 16 portas, `gc8b` 8 portas, etc.) e mapeamento automático de múltiplos slots de serviço (`Slot 1` com 16 PONs e `Slot 11` com 8 PONs), totalizando 24 portas PON reais e 100% das 561 ONUs mapeadas no chassi.

---

## 2. Validação e Testes

- **Testes Unitários:** 196 testes executados com 100% de aprovação via `pytest` (incluindo testes de extração de comunidade, detecção de cipher, provisionamento CLI para todos os fabricantes, multi-slot no driver Fiberhome e endpoints).
- **Contratos OpenAPI:** Sincronizados com sucesso através de `python -m scripts.export_openapi` (62 endpoints e 75 schemas exportados).
- **Docker Compose:** Container `oltapi` recompilado e ativo com status `healthy`.
- **Ambiente Real:** Validado contra a OLT física Fiberhome (`OLT VTX`), com auto-descoberta da comunidade `oltProserv`, teste UDP 161 bem-sucedido e mapeamento completo das 561 ONUs distribuídas nos Slots 1 e 11.
