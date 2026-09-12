# Brainstorming v2: Desprovisionamento e Ações Remotas de Suporte (Reboot e Suspensão)

Este documento detalha o design técnico, comandos CLI por fabricante, contratos de API e fluxos HATEOAS para a implementação dos Itens 2 e 3 do Roadmap.

---

## 1. Item 2: Desprovisionamento / Remoção de ONU (`DELETE`)

Quando um cliente encerra o contrato ou troca de endereço, o ERP precisa liberar a porta PON e os recursos da ONU (ID, VLANs, GemPorts) na OLT.

### 1.1 Contrato REST Proposto
- **Rota:** `DELETE /api/v1/olts/{olt_id}/onus/{serial_or_id}`
- **Query Params opcionais:** `?port={port}&onu_id={onu_id}` (caso o driver precise da porta ou ONU-ID diretamente).
- **Código de Sucesso:** `200 OK` (com payload descritivo) ou `204 No Content`. Recomendado `200 OK` com `ONUActionResponse` para manter rastreabilidade e HATEOAS.

### 1.2 Comandos CLI por Fabricante
1. **Intelbras 8820 (Broadcom CLI):**
   ```text
   enable
   config
   interface gpon {port}
   no ont add {onu_id}
   exit
   write
   ```
2. **Intelbras G-Series (G08 / G16):**
   ```text
   enable
   configure terminal
   interface gpon {port}
   no ont {onu_id}
   exit
   write
   ```
3. **Huawei (VRP CLI):**
   ```text
   enable
   config
   interface gpon {frame}/{slot}
   ont delete {port} {onu_id}
   quit
   save
   ```
4. **Fiberhome (TL1):**
   ```text
   DEL-ONT::DEV={olt_ip},FN={frame},SN={slot},PN={port}:CTAG::ONUID={onu_id};
   ```
5. **V-SOL (V1600 Series CLI):**
   ```text
   enable
   configure terminal
   interface gpon 0/{pon}
   no ont {onu_id}
   exit
   write
   ```
6. **ZTE (ZXROS CLI):**
   ```text
   enable
   configure terminal
   interface gpon-olt_{port}
   no onu {onu_id}
   exit
   write
   ```

---

## 2. Item 3: Ações Remotas no Assinante (Reboot e Suspensão)

Reduz drasticamente o custo operacional (OPEX) do provedor ao evitar envio de técnicos a campo para resolver problemas simples de travamento de CPE ou bloqueio de clientes inadimplentes.

### 2.1 Reboot Remoto da ONU
- **Rota:** `POST /api/v1/olts/{olt_id}/onus/{serial_or_id}/reboot`
- **Comandos por Fabricante:**
  - **Intelbras 8820 / G-Series:** `ont reset <port> <onu_id>` / `ont reboot <onu_id>`
  - **Huawei VRP:** `ont reset <port_id> <onu_id>`
  - **Fiberhome TL1:** `RESET-ONT::DEV={ip},FN={fn},SN={sn},PN={pn}:CTAG::ONUID={onu_id};`
  - **V-SOL:** `interface gpon 0/{pon}` -> `ont reset <onu_id>`
  - **ZTE ZXROS:** `reset gpon onu gpon-onu_{port}:{onu_id}`

### 2.2 Suspensão / Bloqueio por Inadimplência (Corte Financeiro)
- **Rotas:**
  - `POST /api/v1/olts/{olt_id}/onus/{serial_or_id}/suspend`
  - `POST /api/v1/olts/{olt_id}/onus/{serial_or_id}/resume`
- **Comportamento:**
  - Desativa administrativamente a interface da ONU ou desativa a GemPort de serviço.
  - **Intelbras / V-SOL:** `ont deactivate <onu_id>` / `ont activate <onu_id>`
  - **Huawei:** `ont deactivate <port_id> <onu_id>` / `ont activate <port_id> <onu_id>`
  - **Fiberhome:** `SET-ONT::...:STATUS=DEACTIVATED`
  - **ZTE:** `onu deactivate <onu_id>` / `onu activate <onu_id>`

---

## 3. Modelo de Resposta Pydantic & HATEOAS

```python
class ONUActionResponse(BaseModel):
    success: bool = True
    action: str = Field(description="Ex: deprovision, reboot, suspend, resume")
    olt_id: str
    serial: str
    port: Optional[str] = None
    onu_id: Optional[int] = None
    message: str
    links: Dict[str, Link] = Field(default_factory=dict, alias="_links", serialization_alias="_links")
    model_config = {"populate_by_name": True}
```

Após desprovisionar:
- Link de retorno para a porta PON (`port_onus`).
- Link para consultar ONUs não autorizadas (`unauthorized_onus`), pois a ONU reiniciará e aparecerá no autofind.

Após reboot:
- Link para consultar o status óptico pós-reboot (`details`).
