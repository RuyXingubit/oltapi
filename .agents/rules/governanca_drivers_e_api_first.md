# DIRETRIZ MANDATÓRIA: GOVERNANÇA DE DRIVERS, ORIENTAÇÃO A OBJETOS & ARQUITETURA API-FIRST

Aprovado em 15/09/2026 para blindar o projeto contra regressões, retrabalho e quebra de arquitetura entre sessões.

---

## 1. Desacoplamento Radical Backend x Frontend (API-First)
- O backend FastAPI deve funcionar **exclusivamente como uma API REST JSON**.
- É terminantemente proibido manter arquivos estáticos HTML, CSS, JS ou servir páginas web diretamente a partir do backend (`app/static/`).
- Todo e qualquer contrato de dados e endpoints deve estar 100% documentado e sincronizado com `docs/api_contracts/openapi.yaml`.

---

## 2. Driver Compliance Suite & Orientação a Objetos Pura
- Toda e qualquer OLT adicionada ao sistema **DEVE herdar obrigatoriamente de `BaseOLTDriver`**.
- É **proibido** utilizar `hasattr(driver, ...)` ou condicionais por fabricante (`if olt.vendor == ...`) dentro dos serviços de negócio. A camada de serviço conversa exclusivamente com os métodos polimórficos da interface `BaseOLTDriver`.
- Qualquer novo driver deve ser homologado passando obrigatoriamente por uma suíte de testes de conformidade (`BaseDriverComplianceTest`), cobrindo os seguintes métodos:
  1. `get_running_config(olt)`
  2. `backup_config(olt, ...)`
  3. `get_chassis_interfaces(olt)` (apenas interfaces físicas reais declaradas pelo hardware, sem dados inventados)
  4. `get_onu_details(olt, ...)` (sinais ópticos RX/TX reais e estado operacional)
  5. `provision_onu(olt, req)`
  6. `deprovision_onu(olt, ...)`
  7. `suspend_onu(olt, ...)` (bloqueio administrativo)
  8. `resume_onu(olt, ...)` (desbloqueio administrativo)
  9. `reboot_onu(olt, ...)`
  10. `configure_snmp(olt, ...)`

---

## 3. Zero Dados Falsos e Zero Hardcode
- É estritamente proibido presumir portas, formatos de portas (`gpon 0/1/X`), perfis ou comandos hardcoded no código de serviço ou de cliente.
- Todos os dados exibidos ou utilizados em fluxos operacionais devem ser derivados estritamente do hardware físico ou dos registros persistidos no banco de dados.

---

*Nota: As diretrizes do novo Frontend (Flutter e Design System corporativo) serão consolidadas na fase 2 após o saneamento completo do backend na branch dedicada.*
