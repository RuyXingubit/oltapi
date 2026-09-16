# DIRETRIZ MANDATÓRIA: GOVERNANÇA DE DRIVERS, ORIENTAÇÃO A OBJETOS & ARQUITETURA API-FIRST

Aprovado em 15/09/2026 para blindar o projeto contra regressões, retrabalho e quebra de arquitetura entre sessões.

---

## 1. Desacoplamento Radical Backend x Frontend (API-First)
- O backend FastAPI deve funcionar **exclusivamente como uma API REST JSON**.
- É terminantemente proibido manter arquivos estáticos HTML, CSS, JS ou servir páginas web diretamente a partir do backend (`app/static/`).
- Todo e qualquer contrato de dados e endpoints deve estar 100% documentado e sincronizado com `docs/api_contracts/openapi.yaml`.

---

## 2. Driver Compliance Suite, Inversão de Dependência & Zero Código Teórico
- Toda e qualquer OLT adicionada ao sistema **DEVE herdar obrigatoriamente de `BaseOLTDriver`** e se auto-registrar via `@DriverRegistry.register(vendor=..., models=[...])`.
- **Proibição Absoluta de Fabricantes Teóricos:** É terminantemente proibido criar ou manter no código ativo drivers sem equipamento físico de bancada para homologação real. O desenvolvimento é estritamente sob demanda (apenas OLTs reais conectadas e validadas).
- **Isolamento Radical (Ports & Adapters):** Um driver nunca deve importar outro driver. É **terminantemente proibido** utilizar `hasattr(driver, ...)` ou condicionais por fabricante (`if olt.vendor == ...`) dentro dos serviços de negócio. A camada de serviço conversa exclusivamente com os métodos polimórficos da interface `BaseOLTDriver`.
- **Padrão Canônico de Backup:** Todo driver tenta prioritariamente o envio do backup via FTP com a sintaxe CLI nativa do equipamento; caso nenhum FTP esteja disponível ou o comando falhe, o driver DEVE fazer fallback automático para captura do `running-config` pelo terminal (SSH/Telnet).
- Qualquer driver ativo deve ser homologado passando obrigatoriamente pela suíte de testes de conformidade (`BaseDriverComplianceTest`), cobrindo os seguintes métodos contratuais:
  1. `get_running_config(olt)`
  2. `backup_config(olt, ftp_servers=None)` (prioridade FTP nativo + fallback gracioso para terminal)
  3. `get_chassis_interfaces(olt)` (apenas interfaces físicas reais declaradas pelo hardware, sem dados inventados)
  4. `get_onu_details(olt, ...)` (sinais ópticos RX/TX reais e estado operacional)
  5. `provision_onu(olt, req)`
  6. `deprovision_onu(olt, ...)`
  7. `suspend_onu(olt, ...)` (bloqueio administrativo)
  8. `resume_onu(olt, ...)` (desbloqueio administrativo)
  9. `reboot_onu(olt, ...)`
  10. `configure_snmp(olt, ...)`
  11. `list_all_authorized_onus(olt)`
  12. `inspect_management_arch(olt, running_cfg, access_host)`
  13. `execute_wizard_commissioning(olt, req)`

---

## 3. Zero Dados Falsos e Zero Hardcode
- É estritamente proibido presumir portas, formatos de portas (`gpon 0/1/X`), perfis ou comandos hardcoded no código de serviço ou de cliente.
- Proibido gerar strings falsas de firmware ou contagens fictícias de ONUs em fallbacks. Se o equipamento não fornecer o dado, retornar `None` factual.
- Todos os dados exibidos ou utilizados em fluxos operacionais devem ser derivados estritamente do hardware físico ou dos registros persistidos no banco de dados.

---

## 4. Dívida Técnica Mapeada
- **Cadastro de Servidor FTP via Frontend:** A tela/modal de cadastro de servidor FTP no frontend antigo apresenta falhas de submissão e será reimplementada de forma limpa e com tipagem forte no novo Frontend Flutter.

---

*Nota: As diretrizes do novo Frontend (Flutter e Design System corporativo) serão consolidadas na fase 2 após o saneamento completo do backend na branch dedicada.*
