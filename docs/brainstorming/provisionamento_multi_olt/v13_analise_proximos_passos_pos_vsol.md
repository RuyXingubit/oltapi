# Brainstorming: Próximos Passos Pós-Suporte V-SOL
**Versão:** v13 (Cenário com 4 Grandes Fabricantes Homologados: Intelbras, Huawei, Fiberhome e V-SOL)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Panorama Atual do OLTAPI
O projeto atingiu um marco de maturidade relevante:
- **66 testes unitários** automatizados e 100% aprovados em CI/CD.
- **4 ecossistemas de fabricantes dominantes no Brasil** homologados:
  1. **Intelbras:** 8820, 8820i, G08, G16 (Broadcom e G-Series CLI).
  2. **Huawei:** MA5800 (X2/X7/X15/X17) e MA5600T (MA5608T/MA5680T) via VRP CLI.
  3. **Fiberhome:** AN5516 e AN6000 via TL1 (porta 3337) e SSH.
  4. **V-SOL:** Família V1600 (V1600GT, V1600G) via CLI SSH.
- Core de segurança blindado contra injeção CLI, autenticação em tempo constante e identificadores UUIDv7 (RFC 9562).

---

## 2. Direções Estratégicas para os Próximos Passos

### Direção 1: Validação Real na Bancada com a V-SOL V1600GT
- **Conceito:** Aproveitar que a OLT física está disponível na bancada para fazer um teste ponta-a-ponta.
- **Como Funciona:**
  - Criar um utilitário de validação em [scripts/test_live_olt.py](file:///Volumes/240/Code/oltapi/scripts/test_live_olt.py).
  - O usuário informa o IP de gerência local, credenciais e porta.
  - O script conecta na OLT física, lê o running-config real, executa o autofind e valida os parsers contra as respostas exatas do firmware da máquina.
- **Prós:** Feedback imediato do mundo real, eliminando qualquer surpresa de firmware antes de ir para produção.
- **Contras:** Requer que o usuário execute localmente e conecte na OLT da bancada.

### Direção 2: Módulo de Backup Automatizado & Disaster Recovery
- **Conceito:** Transformar o endpoint atual de backup sob demanda em um sistema autônomo de proteção de ativos de rede.
- **Funcionalidades:**
  - Agendador de tarefas periódicas (ex: rodar backups diários às 03:00 da manhã de todas as OLTs).
  - Política de retenção configurável (ex: manter últimos 30 dias de backup e purgar os antigos).
  - Hash diferencial SHA-256 para alertar se houve alterações de configuração entre um backup e outro.
- **Prós:** Agrega valor operacional gigantesco e tranquilidade para a equipe de redes do provedor.
- **Contras:** Não adiciona novos fabricantes.

### Direção 3: Webhooks / Notificações em Tempo Real de Novas ONUs
- **Conceito:** Notificação push para ERPs ou aplicativos móveis quando uma ONU não autorizada é inserida na fibra.
- **Funcionalidades:**
  - Background worker que monitora o autofind das OLTs.
  - Disparo de Webhook HTTP com payload padronizado para o ERP (IXC, MK-Auth, Voalle).
- **Prós:** Agiliza a ativação do cliente pelo técnico em campo.
- **Contras:** Demanda serviço assíncrono rodando continuamente.

### Direção 4: Adicionar Suporte à ZTE (C300 / C320 / C600)
- **Conceito:** Incluir o último fabricante expressivo do mercado nacional (muito comum em redes neutras).
- **Prós:** Cobertura de quase 99% do mercado de provedores no Brasil.
- **Contras:** Mais um driver de CLI antes de testar em produção os que já foram feitos.

### Direção 5: Dockerização Production-Ready & Compose
- **Conceito:** Criar `Dockerfile` multi-stage otimizado e `docker-compose.yml` para subida imediata em ambiente de homologação/produção com volumes persistentes.
- **Prós:** Facilita muito colocar o OLTAPI para rodar na rede do provedor.
