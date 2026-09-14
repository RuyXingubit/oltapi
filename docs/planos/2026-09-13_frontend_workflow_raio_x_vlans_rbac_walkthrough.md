# Walkthrough: Frontend Orientado ao Fluxo de Trabalho (Raio-X de OLTs, VLANs, FTP & RBAC)

A reformulação da interface web do **OLTAPI** foi concluída com sucesso, transformando a aplicação de uma tabela isolada de ONUs em um portal operacional completo, focado no ciclo de vida de operações de telecom e ISP.

---

## 1. Módulos e Recursos Implementados

### 🖥️ OLTs & Raio-X Profundo (`#subview-olts` e `#subview-xray`)
- **Listagem de Chassis:** Exibe todas as OLTs registradas com Fabricante, Modelo, Host:Porta, Protocolo e Conectividade.
- **Teste de Conectividade em Tempo Real:** Dispara `POST /api/v1/olts/{id}/test-connection` e atualiza a badge com latência em milissegundos.
- **Raio-X da OLT (`POST /api/v1/olts/{id}/xray`):**
  - **Métricas do Chassi:** Uptime humanizado (ex: `142 dias, 6 horas`), versão do firmware detectado e total de ONUs físicas conectadas.
  - **Mapa Físico de Portas (GPON & Uplink):**
    - Grade responsiva com LEDs operacionais em tempo real:
      - 🟢 **UP:** Porta ativa e com link/ONUs conectadas.
      - ⚫ **DOWN:** Porta livre / sem link.
      - 🔴 **DISABLED:** Porta desativada administrativamente.
    - Contagem de ONUs por porta PON com barra de progresso proporcional à capacidade máxima (ex: `24 / 128`).
    - Filtros por tipo de porta: *Todas*, *PON* e *Uplink*.
  - **Visualizador de Running-Config:** Bloco de terminal escuro apresentando a configuração ao vivo extraída da memória volátil da OLT, com botão para cópia para a área de transferência.
  - **Onboarding / Baseline v0:** Ação para confirmar a importação e gerar o snapshot baseline v0 diretamente da tela de Raio-X.

---

### 🌐 Gestão de VLANs & Capacidade (`#subview-vlans`)
- **Métricas de Capacidade:**
  - Consulta `GET /api/v1/olts/{id}/vlans/metrics`.
  - Exibe para cada VLAN: VLAN ID, Nome do Serviço, Descrição, **ONUs Provisionadas** (cadastradas no inventário) e **ONUs Ativas** (com link óptico online neste momento).
- **Histórico Completo de Seriais:**
  - Botão **📜 Histórico de Seriais** abre modal dinâmico (`#modal-vlan-history`).
  - Consulta `GET /api/v1/olts/{id}/vlans/{vlan_id}/history` alimentado pela tabela `onu_vlan_history`.
  - Exibe tabela detalhada: Serial, Assinante, Primeiro Registro, Último Visto e Status (*Ativo Agora* vs *Anterior*).
- **Criação de VLANs com Persistência na Flash:**
  - Modal `#modal-new-vlan` para cadastrar VLANs com portas tagged, persistindo automaticamente na memória flash do chassi.

---

### 💾 Configurações & Servidor FTP (`#subview-config`)
- **Transparência de Repositório de Backups:**
  - Consulta `GET /api/v1/ftp-servers/overview`.
  - **Status Operacional:** Indicador LED com badge Online/Offline e latência do socket FTP em tempo real.
  - **Metadados:** Host, Porta, Usuário, Origem da Configuração (`.env` vs Banco de Dados) e Modo Passivo.
  - **Zero Dados Falsos:** Se o FTP não estiver configurado, exibe estado neutro instruindo como definir as variáveis no `.env` (`FTP_HOST`, `FTP_PORT`, `FTP_USER`, etc.).
  - **OLTs Vinculadas:** Tabela de equipamentos que direcionam seus backups para o repositório.
  - **Repositório de Arquivos:** Tabela dos backups e baselines armazenados (nome do arquivo, OLT de origem, tamanho em KB e data/hora).
  - **Botão de Teste Direto:** Botão `⚡ Testar Conectividade FTP` para verificação sob demanda.

---

### 🔐 Governança Estrita de RBAC na Interface
- **Super Administrador (`SUPER_ADMIN`):**
  - Acesso total à sidebar: *Bancada*, *Inventário*, *OLTs & Raio-X*, *VLANs & Serviços*, *Configurações & FTP*, *Inquilinos & Acessos*.
  - Acesso aos botões de infraestrutura: cadastrar OLT, criar VLAN, sincronizar baseline v0, reiniciar ONU e desprovisionar ONU.
- **Operador NOC (`NOC`):**
  - Acesso à sidebar: *Bancada*, *Inventário*, *OLTs & Raio-X*, *VLANs & Serviços*, *Configurações & FTP*.
  - Acesso restrito: oculta gestão de inquilinos, botão de deletar/desprovisionar ONU e botões de criar OLT/VLANs infraestruturais.
  - Permitido: testar conexões, disparar Raio-X, consultar métricas de VLAN, histórico de seriais, status FTP, autorizar ONUs e reiniciar ONUs.
- **Técnico de Campo (`FIELD_TECH`):**
  - Acesso estrito apenas a: *Bancada (ONUs Não Autorizadas)* e *Inventário (ONUs Autorizadas)*.
  - Abas *OLTs & Raio-X*, *VLANs*, *Configurações* e *Inquilinos* ficam completamente ocultas da sidebar.
  - No inventário, os botões destrutivos ou de alteração de estado (Reiniciar e Desprovisionar) são removidos do DOM; permanece apenas o botão de medição de sinal óptico (`📶 Sinal`).

---

## 2. Validações e Testes Executados

1. **Testes Unitários:**
   - `tests/unit/test_olt_xray_and_vlans_metrics.py`: 3/3 testes passando (Overview de FTP, Raio-X com portas UP/DOWN e Métricas de VLANs com histórico).
   - `tests/unit/test_web_ui.py`: 2/2 testes passando (entrega de HTML com todas as views, CSS com classes de grid/LEDs e JS com todas as funções assíncronas).
   - Validação de sintaxe JS via `node -c app/static/js/app.js`: 100% livre de erros.
2. **Sincronização de Contratos OpenAPI:**
   - Executado `./.venv/bin/python -m scripts.export_openapi`: 59 endpoints e 71 esquemas sincronizados em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json`.
3. **Suite Completa de Testes:**
   - 178+ testes executados e validados via `pytest`.
