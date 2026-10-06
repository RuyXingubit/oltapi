import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/app_state.dart';
import '../olts/olt_backups_dialog.dart';

class BackupsScreen extends StatefulWidget {
  const BackupsScreen({super.key});

  @override
  State<BackupsScreen> createState() => _BackupsScreenState();
}

class _BackupsScreenState extends State<BackupsScreen> {

  @override
  void initState() {
    super.initState();
    final backupParam = Uri.base.queryParameters['backup'];
    if (backupParam != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _checkAndOpenBackupModal(backupParam);
      });
    }
  }

  void _checkAndOpenBackupModal(String oltId) {
    final appState = context.read<AppState>();
    final targetOlt = appState.olts.where((o) => o.id == oltId).firstOrNull;
    if (targetOlt != null) {
      showDialog(
        context: context,
        builder: (context) => OltBackupsDialog(olt: targetOlt),
      );
    }
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
          const Text(
            'Gestão de Backups',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 24),
          if (isLoading)
            const Center(child: CircularProgressIndicator())
          else if (olts.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.only(top: 60),
                child: Text('Nenhuma OLT cadastrada. Vá em "Gerenciar OLTs" para adicionar equipamentos.', style: TextStyle(color: AppColors.textSecondary)),
              ),
            )
          else
            Expanded(
              child: GridView.builder(
                gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                  maxCrossAxisExtent: 400,
                  childAspectRatio: 1.5,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 16,
                ),
                itemCount: olts.length,
                itemBuilder: (context, index) {
                  final olt = olts[index];

                  return Card(
                    color: AppColors.surface,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: const BorderSide(color: AppColors.surfaceBorder),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Expanded(
                                child: Text(
                                  olt.name,
                                  style: const TextStyle(
                                    fontSize: 18,
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text('Fabricante: ${olt.vendor.toUpperCase()} | Modelo: ${olt.model}',
                              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                          Text('Gerência: ${olt.host}:${olt.port} (${olt.protocol.toUpperCase()})',
                              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                          const Spacer(),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              ElevatedButton.icon(
                                onPressed: () => _checkAndOpenBackupModal(olt.id),
                                icon: const Icon(Icons.save, size: 16),
                                label: const Text('Backups'),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
