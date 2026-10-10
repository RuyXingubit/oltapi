# Relatório de Homologação em Hardware Físico: Parks Fiberlink (Série 10008S / 21000)

Documento oficial de consolidação técnica e operacional da homologação em hardware físico de bancada e análise de tráfego de produção da OLT **Parks Fiberlink 10008S Series 2** (firmware `4.9.3`), validando o driver universal para múltiplos provedores (ISP-agnóstico).

---

## 1. Identificação do Hardware e Ambiente de Bancada

- **Equipamento:** Parks Fiberlink 10008S Series 2
- **Identificação de Hardware:** `CGP.20-0`, Serial `B6CF76`
- **Firmware Homologado:** `4.9.3` (Parks OS baseado em Linux embarcado com CLI proprietária)
- **Hostname de Bancada:** `OLTabacaxi`
- **Topologia de Interfaces:**
  - **Portas GPON:** 8 portas físicas distribuídas em dois módulos: `gpon1/1` a `gpon1/4` e `gpon2/1` a `gpon2/4`.
  - **Portas Uplink Gigabit:** `ge1/0` (Uplink ativo em bancada), `ge2/0` a `ge4/0`.
  - **Porta de Gerência Física (OOB/AUX):** `mgmt` com IP `192.168.1.1/24` (preservada para acesso local e bancada de suporte).
  - **Interfaces SVI (In-Band):** Subinterfaces virtuais de gerência (ex: `mgmt1.2` associada a VLANs de serviço).

---

## 2. Descobertas Críticas do Sistema Operacional & Protocolos (CLI Quirks)

Durante a interação direta com o hardware na bancada, foram catalogadas particularidades mandatórias do Parks OS:

1. **Instabilidade do Daemon SSH (Dropbear Segfault):**
   Ao estabelecer sessão interativa ou disparar comandos via SSH (porta 22), o processo Dropbear do firmware 4.9.3 sofre falha crítica de segmentação (`Aiee, segfault! You should probably report this as a bug to the developer`). O acesso direto e seguro foi consolidado via Telnet (porta 23).
2. **Handshake Mandatório de Telnet:**
   A OLT não envia o prompt de `Username:` de imediato. Ela aguarda um retorno de carro com quebra de linha (`\r\n`) ao exibir o banner:
   ```text
   Press <RETURN> to get started
   ```
   O client canônico `app.core.telnet.TelnetClient` realiza essa negociação automática e filtra bytes de controle IAC (0xFF).
3. **Desativação de Paginação de Terminal:**
   Para comandos de exibição extensos (`show running-config`, `show gpon onu`), a paginação nativa (`--More--`) deve ser suprimida logo após a autenticação executando:
   ```text
   terminal length 0
   ```
4. **Persistência de Memória:**
   Diferente do padrão `write memory`, a Parks adota o comando padrão Cisco clássico:
   ```text
   copy running-config startup-config
   ```

---

## 3. Padrão Canônico de Provisionamento e Ciclo de Vida de ONUs

Com base na engenharia reversa do hardware e no arquivo de backup de produção de referência (`s44olt01_config_13_07_2026.txt`), foram mapeadas e validadas as operações para ambientes multi-fabricante (Huawei, Intelbras, ZTE, Fiberhome, Parks):

### 3.1. Autofind (Detecção de ONUs Não Autorizadas)
- Comando executado: `show gpon onu unconfigured`
- Formato tabular tratado pelo driver:
  ```text
  Interface     Serial            Model
  -----------------------------------------------
  gpon1/1       HWTC073545B7      EG8041X6
  ```

### 3.2. Sequência de Provisionamento Multi-Fabricante
Para provisionar uma nova ONU na porta GPON, a sequência canônica executada dentro do submodo da interface é:
```text
interface gpon1/1
  onu add serial-number HWTC073545B7
  onu HWTC073545B7 alias "CLIENTE_FIBRA_RESIDENCIAL"
  onu HWTC073545B7 ethernet-profile auto-on uni-port 1-4
  onu HWTC073545B7 flow-profile INTERNET_FTTH
  onu HWTC073545B7 iphost 1 ip dhcp
exit
```
- **Habilitação das Portas LAN:** O parâmetro `ethernet-profile auto-on uni-port 1-4` é fundamental para evitar que ONUs de terceiros iniciem com portas Ethernet em estado administrativamente desativado.
- **Gerência IP:** O comando `iphost 1 ip dhcp` instrui a ONU a solicitar IP de gerência via DHCP na VLAN de serviço associada ao perfil.

### 3.3. Suspensão / Bloqueio Administrativo (Blacklist)
A Parks disponibiliza uma mecânica de bloqueio sem desprovisionamento:
- **Bloqueio:** `gpon blacklist serial-number <SERIAL>` (corta o tráfego do assinante mantendo sua configuração na porta PON).
- **Desbloqueio / Reativação:** `no gpon blacklist serial-number <SERIAL>`.

### 3.4. Reinicialização (Reboot) e Desprovisionamento
- **Reboot:** `onu reset <SERIAL>`.
- **Desprovisionamento / Remoção:** `interface gponX/Y` -> `no onu <SERIAL>`.

---

## 4. Telemetria Óptica Real (dBm & RSSI)

O Parks OS separa o diagnóstico em duas métricas complementares:
1. **Atenuação Recebida na ONU (Downstream):**
   - Comando: `show gpon onu <SERIAL> status`
   - Extração via regex: `Power Level\s*:\s*([+-]?\d+\.?\d*)\s*dBm`
2. **Potência Óptica Recebida na OLT (Upstream RSSI):**
   - Comando: `show gpon onu <SERIAL> rssi`
   - Extração via regex: `RSSI Level\s*:\s*([+-]?\d+\.?\d*)\s*dBm`

O driver unifica essas duas leituras no schema padrão `OpticalPowerReadings(rx_power_dbm, olt_rx_power_dbm)`.

---

## 5. Estratégia de Backup Canônico (FTP Nativo + Fallback)

O driver implementa a diretriz mandatória de governança:
1. **Envio Nativo por FTP:**
   Executa o comando de envio da imagem de inicialização diretamente ao servidor FTP configurado:
   ```text
   copy startup-config ftp://<usuario>:<senha>@<host>/<caminho_remoto>
   ```
2. **Fallback Gracioso via Terminal:**
   Se nenhum servidor FTP estiver configurado no `BackupService` ou se houver falha de rede/credenciais no envio, o driver captura automaticamente o `running-config` via terminal com `show running-config`, armazenando o conteúdo criptografado com Fernet (AES-128).

---

## 6. Cobertura de Testes e Validação em Bancada Física

A homologação do driver Parks Fiberlink foi validada tanto em ambiente simulado quanto em bancada física real com tráfego óptico:

### 6.1. Validação em Hardware Físico com ONT Huawei (EG8041X6-10 / HWTC073545B7)
No dia **10/10/2026**, foi realizado o teste completo de ciclo de vida ponta a ponta com equipamento físico:
1. **Provisionamento Completo (`provision_onu`):**
   - Configuração de `serial`, `flow-profile router_vlan621`, `alias CLIENTE_HOMOLOGADO`, portas LAN automáticas (`ethernet-profile auto-on uni-port 1-4`) e `iphost 1 ip dhcp`.
   - A ONT foi ativada com sucesso e removida automaticamente da lista de `unconfigured`.
   - **Telemetria Óptica Operacional Medida:**
     - Downstream RX Power: **`-21.87 dBm`**
     - Upstream RSSI na OLT: **`-21.25 dBm`**
     - Status: `ACTIVE (PROVISIONED)`
2. **Suspensão e Reativação (`suspend_onu` / `resume_onu`):**
   - Inserção na blacklist (`gpon blacklist serial-number hwtc073545b7`) com isolamento instantâneo do enlace.
   - Remoção com `no gpon blacklist serial-number hwtc073545b7`.
3. **Reinicialização Remota (`reboot_onu`):**
   - Disparo de `onu reset hwtc073545b7` na interface `gpon1/1`.
   - Queda física do enlace óptico durante o boot da ONT e retorno automático ao estado `ACTIVE (PROVISIONED)` após conclusão do ciclo OMCI (~35s).
4. **Desprovisionamento e Idempotência (`deprovision_onu`):**
   - Remoção completa via `no onu hwtc073545b7` na interface `gpon1/1`.
   - Reprovisionamento do zero via `provision_onu`, validando que o ciclo completo é 100% resiliente e idempotente.

### 6.2. Suíte Geral do Sistema e Conformidade
- **Suíte de Conformidade (`BaseDriverComplianceTest`):** 36 testes executados cobrindo todos os métodos polimórficos de `BaseOLTDriver` para o Parks Fiberlink.
- **Testes Unitários Dedicados (`test_parks_driver.py`):** 11 testes cobrindo parsing de CLI, leituras ópticas, regex de portas sem espaços e fallback de backup.
- **Suíte Geral do Sistema:** **246 testes aprovados com 100% de sucesso**.
- **Contratos OpenAPI:** 75 endpoints e 96 esquemas sincronizados em `docs/api_contracts/openapi.yaml` e `docs/api_contracts/openapi.json`.
