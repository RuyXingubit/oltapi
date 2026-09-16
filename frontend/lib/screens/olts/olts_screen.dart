import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';
import '../../providers/settings_provider.dart';
import 'olt_backups_dialog.dart';

class OltsScreen extends StatefulWidget {
  const OltsScreen({super.key});

  @override
  State<OltsScreen> createState() => _OltsScreenState();
}

class _OltsScreenState extends State<OltsScreen> {
  final Map<String, bool> _isTestingConnection = {};
  final Map<String, String> _connectionResults = {};
  final Map<String, bool> _isBackingUp = {};

  Future<void> _testConnection(OltModel olt) async {
    setState(() => _isTestingConnection[olt.id] = true);
    final settings = context.read<SettingsProvider>();

    try {
      final res = await settings.apiClient.testOltConnection(olt.id);
      if (mounted) {
        setState(() {
          _isTestingConnection[olt.id] = false;
          _connectionResults[olt.id] = res.reachable
              ? 'OK (${res.latencyMs?.toStringAsFixed(1) ?? "--"} ms)'
              : 'Falha: ${res.message}';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isTestingConnection[olt.id] = false;
          _connectionResults[olt.id] = 'Erro: $e';
        });
      }
    }
  }

  Future<void> _triggerBackup(OltModel olt) async {
    setState(() => _isBackingUp[olt.id] = true);
    final appState = context.read<AppState>();

    final backup = await appState.triggerBackup(olt.id);
    if (!mounted) return;
    setState(() => _isBackingUp[olt.id] = false);

    if (backup != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusOnline,
          content: Text(
            'Backup de ${olt.name} concluído com sucesso! (${backup.formattedSize})',
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text(appState.errorMessage ?? 'Falha ao realizar backup'),
        ),
      );
    }
  }

  void _showBackups(OltModel olt) {
    showDialog(
      context: context,
      builder: (ctx) => OltBackupsDialog(olt: olt),
    );
  }

  Future<void> _showLiveConfig(OltModel olt) async {
    final settings = context.read<SettingsProvider>();

    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder<String>(
        future: settings.apiClient.getOltConfig(olt.id),
        builder: (context, snapshot) {
          return AlertDialog(
            title: Text('Running-Config: ${olt.name}'),
            content: SizedBox(
              width: 750,
              height: 480,
              child: snapshot.connectionState == ConnectionState.waiting
                  ? const Center(child: CircularProgressIndicator(color: AppColors.primaryLight))
                  : snapshot.hasError
                      ? Center(
                          child: Text(
                            'Erro ao obter config: ${snapshot.error}',
                            style: const TextStyle(color: AppColors.statusDanger),
                          ),
                        )
                      : SingleChildScrollView(
                          child: SelectableText(
                            snapshot.data ?? 'Sem conteúdo',
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
                      const SnackBar(content: Text('Configuração copiada!')),
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
    final appState = context.watch<AppState>();
    final olts = appState.olts;
    final isLoading = appState.isLoadingOlts;

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Text(
                        'OLTs & Gestão de Backups',
                        style: TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceHover,
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppColors.surfaceBorder),
                        ),
                        child: Text(
                          '${olts.length} registradas',
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Hardware físico ativo e políticas de backup automatizadas',
                    style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: isLoading ? null : () => appState.loadOlts(),
                icon: isLoading
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.refresh, size: 16),
                label: const Text('Recarregar OLTs'),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Tabela ou Lista de OLTs
          Expanded(
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.surfaceBorder),
              ),
              child: isLoading
                  ? const Center(child: CircularProgressIndicator(color: AppColors.primaryLight))
                  : olts.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.developer_board_off,
                                size: 54,
                                color: AppColors.textMuted.withValues(alpha: 0.5),
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'Nenhuma OLT cadastrada',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                              const SizedBox(height: 6),
                              const Text(
                                'Cadastre uma OLT via API para iniciar o gerenciamento.',
                                style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                              ),
                            ],
                          ),
                        )
                      : SingleChildScrollView(
                          scrollDirection: Axis.vertical,
                          child: SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(minWidth: 950),
                              child: DataTable(
                                columns: const [
                                  DataColumn(label: Text('NOME DA OLT')),
                                  DataColumn(label: Text('FABRICANTE / MODELO')),
                                  DataColumn(label: Text('IP & PORTA')),
                                  DataColumn(label: Text('PROTOCOLO')),
                                  DataColumn(label: Text('CONECTIVIDADE')),
                                  DataColumn(label: Text('AÇÕES DE GESTÃO')),
                                ],
                                rows: olts.map((olt) {
                                  final isTesting = _isTestingConnection[olt.id] ?? false;
                                  final connResult = _connectionResults[olt.id];
                                  final isBackingUp = _isBackingUp[olt.id] ?? false;

                                  return DataRow(
                                    cells: [
                                      DataCell(
                                        Row(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Container(
                                              width: 8,
                                              height: 8,
                                              decoration: BoxDecoration(
                                                color: olt.status == 'online'
                                                    ? AppColors.statusOnline
                                                    : AppColors.statusDanger,
                                                shape: BoxShape.circle,
                                              ),
                                            ),
                                            const SizedBox(width: 10),
                                            Text(
                                              olt.name,
                                              style: const TextStyle(
                                                fontWeight: FontWeight.bold,
                                                color: AppColors.textPrimary,
                                              ),
                                            ),
                                          ],
                                        ),
                                      ),
                                      DataCell(
                                        Text(
                                          '${olt.vendor.toUpperCase()} • ${olt.model}',
                                          style: const TextStyle(
                                            color: AppColors.textSecondary,
                                            fontSize: 13,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        SelectableText(
                                          '${olt.host}:${olt.port}',
                                          style: const TextStyle(
                                            fontFamily: 'monospace',
                                            color: AppColors.accentCyan,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: AppColors.surfaceHover,
                                            borderRadius: BorderRadius.circular(4),
                                            border: Border.all(color: AppColors.surfaceBorder),
                                          ),
                                          child: Text(
                                            olt.protocol.toUpperCase(),
                                            style: const TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.w600,
                                              color: AppColors.textSecondary,
                                            ),
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        isTesting
                                            ? const SizedBox(
                                                width: 14,
                                                height: 14,
                                                child: CircularProgressIndicator(
                                                  strokeWidth: 2,
                                                  color: AppColors.primaryLight,
                                                ),
                                              )
                                            : connResult != null
                                                ? Text(
                                                    connResult,
                                                    style: TextStyle(
                                                      fontSize: 12,
                                                      fontWeight: FontWeight.w600,
                                                      color: connResult.startsWith('OK')
                                                          ? AppColors.statusOnline
                                                          : AppColors.statusDanger,
                                                    ),
                                                  )
                                                : OutlinedButton(
                                                    style: OutlinedButton.styleFrom(
                                                      padding: const EdgeInsets.symmetric(
                                                          horizontal: 8, vertical: 4),
                                                    ),
                                                    onPressed: () => _testConnection(olt),
                                                    child: const Text('Testar Ping',
                                                        style: TextStyle(fontSize: 11)),
                                                  ),
                                      ),
                                      DataCell(
                                        Wrap(
                                          spacing: 8,
                                          children: [
                                            OutlinedButton.icon(
                                              style: OutlinedButton.styleFrom(
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 8, vertical: 6),
                                              ),
                                              onPressed: isBackingUp ? null : () => _triggerBackup(olt),
                                              icon: isBackingUp
                                                  ? const SizedBox(
                                                      width: 12,
                                                      height: 12,
                                                      child: CircularProgressIndicator(
                                                        strokeWidth: 1.5,
                                                        color: Colors.white,
                                                      ),
                                                    )
                                                  : const Icon(Icons.backup_outlined, size: 14),
                                              label: const Text('Novo Backup',
                                                  style: TextStyle(fontSize: 11)),
                                            ),
                                            OutlinedButton.icon(
                                              style: OutlinedButton.styleFrom(
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 8, vertical: 6),
                                              ),
                                              onPressed: () => _showBackups(olt),
                                              icon: const Icon(Icons.folder_open, size: 14),
                                              label: const Text('Backups',
                                                  style: TextStyle(fontSize: 11)),
                                            ),
                                            OutlinedButton.icon(
                                              style: OutlinedButton.styleFrom(
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 8, vertical: 6),
                                              ),
                                              onPressed: () => _showLiveConfig(olt),
                                              icon: const Icon(Icons.terminal, size: 14),
                                              label: const Text('Running-Config',
                                                  style: TextStyle(fontSize: 11)),
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
          ),
        ],
      ),
    );
  }
}
