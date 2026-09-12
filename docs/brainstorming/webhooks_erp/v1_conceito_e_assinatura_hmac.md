# Brainstorming v1: Sistema de Webhooks & Notificações de Eventos para ERPs

**Data:** 12/09/2026  
**Tema:** Notificação push reativa em tempo real para ERPs de Telecomunicações (IXC, MK-Auth, Voalle, SGP, RadiusNet)  
**Status:** Em Planejamento / Disk-First Rule  

---

## 1. Contexto e Motivação Operacional

Com o **Motor de Auto-Recuperação de Campo (TR-101)** implementado no OLTAPI, quando ocorre uma fusão invertida na madrugada ou troca de CTO e a ONU acende em outra porta PON (na mesma OLT ou em outra OLT/POP), o OLTAPI:
1. Identifica o equipamento pelo hardware serial imutável;
2. Verifica que o contrato está `ACTIVE`;
3. Provisiona na nova porta e limpa a antiga fantasma;
4. Recalcula o Circuit ID Broadband Forum TR-101 (`OLT eth slot/port:onu_id:vlan`).

### O Gargalo:
Se o ERP não for notificado imediatamente sobre essa mudança, o cadastro técnico do ERP continuará apontando para a porta antiga e o Circuit ID antigo. Quando o suporte abrir o contrato do cliente, haverá dessincronia de informações até que alguém faça uma sincronização manual.

### A Solução:
Implementar um subsistema de **Webhooks com Segurança Criptográfica HMAC SHA-256** no OLTAPI. Assim que a auto-reconciliação é executada, o OLTAPI dispara um evento push `onu.reconciled` para o webhook cadastrado do ERP com o novo Circuit ID e nova porta, permitindo que o ERP atualize seu cadastro técnico no mesmo milissegundo.

---

## 2. Padrão de Segurança (HMAC SHA-256 & Timing-Attack Safe)

De acordo com as diretrizes de segurança de APIs corporativas (padrão GitHub/Stripe):

1. **Assinatura Digital do Payload:**
   Cada entrega carrega os cabeçalhos:
   - `X-OLTAPI-Signature: sha256=<hex_digest>`
   - `X-OLTAPI-Event: onu.reconciled`
   - `X-OLTAPI-Delivery: <uuid7>`
   - `X-OLTAPI-Timestamp: <epoch_ou_iso>`

2. **Cálculo da Assinatura:**
   `digest = hmac.new(secret.encode('utf-8'), raw_body_bytes, hashlib.sha256).hexdigest()`

3. **Validação no ERP:**
   O ERP calcula o HMAC do corpo recebido utilizando o `secret` compartilhado e compara usando `hmac.compare_digest` para evitar ataques de temporização (*timing attacks*).

4. **Proteção contra Replay Attacks:**
   O campo `X-OLTAPI-Delivery` com **UUIDv7** garante que cada tentativa tenha um identificador único para deduplicação e idempotência no ERP.

---

## 3. Catálogo de Eventos Planejados

| Evento | Gatilho | Payload Principal |
| :--- | :--- | :--- |
| `onu.reconciled` | ONU auto-recuperada na mesma OLT ou cross-OLT | Serial, contrato, assinante, `old_circuit_id`, `new_circuit_id`, nova OLT, nova porta, novo ONU ID |
| `onu.detected` | Nova ONU desautorizada detectada via autofind | Serial, OLT ID, porta PON, timestamp |
| `onu.stock_rejected` | ONU de estoque tentou subir em porta de cliente | Serial, status do contrato, alerta de tentativa |
| `backup.completed` | Backup de OLT gerado com sucesso | OLT ID, nome, backup UUIDv7, hash SHA-256, tamanho |
| `backup.drift_detected` | Divergência detectada entre running-config e backup anterior | OLT ID, nome, diff linha a linha |
| `webhook.ping` | Teste manual disparado pelo operador | Mensagem de eco e validação de conectividade |

---

## 4. Estrutura de Modelos e Persistência

1. **Assinaturas de Webhook (`data/webhooks.json`):**
   - `id`: UUIDv7
   - `url`: URL HTTP/HTTPS de destino
   - `secret`: Chave de autenticação simétrica
   - `events`: Lista de eventos monitorados (ex: `["onu.reconciled"]` ou `["*"]`)
   - `is_active`: Flag de habilitação
   - `description`: Nome amigável (ex: "Integração IXC Soft Produção")
   - `created_at`: Datetime UTC

2. **Log de Entregas (`data/webhook_deliveries.json`):**
   - Últimas 200 tentativas de envio com status code, latência em ms, sucesso/falha e mensagem de erro se houver.

---

## 5. Próximos Passos
1. Elaborar plano de implementação formal (`implementation_plan.md`).
2. Submeter para aprovação do usuário.
3. Desenvolver modelos, repositório, despachante assíncrono (FastAPI `BackgroundTasks`), rotas e testes unitários.
