# Brainstorming v1: HATEOAS Minimalista Orientado a Fluxo e Estado (State-Driven Workflow)

## 1. Visão Geral e Princípio Norteador

Ao contrário do HATEOAS enciclopédico (que anexa dezenas de links estáticos e incha o payload JSON), o **HATEOAS Orientado a Fluxo** atua como um **assistente de navegação para o desenvolvedor ou ERP**.

Ele responde a duas perguntas cruciais em cada etapa:
1. **O que acabou de acontecer?** (Estado atual do recurso e resultado da operação).
2. **Quais são os próximos passos lógicos que posso tomar a partir daqui?** (Ações disponíveis contextuais).

---

## 2. Fluxo 1: Cadastro da OLT (`POST /api/v1/olts`)

Ao cadastrar uma nova OLT, a API deve:
1. Retornar cabeçalho HTTP padrão `Location: /api/v1/olts/{id}`.
2. Salvar os dados cadastrais (segurança: credenciais criptografadas via Fernet).
3. Executar uma sondagem rápida de conectividade (ping/porta SSH/Telnet).
4. Fornecer `_links` contextuais baseados no status da conexão.

### Cenário A: OLT Conectada com Sucesso (`status: "online"`)
O cliente acabou de adicionar o equipamento e a comunicação está estabelecida. Os próximos passos são descobrir a OLT e verificar clientes pendentes:

```json
{
  "id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "name": "OLT-POP-CENTRO",
  "vendor": "vsol",
  "model": "v1600gt",
  "host": "192.168.10.50",
  "status": "online",
  "message": "OLT cadastrada e comunicação SSH estabelecida com sucesso.",
  "_links": {
    "self": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde", "method": "GET" },
    "config": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/config", "method": "GET" },
    "unauthorized_onus": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/unauthorized", "method": "GET" },
    "backup_initial": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups", "method": "POST" }
  }
}
```

### Cenário B: Falha de Conexão ou Credenciais Incorretas (`status: "unreachable"`)
A OLT foi cadastrada, mas não responde na porta ou a senha falhou. Não faz sentido oferecer links de "listar ONUs" ou "gerar backup" porque vão falhar. O HATEOAS guia o usuário para resolver o problema:

```json
{
  "id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "name": "OLT-POP-CENTRO",
  "vendor": "vsol",
  "model": "v1600gt",
  "host": "192.168.10.50",
  "status": "unreachable",
  "error_reason": "Timeout ao conectar em 192.168.10.50:22 após 3000ms. Verifique rota, firewall ou porta.",
  "_links": {
    "self": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde", "method": "GET" },
    "edit_olt": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde", "method": "PUT" },
    "test_connection": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/test-connection", "method": "POST" }
  }
}
```

---

## 3. Fluxo 2: ONUs Não Autorizadas e Provisionamento Guiado

Quando o técnico ou ERP consulta `GET /api/v1/olts/{id}/onus/unauthorized`:
Cada ONU encontrada traz o link pronto para provisionamento, eliminando a necessidade do ERP memorizar o caminho de provisionamento:

```json
{
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "total_unauthorized": 1,
  "onus": [
    {
      "port": "0/1",
      "serial_number": "VSOL12345678",
      "model": "V2801SG",
      "_links": {
        "provision": {
          "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/onus/provision",
          "method": "POST"
        }
      }
    }
  ]
}
```

---

## 4. Fluxo 3: Backup Gerado e Ações Imediatas

Ao disparar `POST /api/v1/olts/{id}/backups`:
1. Resposta `201 Created` com header `Location: /api/v1/olts/{id}/backups/{backup_id}/download`.
2. `_links` para:
   - Baixar o arquivo (`download`).
   - Comparar com o backup anterior (`diff`).
   - Auditar integridade do arquivo em disco (`audit`).

```json
{
  "backup_id": "0191e512-3456-789a-bcde-f0123456789a",
  "olt_id": "0191e4f2-51a8-7d84-a12b-3456789abcde",
  "size_bytes": 18240,
  "sha256_hash": "a1b2c3d4...",
  "_links": {
    "download": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups/0191e512-3456-789a-bcde-f0123456789a/download", "method": "GET" },
    "compare": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups/compare?target_id=0191e512-3456-789a-bcde-f0123456789a", "method": "GET" },
    "audit": { "href": "/api/v1/olts/0191e4f2-51a8-7d84-a12b-3456789abcde/backups/audit", "method": "GET" }
  }
}
```

---

## 5. Diretrizes de Segurança e Padrões Técnicos

1. **URIs Relativas (Path-only):**
   - Em vez de `http://localhost:8000/api/v1/...` ou `http://10.0.0.15/...`, usar caminhos relativos `/api/v1/...`.
   - **Garantia de Segurança:** Blindagem total contra vazamento de IPs ou nomes de máquinas internas da infraestrutura, além de funcionar perfeitamente com qualquer domínio/porta pública configurada no Nginx/Traefik sem complexidade de reescrita.
2. **Header `Location`:**
   - Sempre presente em respostas `201 Created` apontando para o recurso canônico criado.
3. **Padrão HAL `_links`:**
   - Objeto padronizado com `href` e `method`.
4. **Zero Overhead em Listagens Massivas:**
   - Em endpoints de telemetria massiva (ex: `list_port_onus`), omitir links por ONU para manter performance máxima de rede e processamento.
