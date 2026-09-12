# Brainstorming: Gerenciamento Integral da OLT (NetDevOps) vs Provisionamento GPON

## 1. A Pergunta Estratégica
> "Todas as configurações da OLT serão salvas no backup? Seria muito interessante passarmos a controlar a OLT inteira via API (novas VLANs, portas de uplink, infraestrutura). Ou isso é exagero?"

---

## 2. Integridade dos Backups (O que é salvo?)
**Resposta:** **100% da configuração ativa da OLT é salva.**
- O comando executado no driver (`show running-config`, `display current-configuration` ou dump TL1) não filtra nada; ele extrai o arquivo de configuração bruto e integral do equipamento.
- Nele estão contidos:
  - Portas de Uplink (10G/40G SFP+, interfaces GE, LACP, MTU, trunking).
  - Toda a árvore de VLANs e SVLANs.
  - Rotas de gerência, gateway padrão, servidores NTP, Syslog, SNMP, usuários locais.
  - Perfis de DBA, line-profiles, service-profiles e todas as ONUs autorizadas.
- O backup é salvo com hash criptográfico SHA-256 e UUIDv7. Se a OLT queimar ou for resetada, esse arquivo restaura 100% do equipamento exatamente como estava.

---

## 3. Gerenciar Tudo na OLT via API: É Exagero ou o Caminho Certo?

### Veredito: **NÃO é exagero, é a evolução natural para uma plataforma NetDevOps / SDN.**
No entanto, na engenharia de redes de telecom, existe uma fronteira clara de **risco operacional e impacto de falha (Blast Radius)**.

### Matriz de Risco Operacional por Camada

| Camada | Exemplos | Frequência de Alteração | Risco / Blast Radius | Recomendação para a API |
| :--- | :--- | :--- | :--- | :--- |
| **Camada 1: Assinante (Last Mile GPON)** | Provisionar ONU, alterar VLAN da ONU, reboot OMCI, suspender/reativar, auto-recuperar. | **Diária / Contínua** (dezenas a centenas de vezes por dia). | **Baixo / Isolado:** Uma falha afeta estritamente 1 único cliente. | **Automação Total pelo ERP / API.** (Nosso foco atual). |
| **Camada 2: Serviços de Rede (VLANs & Profiles)** | Criar nova VLAN de serviço, listar VLANs ativas, criar profile de velocidade (ex: 600M). | **Semanal / Mensal** (ao lançar novo plano comercial ou novo serviço). | **Médio:** Criar uma VLAN não derruba a rede; mas alterar tag de VLAN existente pode afetar um grupo de clientes. | **Excelente candidato para a API** (com endpoints REST padronizados). |
| **Camada 3: Infraestrutura & Transporte (Uplinks & Core)** | Configurar porta 10G SFP+, criar agregação LACP, alterar MTU, mexer em IP de gerência ou rotas. | **Rara** (apenas na ativação do POP ou expansão de link). | **CRÍTICO:** Uma configuração errada numa porta de Uplink **apaga o link de transporte e derruba a OLT inteira com 2.000 clientes instantaneamente!** | **Implementar com extrema cautela**, confirmação explícita e travas de segurança rigorosas. |

---

## 4. Arquitetura Modular Recomendada

Para evoluirmos o OLTAPI com segurança militar, dividimos o roadmap em módulos progressivos:

### Módulo 1 (Atual - 100% Operacional): Ciclo de Vida de Assinante GPON
- Autofind, provisionamento, diagnóstico óptico, reboot, bloqueio, desprovisionamento, TR-101 e webhooks.

### Módulo 2 (Próximo Passo Natural): Gestão de VLANs e Perfis (`/api/v1/olts/{id}/vlans`)
- `GET /api/v1/olts/{id}/vlans`: Lista todas as VLANs já existentes na OLT.
- `POST /api/v1/olts/{id}/vlans`: Cria uma nova VLAN de serviço na OLT (Intelbras, Huawei, Fiberhome, etc.).
- `GET /api/v1/olts/{id}/profiles`: Lista profiles de tráfego e DBA disponíveis para uso no provisionamento.

### Módulo 3 (Fase Avançada): Telemetria e Status de Uplinks (`/api/v1/olts/{id}/uplinks`)
- `GET /api/v1/olts/{id}/uplinks`: Consulta status de portas de transporte (Link Up/Down, velocidade negociada, tráfego Rx/Tx, descartes).
- Apenas operações de **leitura e monitoramento** inicialmente, evitando comandos destrutivos no core.
