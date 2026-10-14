# Plano de Implementação: Onda B — Disaster Recovery Avançado (Multi-FTP, Unified Diff Visual, Auditoria SHA-256 & Expurgo)

**Data:** 2026-10-14  
**Referência SDD:** Seção 5.2 de [`docs/SDD.md`](../SDD.md)

---

## 1. Objetivo

Concluir a **Onda B** do Frontend NOC em Flutter (`frontend/`), entregando a gestão completa de Disaster Recovery:
- Cadastro, teste de conectividade real e vínculo por OLT de **Servidores FTP Remotos** (`/api/v1/ftp-servers*`, `/api/v1/olts/{id}/ftp-servers`).
- **Comparador Visual de Configurações (Unified Diff)** entre snapshots com realce de adições/remoções e validação de hash **SHA-256** (`/api/v1/olts/{id}/backups/compare`).
- **Auditoria de Integridade & Detecção de Config Drift** por OLT e para todo o parque (`/api/v1/backups/audit-all`, `/api/v1/olts/{id}/backups/audit`).
- **Backup em Lote (`run-all`) & Políticas de Retenção/Expurgo (`purge` / `purge-all`)**.

---

## 2. Etapas de Execução

1. **Modelos (`frontend/lib/models/backup_model.dart`):**
   - Adicionar `FtpServerModel`, `FtpTestResultModel`, `OltFtpDestinationsModel`, `BackupDiffResultModel`, `BackupAuditReportModel`, `PurgeResultModel` e `BatchBackupResultModel`.
2. **Cliente HTTP (`frontend/lib/core/network/api_client.dart`):**
   - Adicionar os métodos de FTP, comparação Unified Diff, auditoria e expurgo.
3. **Modal de Histórico, Unified Diff Visual & Expurgo por OLT (`frontend/lib/screens/olts/olt_backups_dialog.dart`):**
   - Adicionar disparo de backup imediato, seletor de snapshots Base vs Alvo para Unified Diff colorido, vínculo de servidores FTP da OLT e expurgo individual.
4. **Tela de Gestão de Backups & Multi-FTP (`frontend/lib/screens/backups/backups_screen.dart`):**
   - Evoluir `BackupsScreen` com duas abas (`Snapshots, Drift & Auditoria por OLT` e `Servidores FTP Remotos`) + ações globais (`Backup em Lote`, `Auditar Parque`, `Expurgo Global`).
5. **Testes & Qualidade (`frontend/test/models_test.dart` e `frontend/test/widget_test.dart`):**
   - Adicionar testes unitários para todos os modelos de Disaster Recovery / FTP e widget tests cobrindo `BackupsScreen`, servidores FTP e `OltBackupsDialog` (Unified Diff).
   - Executar `flutter analyze` (0 issues) e `flutter test` (100% pass).
6. **Documentação SDD & Walkthrough:**
   - Atualizar [`docs/SDD.md`](../SDD.md) e [`docs/ROADMAP.md`](../ROADMAP.md) marcando a **Onda B** como concluída (100% das ondas A, B e C finalizadas) e gerar [`docs/planos/2026-10-14_onda_b_disaster_recovery_ftp_diff_walkthrough.md`](2026-10-14_onda_b_disaster_recovery_ftp_diff_walkthrough.md).
