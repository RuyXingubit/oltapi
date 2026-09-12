# Brainstorming v1: Fallback Telnet -> SSH & Auto-Upgrade de Segurança

## 1. Contexto & Proposta do Usuário
Muitas OLTs legadas em campo (especialmente Fiberhome AN5516 e Intelbras) possuem o Telnet ativo de fábrica, mas o SSH desabilitado ou com falha de handshake criptográfico.
A proposta consiste em:
1. O sistema tenta conexão segura via **SSH** (porta 22).
2. Se falhar (ex: `Connection reset`, timeout, banner error):
3. O sistema faz fallback transparente para **Telnet** (porta 23).
4. Ao autenticar com sucesso via Telnet:
   - Identifica se o firmware suporta SSH.
   - Executa os comandos para habilitar o serviço SSH e gerar as chaves criptográficas (`set ssh server enable` / `crypto key generate rsa`).
   - Salva a configuração na memória permanente (flash).
   - Testa a nova conexão SSH.
   - Sendo bem-sucedido, atualiza o cadastro da OLT no banco de dados para `protocol='ssh'`, eliminando o tráfego em texto plano para os próximos acessos.

---

## 2. Análise de Segurança (Diretriz Mandatória)
- **Aumenta ou diminui a segurança?** **AUMENTA A SEGURANÇA.**
  - Transforma concentradores que hoje trafegam credenciais em texto claro na rede do provedor em canais 100% criptografados via SSH.
  - Elimina a necessidade de técnicos acessarem via Telnet no dia a dia.

---

## 3. Prós e Contras

### Vantagens (Prós):
1. **Zero Fricção no Onboarding:** O provedor cadastra a OLT sem precisar acessá-la manualmente antes para habilitar SSH.
2. **Hardening Proativo da Infraestrutura:** A própria API eleva o nível de segurança do parque de equipamentos do provedor.
3. **Fallback Resiliente:** Equipamentos com firmwares antigos sem suporte a SSH continuam operando via Telnet com aviso claro no dashboard.

### Cuidados e Desafios (Contras):
1. **Variação de Sintaxe de Firmware:** Cada fabricante e versão de firmware possui comandos específicos para habilitar SSH e gerar chaves criptográficas:
   - **Fiberhome AN5516:** `admin` -> `set ssh server enable` / `set ssh user ...` (ou comandos TL1 específicos).
   - **Intelbras 8820:** `enable` -> `config` -> `ip ssh server enable`.
   - **Huawei:** `system-view` -> `rsa local-key-pair create` -> `stelnet server enable`.
2. **Tempo de Geração de Chaves RSA:** Gerar chaves RSA de 2048 bits em processadores MIPS/ARM fracos de OLTs antigas pode levar de 5 a 15 segundos.
3. **Firmwares sem SSH:** Existem OLTs legadas cujo binário de firmware não foi compilado com o daemon SSH (OpenSSH/Dropbear). Nesses casos, o sistema deve manter Telnet com aviso de auditoria.

---

## 4. Próximos Passos Propostos
1. Validar se a OLT física de teste aceita conexão via Telnet na porta 23.
2. Testar comandos manuais via Telnet para verificar a resposta do terminal da Fiberhome.
3. Projetar o módulo de Auto-Elevação de Segurança no `OLTConnectionService`.
