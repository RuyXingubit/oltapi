# Baseline de Segurança: OLT Provisioning & Diagnostics API

## 1. Princípio Fundamental: Segurança em Primeiro Lugar
Seguindo a diretriz obrigatória do projeto, toda funcionalidade implementada é avaliada quanto ao seu impacto na segurança do sistema e da rede do provedor. Acesso não autorizado a uma OLT pode paralisar a operação de telecomunicações de uma cidade inteira.

---

## 2. Controles de Segurança Ativos

### 2.1 Prevenção contra Injeção de Comandos CLI (CLI Command Injection)
Como o driver monta comandos para envio direto a terminais de gerência (SSH/Telnet), todos os parâmetros de entrada fornecidos por ERPs ou técnicos são estritamente sanitizados:
- **Porta PON (`port`):** Validação por expressão regular `^[0-9]+(/[0-9]+)*$` (apenas dígitos e barras).
- **Serial da ONU (`serial`):** Validação por regex alfanumérico estrito `^[A-Za-z0-9]{4,20}$`. Rejeita espaços, ponto-e-vírgula, pipes (`|`), redirecionamentos (`>`, `<`), backticks e caracteres de escape.
- **VLAN (`vlan`):** Validação numérica estrita no intervalo válido IEEE 802.1Q (`1 <= vlan <= 4094`).
- **Descrição (`description`):** Apenas alfanuméricos, underscores e hífens (`^[A-Za-z0-9_\-]{1,64}$`). Rejeita aspas e caracteres de controle de terminal.

### 2.2 Autenticação e Controle de Acesso
- Todos os endpoints sob `/api/v1/` exigem o cabeçalho HTTP `X-API-Key`.
- A chave é comparada via tempo constante (`hmac.compare_digest`) para prevenir ataques de temporização (*timing attacks*).
- Requisições sem chave válida são rejeitadas imediatamente com status HTTP `401 Unauthorized`.

### 2.3 Proteção de Credenciais de Infraestrutura
- O modelo de saída da OLT (`OLTResponse`) omite explicitamente a senha de acesso da OLT.
- Credenciais só são utilizadas internamente no momento em que o driver estabelece a conexão com o equipamento.

### 2.4 Prevenção de Path Traversal na Entrega de Backups
- O download de backups (`/backups/{backup_id}/download`) valida que o `backup_id` é um UUID estrito antes de qualquer busca em disco.
- O caminho final do arquivo é resolvido e checado para garantir que permanece confinado dentro do diretório autorizado de backups daquela OLT específica, impedindo ataques com `../`.
