# PRD: API Unificada de Provisionamento Multi-OLT

## 1. Visão do Produto e Problema
Provedores de Internet (ISPs) operam redes com múltiplos fabricantes de OLTs (Intelbras 8820/4840/G16, Huawei MA5800, Fiberhome, Parks). Cada fabricante possui sintaxes de terminal (CLI), protocolos e comportamentos distintos.
Isso gera:
- Dependência de softwares caros de mercado ou de interfaces web lentas.
- Dificuldade de integração direta com ERPs (IXC, MK-Auth, SGP, Voalle, etc.).
- Complexidade para técnicos de campo autorizarem e diagnosticarem ONUs rapidamente.

**Solução:** Uma API REST agnóstica, rápida e segura construída em Python (FastAPI) com o padrão *Driver/Adapter Pattern*, permitindo que qualquer ERP ou técnico via Postman realize o ciclo de vida de provisionamento, backup e diagnóstico das OLTs através de uma interface padronizada.

---

## 2. Personas e Casos de Uso
1. **Sistema ERP de Provedor:**
   - Consome a API REST via chamadas automatizadas quando um contrato é assinado ou alterado.
   - Dispara provisionamento informando apenas serial, porta PON, perfil e VLAN.
2. **Técnico de Campo / NOC (via Postman/cURL):**
   - Lista ONUs desautorizadas conectadas na caixa de atendimento.
   - Realiza o provisionamento manual no ato da instalação.
   - Consulta sinal óptico (dBm) para certificar a qualidade da fibra.
3. **Engenheiro de Redes / SRE:**
   - Dispara backups automatizados das OLTs e faz o download seguro dos arquivos `.cfg` / `.txt`.
   - Consulta o *running-config* ativo de qualquer OLT centralizada.

---

## 3. Escopo Funcional e Operações Suportadas
A plataforma cobre as operações vitais para o ciclo de vida operacional de rede PON:
1. **Visualizar Configurações:** Obter a configuração corrente (`running-config` / TL1) das OLTs cadastradas.
2. **Backup & Disaster Recovery:** Disparar rotinas sob demanda ou periódicas, salvar com integridade SHA-256 e ID **UUIDv7**, auditoria e expurgo automático.
3. **Diagnóstico de Porta e ONU:** Listar ONUs de uma porta PON e consultar sinal óptico e status operacional de uma ONU específica, com links HATEOAS de navegação.
4. **Varredura de Descoberta (Autofind):** Listar ONUs pendentes de autorização (*unconfigured / autofind*).
5. **Provisionamento:** Autorizar ONU na porta com perfil e VLAN.
6. **Desprovisionamento & Cancelamento:** Excluir ONU da OLT e liberar recursos da porta PON (`DELETE`).
7. **Ações Remotas de Assinante:** Reboot remoto OMCI, Suspensão Administrativa (bloqueio por inadimplência) e Reativação / Desbloqueio financeiro (`suspend` / `resume`).
8. **Assistente Zero-Touch Bootstrap:** Geração de scripts oficiais para OLTs novas de fábrica.
9. **ONU como Entidade Autônoma & Auto-Recuperação Reativa (TR-101):** Rastreamento de hardware ancorado ao contrato comercial do ERP. Resolução automática de fusões invertidas em caixas CEO, trocas de CTO ou cutovers de POP com recálculo do Circuit ID Broadband Forum TR-101 e desprovisionamento da posição fantasma antiga.
10. **Linha do Tempo do NOC & Geolocalização GIS:** Linha do tempo global reversa para auditoria matinal de movimentações noturnas e suporte a latitude/longitude para integração geográfica.
11. **Webhooks Criptografados para ERPs (HMAC SHA-256):** Notificações push assíncronas em tempo real com integridade criptográfica para sincronização de novos Circuit IDs e eventos de rede com o ERP.
12. **Autofind Scanner em Segundo Plano:** Worker periódico em background com locks defensivos por OLT, detecção de ONUs virgens e auto-conciliação autônoma contínua.

*Parque de Fabricantes Suportados:*
- **Intelbras:** 8820i / 8820 (Broadcom CLI) e Linha G-Series (G08 / G16).
- **Huawei:** SmartAX MA5800 / MA5608T (VRP CLI).
- **Fiberhome:** AN5516-01 / AN5516-04 / AN5516-06 (TL1 Protocol).
- **V-SOL:** V1600GT / V1600G (CLI).
- **ZTE:** ZXA10 C300 / C320 (ZXROS CLI).

---

## 4. Critérios de Aceite
- [x] Contrato OpenAPI 3.1.0 especificado e validado (`docs/api_contracts/openapi.yaml`).
- [x] Toda entidade e backup identificado por **UUIDv7** (RFC 9562).
- [x] Proteção ativa contra injeção de comandos CLI em todos os parâmetros de entrada.
- [x] Autenticação por token/chave de API em todos os endpoints sensíveis.
- [x] 6 Drivers de fabricantes implementados com parsers e geração de comandos realistas.
- [x] Ciclo de vida completo de ONUs: Descoberta, Provisionamento, Reboot, Suspensão, Reativação e Desprovisionamento.
- [x] Suporte a HATEOAS em todos os endpoints fornecendo transições de estado navegáveis.
- [x] Motor de Auto-Recuperação Reativa de Campo e Circuit ID Broadband Forum TR-101.
- [x] Subsistema de Webhooks com assinatura digital HMAC SHA-256 e execução não-bloqueante.
- [x] Autofind Scanner periódico em background com proteção de concorrência por OLT e endpoints de controle operacional.
- [x] 100% de cobertura de testes unitários automatizados (128 testes passando).
- [x] Pipeline CI/CD GitHub Actions otimizado, sem avisos de depreciação e com limite de tempo e controle de concorrência.
