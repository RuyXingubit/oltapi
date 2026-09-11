# Brainstorming: Próximos Passos de Evolução do OLTAPI
**Versão:** v9 (Análise de Prioridades: Fiberhome TL1 vs Backup Automatizado vs Webhooks vs Docker)  
**Data:** 2026-09-11  
**Autor:** Antigravity & Usuário  

---

## 1. Status Atual do Projeto
Com **48 testes unitários** aprovados e cobertura dos ecossistemas:
- **Intelbras 8820 / 8820i** (Broadcom CLI)
- **Intelbras G-Series G08 e G16** (G-Series CLI)
- **Huawei MA5800 e MA5600T** (VRP CLI)

Temos a base do MVP estável com os 6 fluxos essenciais (configuração, backup com SHA-256/UUIDv7, diagnóstico óptico, autofind, provisionamento agnóstico e bootstrap zero-touch).

---

## 2. Opções Estratégicas para o Próximo Passo

### Opção A: Driver Fiberhome (AN5516-01/04/06 e AN6000)
- **Objetivo:** Completar a "tríplice coroa" das OLTs mais usadas pelos provedores de internet no Brasil (Intelbras, Huawei e Fiberhome).
- **Abordagem Técnica:** Implementar driver via **TL1 (Transaction Language 1)** na porta TCP 3337 ou CLI SSH.
- **Prós:** Fecha o trio de marcas dominantes em 90%+ dos ISPs nacionais.
- **Contras:** A sintaxe TL1 é baseada em blocos posicionais de comandos (`LOGIN:::1::...`, `ADD-ONU::...`), exigindo um parser dedicado.

### Opção B: Módulo de Backup & Disaster Recovery Automatizado
- **Objetivo:** Transformar o backup sob demanda existente em um serviço autônomo e resiliente.
- **Recursos:**
  - Agendamento periódico de coleta de backup de todas as OLTs cadastradas.
  - Rotação e retenção configurável (ex: expirar backups com mais de 30 dias).
  - Verificação automática de integridade (alerta se o running-config sofreu alteração não esperada).
- **Prós:** Agrega valor operacional imediato e segurança para o ISP antes de colocar em produção.
- **Contras:** Não expande a variedade de fabricantes suportados.

### Opção C: Webhooks de Detecção de Novas ONUs (Autofind Push)
- **Objetivo:** Eliminar a necessidade de o ERP ficar fazendo polling contínuo para descobrir se uma nova ONU foi plugada.
- **Recursos:**
  - Background worker que consulta o `autofind` das OLTs a cada X minutos.
  - Disparo de evento HTTP POST (`webhook`) para o ERP com payload `{ "event": "onu_discovered", "olt_id": "...", "port": "0/1/0", "serial": "..." }`.
- **Prós:** Experiência moderna para o técnico em campo (notificação push no app ou bot de Telegram/WhatsApp do provedor).
- **Contras:** Requer mecanismo de agendamento em background (FastAPI BackgroundTasks ou Celery/ARQ).

### Opção D: Empacotamento Docker & Deploy Production-Ready
- **Objetivo:** Criar o `Dockerfile` otimizado multi-stage e `docker-compose.yml` para implantação com 1 comando.
- **Recursos:** Configuração de persistência de backups (`/data/backups`), variáveis de ambiente seguras (`.env`) e healthcheck nativo do container.
- **Prós:** Facilita teste prático e homologação em laboratório ou ambiente real.
- **Contras:** Tarefa puramente de empacotamento infra/DevOps.

---

## 3. Matriz de Decisão e Recomendação

| Opção | Impacto no Negócio | Complexidade | Recomendação |
| :--- | :---: | :---: | :---: |
| **A. Fiberhome TL1** | Altíssimo | Média | 🥇 **Prioridade Recomendada 1** |
| **B. Backup Automatizado** | Alto | Baixa/Média | 🥈 **Prioridade Recomendada 2** |
| **C. Webhooks Autofind** | Alto | Média | 🥉 **Prioridade Recomendada 3** |
| **D. Docker / Compose** | Médio | Baixa | ⚡ Pode ser feito a qualquer momento |
