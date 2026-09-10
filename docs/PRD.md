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

## 3. Limites do MVP (Foco Estrito)
O MVP cobre estritamente as 5 operações fundamentais:
1. **Visualizar Configurações:** Obter a configuração corrente (`running-config`) das OLTs cadastradas.
2. **Backup de Configurações:** Disparar rotina de backup, salvar localmente com integridade SHA-256 e ID **UUIDv7**, e permitir download via API.
3. **Diagnóstico de Porta e ONU:** Listar ONUs de uma porta PON e consultar sinal óptico e status operacional de uma ONU específica.
4. **Varredura de Descoberta:** Listar ONUs pendentes de autorização (*unconfigured / autofind*).
5. **Provisionamento:** Autorizar ONU na porta com perfil e VLAN.

*Piloto Inicial do MVP:* OLT **Intelbras 8820** (GPON).

---

## 4. Critérios de Aceite
- [x] Contrato OpenAPI 3.1.0 especificado e validado (`docs/api_contracts/openapi.yaml`).
- [x] Toda entidade e backup identificado por **UUIDv7** (RFC 9562).
- [x] Proteção ativa contra injeção de comandos CLI em todos os parâmetros de entrada.
- [x] Autenticação por token/chave de API em todos os endpoints sensíveis.
- [x] Driver da Intelbras 8820 implementado com parser de CLI realistas e desacoplado.
- [x] 100% de cobertura de testes unitários para gerador UUIDv7, sanitizadores de segurança, parsers e endpoints da API.
- [x] Pipeline CI/CD GitHub Actions otimizado, sem avisos de depreciação e com limite de tempo e controle de concorrência.
