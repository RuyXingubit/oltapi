# Plano de Homologação do Fabricante Parks (Série Fiberlink 10008S / 21000)

## 1. Visão Geral e Contexto
O objetivo deste plano é homologar o vendor **Parks** e a família de OLTs **Fiberlink** (especificamente o modelo Fiberlink 10008S Series 2 e compatíveis) no ecossistema OLTAPI.
A homologação foi realizada com acesso direto a hardware de bancada física (`192.168.1.1`) e análise de arquivo de backup de produção de referência (`s44olt01_config_13_07_2026.txt`).
O driver desenvolvido deve ser 100% universal e multi-provedor (ISP-agnóstico), sem amarras ou dados fixos de clientes ou topologias locais.

## 2. Decisões Arquiteturais e Requisitos
1. **Padrão Ports & Adapters (SOLID / BaseOLTDriver):**
   - Criação da classe `ParksFiberlinkDriver` em `app/drivers/parks/parks_fiberlink.py`.
   - Registro automático no `DriverRegistry` via `@DriverRegistry.register(OLTVendor.PARKS)`.
   - Isolamento radical: nenhum acoplamento com outros drivers; comunicação polimórfica com os serviços.
2. **Extração de Telnet Reutilizável:**
   - Extração do cliente Telnet limpo e resiliente para `app.core.telnet.TelnetClient` para uso compartilhado por Fiberhome, Parks e futuros concentradores.
   - Tratamento do handshake inicial de Telnet da Parks (`Press <RETURN> to get started`) e envio de `terminal length 0`.
   - Contorno da falha nativa do SSH Dropbear da Parks (segfault no firmware 4.9.3).
3. **Ciclo de Vida Canônico de ONUs:**
   - Autofind: `show gpon onu unconfigured`.
   - Provisionamento: `onu add`, `alias`, `ethernet-profile auto-on uni-port 1-4`, `flow-profile`, `iphost 1 ip dhcp`.
   - Desprovisionamento: `no onu <serial>`.
   - Suspensão e Reativação: `gpon blacklist serial-number <serial>` e `no gpon blacklist serial-number <serial>`.
   - Reboot: `onu reset <serial>`.
4. **Telemetria Óptica e Portas:**
   - Leitura combinada de potência recebida na ONU (`show gpon onu <serial> status`) e potência recebida na OLT (`show gpon onu <serial> rssi`).
   - Mapeamento determinístico de interfaces GPON e Uplinks GE sem dados inventados.
5. **Padrão Canônico de Backup:**
   - Upload prioritário via FTP nativo (`copy startup-config ftp://...`).
   - Fallback gracioso para captura de terminal via `show running-config` com criptografia Fernet em disco.
6. **Conformidade e Testes Unitários:**
   - Extensão de `BaseDriverComplianceTest` com a classe `TestParksCompliance` em `tests/unit/test_driver_compliance.py`.
   - Criação de suíte de testes unitários dedicada `tests/unit/test_parks_driver.py`.
   - Garantia de zero regressão em 100% dos testes do projeto.
