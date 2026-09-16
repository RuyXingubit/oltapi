# Implementação do Frontend Flutter para OLTAPI (MVP 1.0)

Criação da aplicação frontend Flutter multi-plataforma (Desktop macOS/Linux/Windows e Web) para o OLTAPI, espelhada nas melhores práticas e na arquitetura do software de referência de mercado para ISPs, sem jargões fictícios, com tema Dark NOC de alto contraste, integração REST direta com o backend FastAPI e tolerância zero a pixel overflow.

## User Review Required

> [!IMPORTANT]
> **Localização do Código do Frontend:** O projeto Flutter será inicializado em `/Volumes/240/Code/oltapi/frontend` para manter o desacoplamento total da API REST (conforme a regra de governança que proíbe templates ou arquivos estáticos servidos pelo FastAPI em `app/static/`).
> 
> **Autenticação & Conexão:** A aplicação armazenará de forma persistente e segura a URL do backend (`http://localhost:8000` por padrão) e a `X-API-Key` (ou token JWT), com validação de conectividade em tempo real.

## Open Questions

Nenhuma questão bloqueante restante, pois o alinhamento das 5 telas e da nomenclatura canônica de mercado já foi validado.

---

## Proposed Changes

### 1. Inicialização do Projeto Flutter & Dependências

#### [NEW] `frontend/pubspec.yaml`
- Criação do projeto Flutter `olt_frontend` (`com.oltapi.frontend`).
- Dependências essenciais:
  - `http: ^1.2.0` (chamadas HTTP REST resilientes).
  - `shared_preferences: ^2.2.2` (armazenamento local seguro das credenciais/URL da API).
  - `intl: ^0.19.0` (formatação de datas, números e bytes).
  - `provider: ^6.1.1` (gerenciamento de estado reativo e injeção de dependências).

---

### 2. Design System & Theme NOC

#### [NEW] `frontend/lib/core/theme/app_theme.dart` & `app_colors.dart`
- Paleta semântica NOC Dark Mode:
  - Fundo base: `#0C1017`
  - Painéis / Cartões: `#151B26` com bordas `#212C3D`
  - Verde Online / Sinal Bom: `#22C55E`
  - Amarelo Atenção / Sinal Limítrofe: `#EAB308`
  - Vermelho LOS / Crítico / Offline: `#EF4444`
  - Azul Ação / Unconfigured: `#3B82F6`
- Tipografia: Sans-serif para labels operacionais e `JetBrains Mono` / Monospace para seriais, portas PON, comandos e IPs.
- Componentes reutilizáveis com constraints defensivas contra overflow (`TextOverflow.ellipsis`, `SingleChildScrollView`, `Flexible`).

---

### 3. Camada de Dados & Clientes de API

#### [NEW] `frontend/lib/core/network/api_client.dart`
- Cliente HTTP centralizado com injeção automática de `X-API-Key`, tratamento padronizado de timeouts, 401/403 (autenticação), 404, 502 (OLT inalcançável) e 500.

#### [NEW] `frontend/lib/models/`
- `olt_model.dart`: Modelagem de OLT (`id`, `name`, `vendor`, `model`, `host`, `port`, `status`).
- `onu_model.dart`: Modelagem de ONU autorizada e não autorizada (`serial`, `port`, `onu_id`, `rx_power`, `tx_power`, `status`, `description`, `vlan`).
- `backup_model.dart`: Modelagem de histórico de backups (`backup_id`, `created_at`, `size_bytes`, `sha256_hash`).

---

### 4. Camada de Apresentação (As 5 Telas do MVP)

#### [NEW] `frontend/lib/screens/shell/app_shell.dart`
- Barra superior horizontal (Navbar) contendo:
  - Logo/Identidade OLTAPI.
  - Seletores de tela: `Dashboard` | `Aguardando Autorização (Unconfigured)` | `ONUs Autorizadas (Configured)` | `Diagnóstico Óptico` | `OLTs & Backups` | `Configurações`.
  - Indicador de status de conexão com o backend (bolinha verde/vermelha com latência).

#### [NEW] `frontend/lib/screens/unconfigured/unconfigured_screen.dart`
- Lista de ONUs pendentes de autorização agrupadas por OLT.
- Colunas: Tipo PON, Placa, Porta PON, Serial (SN), Modelo Detectado, Tempo de Detecção.
- Ação: Modal de Autorização (`Dialog` seguro) para definir Nome do Cliente, VLAN e Perfil.

#### [NEW] `frontend/lib/screens/configured/configured_screen.dart`
- Tabela mestre de ONUs autorizadas com campo de busca instantânea (`Serial, Nome, MAC`).
- Filtros por OLT, Porta PON e Status.
- Badges de status (Online, LOS, PwrFail) e medidor visual de sinal óptico em dBm.
- Botão `Visualizar` que abre a tela de detalhes.

#### [NEW] `frontend/lib/screens/onu_detail/onu_detail_dialog.dart`
- Painel de informações completas da ONU (Sinal Rx OLT, Rx ONU, Distância, VLAN, Porta).
- Barra de Ações Rápidas:
  - `Reiniciar (Reboot)`
  - `Suspender / Bloquear`
  - `Reativar`
  - `Desprovisionar / Excluir` (com modal de dupla confirmação exigindo confirmação do serial).

#### [NEW] `frontend/lib/screens/olts/olts_screen.dart`
- Tabela de OLTs ativas (`VSOL V1600`, `Fiberhome AN5516`).
- Teste de conectividade em 1-clique.
- Botão para disparar e baixar **Backup Imediato** (`.cfg`).

#### [NEW] `frontend/lib/screens/settings/settings_screen.dart`
- Formulário para configurar URL base da API e Chave de API (`X-API-Key`).
- Testador de ping e healthcheck do backend.

---

## Verification Plan

### Automated Tests
1. **Testes Unitários & Widget em Flutter:**
   - Executar suíte de testes de modelos e regras de negócio:
     ```bash
     cd frontend && flutter test
     ```
   - Validação de parsing de JSON da API para os modelos Dart (`OLTResponse`, `ONUDetails`, `UnauthorizedONU`).
   - Validação de renderização e ausência de pixel overflow em tamanhos de tela variados.
2. **Conformidade do Backend:**
   - Garantir que a suíte de 219 testes do backend Python continua 100% passando:
     ```bash
     pytest tests/unit -v
     ```

### Manual Verification
- Inicializar a aplicação Flutter em modo desktop macOS (`flutter run -d macos`) ou Chrome web (`flutter run -d chrome`).
- Verificar a conexão com a API local (`http://localhost:8000`), a listagem das OLTs cadastradas e a navegação entre as 5 telas sem nenhum erro de overflow.
