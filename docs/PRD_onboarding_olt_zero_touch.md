# PRD: Onboarding Contínuo de OLTs Zero-Touch (À Prova de Erro Humano)

**Data de Consolidação:** 2026-09-13  
**Status:** Aprovado para Implementação  
**Escopo:** API Backend, Drivers de Comunicação, Orquestrador de Onboarding, Interface Web e Cobertura de Testes Unitários.

---

## 1. Contexto e Problema de Negócio

No fluxo anterior, o cadastro e adoção de uma OLT em produção (Brownfield) demandava múltiplas etapas manuais e suscetíveis a erro humano:
- O operador precisava adivinhar/escolher fabricante, modelo, protocolo (SSH/Telnet) e porta em formulários extensos.
- Após cadastrar, precisava lembrar de testar, navegar até a tela de telemetria e clicar manualmente em "Criar Baseline v0".
- A configuração do SNMP dependia de testes manuais e comandos individuais.

Esse fluxo fragmentado gerava inconsistências, confusão na interface (botões de escrita pesada misturados em telas de telemetria) e lentidão operacional.

---

## 2. Visão do Produto: Onboarding Contínuo ("Zero-Touch")

O sistema passará a oferecer um **Pipeline Automatizado Contínuo**:
O operador apenas informa os 4 dados fundamentais:
1. **Nome da OLT** (ex: `OLT VTX`)
2. **Endereço IP / Host** (ex: `172.16.65.2`)
3. **Usuário** (ex: `admin`)
4. **Senha** (ex: `******`)
*(Opções avançadas recolhidas com porta customizada caso haja NAT específico)*.

A partir desse clique único, o backend assume o controle total e orquestra as seguintes etapas com feedback visual em tempo real:

```
[Cadastro Inicial]
       │
       ▼
[1. Negociação de Conexão: SSH (:22) -> Fallback Telnet (:23)]
       │
       ▼
[2. Fingerprinting: Reconhecimento Automático do Fabricante e Modelo]
       │
       ▼
[3. Segurança Obrigatória: Extração e Backup Baseline v0 com Hash SHA-256]
       │
       ▼
[4. SNMP Inteligente: Adota existente ou provisiona comunidade da Empresa (Zero Hardcode)]
       │
       ▼
[5. Ingestão de Inventário: Mapeamento de Portas, VLANs e ONUs com Circuit ID TR-101]
       │
       ▼
[6. Card Resumo Consolidado: OLT Pronta para Uso Diário]
```

---

## 3. Regras de Negócio e Diretrizes de Segurança

1. **Segurança em Primeiro Lugar:**
   - Nenhuma OLT é liberada no inventário sem a criação bem-sucedida do backup de segurança inicial (Baseline v0). Se a coleta da running-config falhar, o pipeline é abortado de forma atômica.
2. **Zero Hardcode de Empresa / Provedor:**
   - A comunidade SNMP automática gerada utiliza dinamicamente o nome da organização cadastrada no setup inicial da aplicação (`TenantModel` do tipo `PROVIDER_OWNER`).
   - O formato padrão é `<empresa_slug>_<olt_slug>` ou `olt_<empresa_slug>_ro`, sem caracteres especiais e restrita a somente leitura.
3. **Desacoplamento da Telemetria (Raio-X):**
   - O botão `Confirmar Importação & Criar Baseline v0` é **definitivamente removido** da tela de Telemetria / Raio-X.
   - O Raio-X passa a ser estritamente um painel de monitoramento e diagnóstico operacional ao vivo.
4. **Resiliência de Protocolo:**
   - O probe tenta primeiro SSH (mais seguro). Caso a porta 22 esteja fechada ou ocorra timeout, tenta Telnet (porta 23). O primeiro que responder com autenticação válida é adotado.

---

## 4. Arquitetura Técnica

### 4.1. Backend
- **Novo Serviço:** `app/services/olt_onboarding_service.py` (`OLTOnboardingService`).
- **Novo Endpoint:** `POST /api/v1/olts/onboard`.
- **Modelos Pydantic:** `OLTOnboardRequest` e `OLTOnboardResponse`.
- **Drivers:** Métodos auxiliares de detecção de banner e fingerprinting por prompt CLI.

### 4.2. Frontend
- **Modal de Onboarding Simplificado:** Campos limpos (Nome, IP, Usuário, Senha) + accordion "Avançado" (Porta).
- **Stepper Visual Interativo:** Barra de progresso com checklist visual atualizado a cada etapa concluída.
- **Card Resumo:** Apresenta o chassi onboardado com botões de navegação rápida.
- **Limpeza do Raio-X:** Remoção do botão de baseline v0 do cabeçalho da telemetria.

### 4.3. Qualidade & Testes
- Suíte dedicada em `tests/unit/test_olt_onboarding_pipeline.py`.
- Validação de 100% dos testes via `pytest`.
- Sincronização obrigatória de contratos OpenAPI (`python -m scripts.export_openapi`).
