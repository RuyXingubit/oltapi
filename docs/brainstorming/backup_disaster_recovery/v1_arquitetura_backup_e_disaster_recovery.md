# Módulo de Backup Automatizado & Disaster Recovery (v1)

## 1. Contexto e Objetivos

Em ambientes de provedores de internet (ISPs), a integridade dos equipamentos OLT é crítica para a continuidade das operações de banda larga. Qualquer pane elétrica, queima de controladora ou alteração indevida de configuração pode interromper serviços de centenas ou milhares de clientes.

Este documento estabelece a arquitetura do **Módulo de Backup Automatizado & Disaster Recovery** da OLTAPI, contemplando:
1. **Agendamento em Background (Scheduler):** Rotina periódica não bloqueante para coleta de running-config de todas as OLTs cadastradas ou OLTs selecionadas.
2. **Auditoria de Integridade e Detecção de Config Drift:** Comparação criptográfica baseada em SHA-256 para identificar se houve modificação entre backups sucessivos.
3. **Diff Textual de Configurações (Unified Diff):** Visualização analítica das linhas adicionadas, removidas ou modificadas entre duas versões de backup.
4. **Política de Retenção e Expurgo Automatizado (Retention & Purge):** Limpeza segura de backups antigos (por quantidade máxima ou janela temporal em dias), evitando consumo descontrolado de disco.
5. **Restauração / Disaster Recovery Readiness:** Endpoints e utilitários para entrega estruturada do script de restauração rápida.

---

## 2. Arquitetura do Módulo

```
   ┌────────────────────────────────────────────────────────┐
   │             FastAPI Scheduler / BackgroundTask         │
   │           (Cron periódico / Execução Programada)       │
   └───────────────────────────┬────────────────────────────┘
                               │
                               ▼
               ┌───────────────────────────────┐
               │    BackupSchedulerService     │
               └───────────────┬───────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        ▼                                             ▼
┌───────────────┐                             ┌───────────────┐
│ DriverFactory │                             │ BackupStorage │
└───────┬───────┘                             └───────┬───────┘
        │ Coleta running-config via CLI/TL1           │ Salva .cfg (UUIDv7)
        ▼                                             │ Hash SHA-256
 ┌─────────────┐                                      │ Expurga antigos
 │ OLT Física  │                                      │ Calcula diff
 └─────────────┘                                      ▼
                                            ┌───────────────────┐
                                            │ /data/backups/    │
                                            │   {olt_id}/       │
                                            │ backups.json      │
                                            └───────────────────┘
```

---

## 3. Modelo de Dados

### 3.1 `BackupDiffResult`
- `olt_id`: UUIDv7 da OLT
- `base_backup_id`: UUIDv7 do backup base (anterior)
- `target_backup_id`: UUIDv7 do backup alvo (mais recente)
- `identical`: bool (True se os hashes SHA-256 forem rigorosamente iguais)
- `base_sha256`: Hash do backup base
- `target_sha256`: Hash do backup alvo
- `diff_lines`: List[str] (saída unificada padrão `unified_diff`)
- `additions_count`: int
- `deletions_count`: int

### 3.2 `BackupAuditReport`
- `olt_id`: UUIDv7 da OLT
- `olt_name`: Nome da OLT
- `total_backups`: Quantidade total armazenada
- `total_bytes`: Espaço total consumido em bytes
- `latest_backup`: Optional[BackupMetadata]
- `previous_backup`: Optional[BackupMetadata]
- `has_changed`: bool (se o último difere do penúltimo)
- `last_backup_at`: Optional[datetime]

### 3.3 `PurgePolicy`
- `max_backups_per_olt`: int (ex: 30)
- `max_age_days`: int (ex: 60)

---

## 4. Endpoints REST da API

1. `POST /api/v1/backups/run-all`:
   - Dispara imediatamente o ciclo de backup para todas as OLTs cadastradas (ou apenas ativas) em background.
2. `GET /api/v1/olts/{olt_id}/backups/audit`:
   - Retorna o status de auditoria de integridade da OLT (último backup, penúltimo, status de drift e espaço ocupado).
3. `GET /api/v1/olts/{olt_id}/backups/compare`:
   - Parâmetros: `base_id` e `target_id` (opcionais, default: compara os 2 mais recentes).
   - Retorna o `BackupDiffResult` com os hashes e linhas alteradas.
4. `POST /api/v1/olts/{olt_id}/backups/purge`:
   - Executa a política de expurgo manual ou personalizada, retornando a lista de backups removidos e espaço liberado.
5. `POST /api/v1/backups/purge-all`:
   - Executa a limpeza em todas as OLTs do inventário.
