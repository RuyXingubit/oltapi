import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/backup_model.dart';
import '../../models/olt_model.dart';
import '../../providers/settings_provider.dart';

class OltBackupsDialog extends StatefulWidget {
  final OltModel olt;

  const OltBackupsDialog({super.key, required this.olt});

  @override
  State<OltBackupsDialog> createState() => _OltBackupsDialogState();
}

class _OltBackupsDialogState extends State<OltBackupsDialog> {
  List<BackupModel> _backups = [];
  bool _isLoading = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadBackups();
  }

  Future<void> _loadBackups() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final settings = context.read<SettingsProvider>();
    try {
      final backups = await settings.apiClient.getOltBackups(widget.olt.id);
      if (mounted) {
        setState(() {
          _backups = backups;
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

  Future<void> _viewBackupContent(BackupModel backup) async {
    final settings = context.read<SettingsProvider>();

    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder<String>(
        future: settings.apiClient.downloadBackupText(widget.olt.id, backup.backupId),
        builder: (context, snapshot) {
          return AlertDialog(
            title: Text('Backup: ${backup.filename}'),
            content: SizedBox(
              width: 700,
              height: 450,
              child: snapshot.connectionState == ConnectionState.waiting
                  ? const Center(child: CircularProgressIndicator(color: AppColors.primaryLight))
                  : snapshot.hasError
                      ? Center(child: Text('Erro: ${snapshot.error}', style: const TextStyle(color: AppColors.statusDanger)))
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
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Configuração copiada para a área de transferência!')),
                    );
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

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.surfaceBorder, width: 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 800, maxHeight: 600),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: const Icon(Icons.history, color: AppColors.primaryLight, size: 22),
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Histórico de Backups - ${widget.olt.name}',
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                          ),
                          Text(
                            '${widget.olt.vendor.toUpperCase()} • ${widget.olt.host}',
                            style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                          ),
                        ],
                      ),
                    ],
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppColors.textSecondary, size: 20),
                    onPressed: () => Navigator.of(context).pop(),
                    splashRadius: 20,
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Conteúdo
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator(color: AppColors.primaryLight))
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
                                      color: AppColors.textMuted.withValues(alpha: 0.5),
                                    ),
                                    const SizedBox(height: 12),
                                    const Text(
                                      'Nenhum backup encontrado para esta OLT.',
                                      style: TextStyle(color: AppColors.textSecondary),
                                    ),
                                  ],
                                ),
                              )
                            : SingleChildScrollView(
                                child: ConstrainedBox(
                                  constraints: const BoxConstraints(minWidth: 700),
                                  child: DataTable(
                                    columns: const [
                                      DataColumn(label: Text('DATA & HORA')),
                                      DataColumn(label: Text('ARQUIVO (.CFG)')),
                                      DataColumn(label: Text('TAMANHO')),
                                      DataColumn(label: Text('HASH SHA-256')),
                                      DataColumn(label: Text('AÇÃO')),
                                    ],
                                    rows: _backups.map((backup) {
                                      final dateFormat = DateFormat('dd/MM/yyyy HH:mm');
                                      final dateStr = backup.createdAt != null
                                          ? dateFormat.format(backup.createdAt!.toLocal())
                                          : 'N/A';

                                      return DataRow(
                                        cells: [
                                          DataCell(Text(dateStr, style: const TextStyle(fontSize: 13))),
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
                                              constraints: const BoxConstraints(maxWidth: 120),
                                              child: Text(
                                                backup.sha256Hash.substring(0, 12),
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
                                            OutlinedButton.icon(
                                              style: OutlinedButton.styleFrom(
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 8, vertical: 4),
                                              ),
                                              onPressed: () => _viewBackupContent(backup),
                                              icon: const Icon(Icons.remove_red_eye_outlined, size: 14),
                                              label: const Text('Ver Config', style: TextStyle(fontSize: 11)),
                                            ),
                                          ),
                                        ],
                                      );
                                    }).toList(),
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
