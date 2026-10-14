import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/backup_model.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';

class OltBackupsDialog extends StatefulWidget {
  final OltModel olt;

  const OltBackupsDialog({super.key, required this.olt});

  @override
  State<OltBackupsDialog> createState() => _OltBackupsDialogState();
}

class _OltBackupsDialogState extends State<OltBackupsDialog> {
  List<BackupModel> _backups = [];
  BackupAuditReportModel? _auditReport;
  OltFtpDestinationsModel? _ftpDestinations;
  bool _isLoading = true;
  bool _isTriggering = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadBackupsAndAudit();
  }

  Future<void> _loadBackupsAndAudit() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final api = context.read<AppState>().apiClient;
    try {
      final backups = await api.getOltBackups(widget.olt.id);
      BackupAuditReportModel? audit;
      OltFtpDestinationsModel? ftpDest;
      try {
        audit = await api.auditOltBackups(widget.olt.id);
      } catch (_) {}
      try {
        ftpDest = await api.getOltFtpDestinations(widget.olt.id);
      } catch (_) {}
      if (mounted) {
        setState(() {
          _backups = backups;
          _auditReport = audit;
          _ftpDestinations = ftpDest;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? AppColors.statusDanger : AppColors.statusOnline,
      ),
    );
  }

  Future<void> _handleTriggerBackup() async {
    setState(() => _isTriggering = true);
    final api = context.read<AppState>().apiClient;
    try {
      final created = await api.triggerOltBackup(widget.olt.id);
      if (!mounted) return;
      _showSnack('Snapshot ${created.filename} coletado (${created.formattedSize}).');
      await _loadBackupsAndAudit();
    } catch (e) {
      _showSnack('Falha ao coletar backup: $e', isError: true);
    } finally {
      if (mounted) setState(() => _isTriggering = false);
    }
  }

  Future<void> _viewBackupContent(BackupModel backup) async {
    final settings = context.read<AppState>();

    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder<String>(
        future: settings.apiClient.downloadBackupText(widget.olt.id, backup.backupId),
        builder: (context, snapshot) {
          return AlertDialog(
            backgroundColor: AppColors.surface,
            title: Text(
              'Backup: ${backup.filename}',
              style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
            ),
            content: SizedBox(
              width: 720,
              height: 460,
              child: snapshot.connectionState == ConnectionState.waiting
                  ? const Center(
                      child: CircularProgressIndicator(color: AppColors.primaryLight),
                    )
                  : snapshot.hasError
                      ? Center(
                          child: Text(
                            'Erro: ${snapshot.error}',
                            style: const TextStyle(color: AppColors.statusDanger),
                          ),
                        )
                      : SingleChildScrollView(
                          child: SelectableText(
                            snapshot.data ?? 'Vazio',
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                              color: AppColors.textPrimary,
                            ),
                          ),
                        ),
            ),
            actions: [
              if (snapshot.hasData)
                TextButton.icon(
                  icon: const Icon(Icons.copy, size: 16),
                  label: const Text('Copiar'),
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: snapshot.data!));
                    _showSnack('Configuração copiada para a área de transferência!');
                  },
                ),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Fechar'),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _showUnifiedDiffModal({
    String? initialBaseId,
    String? initialTargetId,
  }) async {
    if (_backups.length < 2 && initialBaseId == null && initialTargetId == null) {
      _showSnack(
        'São necessários pelo menos 2 snapshots para executar o comparador Unified Diff.',
        isError: true,
      );
      return;
    }

    String? baseId = initialBaseId ??
        (_backups.length >= 2 ? _backups[1].backupId : _backups.firstOrNull?.backupId);
    String? targetId = initialTargetId ?? _backups.firstOrNull?.backupId;
    BackupDiffResultModel? diffResult;
    bool loadingDiff = true;
    String? diffError;

    final api = context.read<AppState>().apiClient;

    Future<void> fetchDiff(StateSetter setModalState) async {
      setModalState(() {
        loadingDiff = true;
        diffError = null;
      });
      try {
        final res = await api.compareOltBackups(
          widget.olt.id,
          baseId: baseId,
          targetId: targetId,
        );
        setModalState(() {
          diffResult = res;
          loadingDiff = false;
        });
      } catch (e) {
        setModalState(() {
          diffError = e.toString();
          loadingDiff = false;
        });
      }
    }

    await showDialog<void>(
      context: context,
      builder: (ctx) {
        bool initialized = false;
        return StatefulBuilder(
          builder: (ctx, setModalState) {
            if (!initialized) {
              initialized = true;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                fetchDiff(setModalState);
              });
            }

            return AlertDialog(
              backgroundColor: AppColors.surface,
              title: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Flexible(
                    child: Text(
                      'Comparador Unified Diff • ${widget.olt.name}',
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  if (diffResult != null)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: (diffResult!.identical
                                ? AppColors.statusOnline
                                : AppColors.statusWarning)
                            .withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        diffResult!.identical
                            ? 'IDÊNTICOS (SHA-256 IGUAL)'
                            : 'DRIFT (+${diffResult!.additionsCount} / -${diffResult!.deletionsCount})',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: diffResult!.identical
                              ? AppColors.statusOnline
                              : AppColors.statusWarning,
                        ),
                      ),
                    ),
                ],
              ),
              content: SizedBox(
                width: 820,
                height: 520,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (_backups.length >= 2)
                      Wrap(
                        spacing: 12,
                        runSpacing: 8,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          SizedBox(
                            width: 300,
                            child: DropdownButtonFormField<String>(
                              isExpanded: true,
                              initialValue: baseId,
                              dropdownColor: AppColors.surface,
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 12,
                              ),
                              decoration: const InputDecoration(
                                isDense: true,
                                labelText: 'Snapshot Base (Anterior)',
                              ),
                              items: _backups
                                  .map(
                                    (b) => DropdownMenuItem(
                                      value: b.backupId,
                                      child: Text(
                                        b.filename,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  )
                                  .toList(),
                              onChanged: (v) {
                                baseId = v;
                              },
                            ),
                          ),
                          SizedBox(
                            width: 300,
                            child: DropdownButtonFormField<String>(
                              isExpanded: true,
                              initialValue: targetId,
                              dropdownColor: AppColors.surface,
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 12,
                              ),
                              decoration: const InputDecoration(
                                isDense: true,
                                labelText: 'Snapshot Alvo (Recente)',
                              ),
                              items: _backups
                                  .map(
                                    (b) => DropdownMenuItem(
                                      value: b.backupId,
                                      child: Text(
                                        b.filename,
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  )
                                  .toList(),
                              onChanged: (v) {
                                targetId = v;
                              },
                            ),
                          ),
                          ElevatedButton.icon(
                            onPressed:
                                loadingDiff ? null : () => fetchDiff(setModalState),
                            icon: const Icon(Icons.compare_arrows, size: 16),
                            label: const Text('Comparar'),
                          ),
                        ],
                      ),
                    const SizedBox(height: 12),
                    Expanded(
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppColors.codeBackground,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppColors.surfaceBorder),
                        ),
                        child: loadingDiff
                            ? const Center(child: CircularProgressIndicator())
                            : diffError != null
                                ? Center(
                                    child: Text(
                                      diffError!,
                                      style: const TextStyle(
                                        color: AppColors.statusDanger,
                                      ),
                                    ),
                                  )
                                : diffResult == null || diffResult!.identical
                                    ? const Center(
                                        child: Text(
                                          'Nenhuma divergência entre os snapshots selecionados (Hashes SHA-256 idênticos).',
                                          style: TextStyle(
                                            color: AppColors.statusOnline,
                                            fontSize: 13,
                                          ),
                                        ),
                                      )
                                    : ListView.builder(
                                        itemCount: diffResult!.diffLines.length,
                                        itemBuilder: (ctx, idx) {
                                          final line = diffResult!.diffLines[idx];
                                          Color lineColor = AppColors.textPrimary;
                                          Color? bgColor;
                                          if (line.startsWith('+') &&
                                              !line.startsWith('+++')) {
                                            lineColor = AppColors.statusOnline;
                                            bgColor = AppColors.statusOnline
                                                .withValues(alpha: 0.08);
                                          } else if (line.startsWith('-') &&
                                              !line.startsWith('---')) {
                                            lineColor = AppColors.statusDanger;
                                            bgColor = AppColors.statusDanger
                                                .withValues(alpha: 0.08);
                                          } else if (line.startsWith('@@')) {
                                            lineColor = AppColors.accentCyan;
                                          }
                                          return Container(
                                            color: bgColor,
                                            padding: const EdgeInsets.symmetric(
                                              vertical: 1,
                                              horizontal: 4,
                                            ),
                                            child: SelectableText(
                                              line,
                                              style: TextStyle(
                                                fontFamily: 'monospace',
                                                fontSize: 12,
                                                color: lineColor,
                                              ),
                                            ),
                                          );
                                        },
                                      ),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Fechar'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _showPurgeOltModal() async {
    final maxCountCtrl = TextEditingController(text: '30');
    final maxDaysCtrl = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Text(
          'Política de Expurgo • ${widget.olt.name}',
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
        ),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: maxCountCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: const InputDecoration(
                  labelText: 'Máximo de Backups Retidos por OLT *',
                  hintText: '30',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: maxDaysCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: const InputDecoration(
                  labelText: 'Idade Máxima em Dias (Opcional)',
                  hintText: 'Ex: 90',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Aplicar Expurgo'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    final maxCount = int.tryParse(maxCountCtrl.text.trim()) ?? 30;
    final maxDays = int.tryParse(maxDaysCtrl.text.trim());

    try {
      final res = await context.read<AppState>().apiClient.purgeOltBackups(
            widget.olt.id,
            maxBackupsPerOlt: maxCount,
            maxAgeDays: maxDays,
          );
      if (!mounted) return;
      _showSnack(
        'Expurgo concluído: ${res.deletedCount} removidos (${res.formattedFreedBytes} liberados), ${res.remainingCount} retidos.',
      );
      await _loadBackupsAndAudit();
    } catch (e) {
      _showSnack('Erro ao expurgar backups: $e', isError: true);
    }
  }

  Future<void> _showBindFtpModal() async {
    final api = context.read<AppState>().apiClient;
    List<FtpServerModel> allServers = [];
    try {
      allServers = await api.getFtpServers();
    } catch (e) {
      _showSnack('Erro ao listar servidores FTP: $e', isError: true);
      return;
    }
    if (!mounted) return;

    final selectedIds = <String>{
      ...?_ftpDestinations?.specificDestinations.map((s) => s.id),
    };

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: Text(
            'Destinos FTP • ${widget.olt.name}',
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 460,
            child: allServers.isEmpty
                ? const Text(
                    'Nenhum servidor FTP cadastrado. Cadastre servidores FTP na tela de Gestão de Backups.',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  )
                : SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Text(
                          'Selecione os servidores FTP dedicados a esta OLT (servidores marcados como Global Default recebem cópia automaticamente):',
                          style: TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12,
                          ),
                        ),
                        const SizedBox(height: 12),
                        ...allServers.map((srv) {
                          final checked = selectedIds.contains(srv.id);
                          return CheckboxListTile(
                            value: checked,
                            dense: true,
                            title: Text(
                              '${srv.name} (${srv.host}:${srv.port})',
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 13,
                              ),
                            ),
                            subtitle: Text(
                              'Path: ${srv.basePath}${srv.isGlobalDefault ? " • GLOBAL DEFAULT" : ""}',
                              style: const TextStyle(
                                color: AppColors.textMuted,
                                fontSize: 11,
                              ),
                            ),
                            onChanged: (val) {
                              setModalState(() {
                                if (val == true) {
                                  selectedIds.add(srv.id);
                                } else {
                                  selectedIds.remove(srv.id);
                                }
                              });
                            },
                          );
                        }),
                      ],
                    ),
                  ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            if (allServers.isNotEmpty)
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Salvar Vínculos FTP'),
              ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    try {
      final updated = await api.bindOltFtpServers(
        widget.olt.id,
        selectedIds.toList(),
      );
      if (!mounted) return;
      setState(() => _ftpDestinations = updated);
      _showSnack(
        'Vínculos FTP atualizados (${updated.effectiveDestinations.length} destino(s) efetivo(s)).',
      );
    } catch (e) {
      _showSnack('Erro ao vincular servidores FTP: $e', isError: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasDrift = _auditReport?.hasChanged ?? false;
    final effectiveFtps = _ftpDestinations?.effectiveDestinations ?? const [];

    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.surfaceBorder, width: 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 920, maxHeight: 660),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Wrap(
                spacing: 12,
                runSpacing: 10,
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(
                          Icons.history,
                          color: AppColors.primaryLight,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Flexible(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Histórico de Backups - ${widget.olt.name}',
                              style: const TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                            Text(
                              '${widget.olt.vendor.toUpperCase()} • ${widget.olt.host} • Destinos FTP Efetivos: ${effectiveFtps.length}',
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.textSecondary,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ],
                        ),
                      ),
                      if (_auditReport != null) ...[
                        const SizedBox(width: 10),
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: (hasDrift
                                    ? AppColors.statusWarning
                                    : AppColors.statusOnline)
                                .withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            hasDrift ? 'CONFIG DRIFT DETECTADO' : 'ÍNTEGRO (SEM DRIFT)',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.bold,
                              color: hasDrift
                                  ? AppColors.statusWarning
                                  : AppColors.statusOnline,
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      OutlinedButton.icon(
                        onPressed: _showBindFtpModal,
                        icon: const Icon(Icons.cloud_upload_outlined, size: 15),
                        label: const Text('Destinos FTP'),
                      ),
                      OutlinedButton.icon(
                        onPressed: () => _showUnifiedDiffModal(),
                        icon: const Icon(Icons.compare_arrows, size: 15),
                        label: const Text('Unified Diff'),
                      ),
                      OutlinedButton.icon(
                        onPressed: _showPurgeOltModal,
                        icon: const Icon(Icons.cleaning_services_outlined, size: 15),
                        label: const Text('Expurgar'),
                      ),
                      ElevatedButton.icon(
                        onPressed: _isTriggering ? null : _handleTriggerBackup,
                        icon: const Icon(Icons.save_alt, size: 15),
                        label: Text(
                          _isTriggering ? 'Coletando...' : 'Coletar Agora',
                        ),
                      ),
                      IconButton(
                        icon: const Icon(
                          Icons.close,
                          color: AppColors.textSecondary,
                          size: 20,
                        ),
                        onPressed: () => Navigator.of(context).pop(),
                        splashRadius: 20,
                      ),
                    ],
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Conteúdo
              Expanded(
                child: _isLoading
                    ? const Center(
                        child: CircularProgressIndicator(
                          color: AppColors.primaryLight,
                        ),
                      )
                    : _errorMessage != null
                        ? Center(
                            child: Text(
                              _errorMessage!,
                              style: const TextStyle(color: AppColors.statusDanger),
                            ),
                          )
                        : _backups.isEmpty
                            ? Center(
                                child: Column(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Icon(
                                      Icons.cloud_off_outlined,
                                      size: 48,
                                      color: AppColors.textMuted
                                          .withValues(alpha: 0.5),
                                    ),
                                    const SizedBox(height: 12),
                                    const Text(
                                      'Nenhum backup encontrado para esta OLT.',
                                      style: TextStyle(
                                        color: AppColors.textSecondary,
                                      ),
                                    ),
                                  ],
                                ),
                              )
                            : SingleChildScrollView(
                                child: SingleChildScrollView(
                                  scrollDirection: Axis.horizontal,
                                  child: ConstrainedBox(
                                    constraints: const BoxConstraints(minWidth: 760),
                                    child: DataTable(
                                      columns: const [
                                        DataColumn(label: Text('DATA & HORA')),
                                        DataColumn(label: Text('ARQUIVO (.CFG)')),
                                        DataColumn(label: Text('TAMANHO')),
                                        DataColumn(label: Text('HASH SHA-256')),
                                        DataColumn(label: Text('AÇÕES')),
                                      ],
                                      rows: _backups.map((backup) {
                                        final dateFormat =
                                            DateFormat('dd/MM/yyyy HH:mm');
                                        final dateStr = backup.createdAt != null
                                            ? dateFormat
                                                .format(backup.createdAt!.toLocal())
                                            : 'N/A';
                                        final hashPreview =
                                            backup.sha256Hash.length >= 12
                                                ? backup.sha256Hash.substring(0, 12)
                                                : backup.sha256Hash;

                                        return DataRow(
                                          cells: [
                                            DataCell(
                                              Text(
                                                dateStr,
                                                style: const TextStyle(fontSize: 13),
                                              ),
                                            ),
                                            DataCell(
                                              Text(
                                                backup.filename,
                                                style: const TextStyle(
                                                  fontFamily: 'monospace',
                                                  fontSize: 12,
                                                  color: AppColors.textPrimary,
                                                ),
                                              ),
                                            ),
                                            DataCell(
                                              Text(
                                                backup.formattedSize,
                                                style: const TextStyle(
                                                  color: AppColors.accentCyan,
                                                  fontWeight: FontWeight.w600,
                                                ),
                                              ),
                                            ),
                                            DataCell(
                                              ConstrainedBox(
                                                constraints: const BoxConstraints(
                                                  maxWidth: 120,
                                                ),
                                                child: Text(
                                                  hashPreview,
                                                  style: const TextStyle(
                                                    fontFamily: 'monospace',
                                                    fontSize: 11,
                                                    color: AppColors.textMuted,
                                                  ),
                                                  overflow: TextOverflow.ellipsis,
                                                ),
                                              ),
                                            ),
                                            DataCell(
                                              Row(
                                                mainAxisSize: MainAxisSize.min,
                                                children: [
                                                  OutlinedButton.icon(
                                                    style: OutlinedButton.styleFrom(
                                                      padding:
                                                          const EdgeInsets.symmetric(
                                                        horizontal: 8,
                                                        vertical: 4,
                                                      ),
                                                    ),
                                                    onPressed: () =>
                                                        _viewBackupContent(backup),
                                                    icon: const Icon(
                                                      Icons.remove_red_eye_outlined,
                                                      size: 14,
                                                    ),
                                                    label: const Text(
                                                      'Ver Config',
                                                      style: TextStyle(fontSize: 11),
                                                    ),
                                                  ),
                                                  const SizedBox(width: 6),
                                                  OutlinedButton.icon(
                                                    style: OutlinedButton.styleFrom(
                                                      padding:
                                                          const EdgeInsets.symmetric(
                                                        horizontal: 8,
                                                        vertical: 4,
                                                      ),
                                                    ),
                                                    onPressed: () =>
                                                        _showUnifiedDiffModal(
                                                      initialTargetId:
                                                          backup.backupId,
                                                    ),
                                                    icon: const Icon(
                                                      Icons.difference_outlined,
                                                      size: 14,
                                                    ),
                                                    label: const Text(
                                                      'Diff',
                                                      style: TextStyle(fontSize: 11),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          ],
                                        );
                                      }).toList(),
                                    ),
                                  ),
                                ),
                              ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
