# Walkthrough — Onda B: Disaster Recovery Avançado (Multi-FTP, Unified Diff Visual, Auditoria SHA-256 & Expurgo)

**Data:** 2026-10-14
**Status:** Concluído (100% de Paridade entre Backend e Frontend nas Ondas A, B e C)

---

## 1. Resumo das Entregas

Com a conclusão da **Onda B**, todas as 3 ondas de evolução do Frontend NOC em Flutter especificadas no [`docs/SDD.md`](file:///Volumes/240/Code/oltapi/docs/SDD.md) (**Onda A**, **Onda B** e **Onda C**) estão 100% implementadas, testadas e homologadas contra os contratos reais do Backend FastAPI (`app/api/v1/`).

1. **Modelos de Domínio de Disaster Recovery & Multi-FTP ([`backup_model.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/models/backup_model.dart)):**
   - `FtpServerModel`: Repositório FTP remoto (`id`, `name`, `host`, `port`, `username`, `basePath`, `isGlobalDefault`, `isActive`).
   - `FtpTestResultModel`: Diagnóstico de conectividade e escrita real (`success`, `message`, `banner`, `workingDirectory`, `latencyMs`).
   - `OltFtpDestinationsModel`: Destinos FTP específicos, globais e efetivos vinculados a uma OLT.
   - `BackupDiffResultModel`: Comparação Unified Diff entre snapshots (`identical`, `baseSha256`, `targetSha256`, `diffLines`, `additionsCount`, `deletionsCount`).
   - `BackupAuditReportModel`: Auditoria de integridade SHA-256 e detecção de Configuration Drift (`totalBackups`, `totalBytes`, `hasChanged`, `lastBackupAt`).
   - `PurgeResultModel` & `BatchBackupResultModel`: Resultados de políticas de retenção/expurgo e coleta em lote (`run-all`).

2. **Cliente HTTP REST ([`api_client.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/core/network/api_client.dart)):**
   - Integração de 13 operações REST de Disaster Recovery e FTP:
     - `auditOltBackups`, `compareOltBackups`, `purgeOltBackups`
     - `runAllBackups`, `auditAllBackups`, `purgeAllBackups`
     - `getFtpServers`, `createFtpServer`, `updateFtpServer`, `deleteFtpServer`, `testFtpServer`
     - `getOltFtpDestinations`, `bindOltFtpServers`

3. **Modal de Backups, Unified Diff & Destinos FTP por OLT ([`olt_backups_dialog.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/olts/olt_backups_dialog.dart)):**
   - Badge de integridade em tempo real (`CONFIG DRIFT DETECTADO` vs `ÍNTEGRO (SEM DRIFT)`).
   - Comparador Visual **Unified Diff** com realce sintático (`+` adições em verde, `-` remoções em vermelho, `@@` hunks em ciano) e seleção de snapshots Base e Alvo com `isExpanded: true`.
   - Vínculo de servidores FTP específicos por OLT (`Destinos FTP`) e expurgo sob demanda (`Expurgar`).

4. **Central de Disaster Recovery & Servidores FTP Remotos ([`backups_screen.dart`](file:///Volumes/240/Code/oltapi/frontend/lib/screens/backups/backups_screen.dart)):**
   - Ações globais no topo: `Auditar Parque (SHA-256)`, `Expurgo Global` e `Backup em Lote (Run All)`.
   - **Sub-aba 1 — Snapshots, Drift & Auditoria por OLT:** Cards de OLTs enriquecidos com status de Configuration Drift, contagem de snapshots, volume ocupado e atalho direto para o modal de Backups/Diff/FTP.
   - **Sub-aba 2 — Servidores FTP Remotos:** CRUD completo de servidores FTP com badge `GLOBAL DEFAULT`, botão `Testar FTP` exibindo latência em ms, diretório `PWD` e banner do servidor FTP.

---

## 2. Validação & Testes Automatizados

- `flutter analyze`: **0 issues found**.
- `flutter test`: **21/21 testes passando (100%)**, cobrindo:
  - Deserialização de todos os modelos da Onda B em [`models_test.dart`](file:///Volumes/240/Code/oltapi/frontend/test/models_test.dart).
  - Renderização sem overflow de `BackupsScreen`, `OltBackupsDialog` e modal `Comparador Unified Diff` em [`widget_test.dart`](file:///Volumes/240/Code/oltapi/frontend/test/widget_test.dart).
