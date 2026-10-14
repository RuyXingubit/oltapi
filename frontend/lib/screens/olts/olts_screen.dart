import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';
import 'olt_form_dialog.dart';
import 'olt_onboard_wizard_dialog.dart';
import 'olt_vlans_dialog.dart';
import 'olt_xray_dialog.dart';

class OltsScreen extends StatefulWidget {
  const OltsScreen({super.key});

  @override
  State<OltsScreen> createState() => _OltsScreenState();
}

class _OltsScreenState extends State<OltsScreen> {
  final Map<String, bool> _isTestingConnection = {};
  final Map<String, String> _connectionResults = {};

  void _showOltForm([OltModel? olt]) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => OltFormDialog(olt: olt),
    );
  }

  void _showOnboardWizard() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const OltOnboardWizardDialog(),
    );
  }

  void _showXRayDialog(OltModel olt) {
    showDialog(
      context: context,
      builder: (context) => OltXRayDialog(olt: olt),
    );
  }

  void _showVlansDialog(OltModel olt) {
    showDialog(
      context: context,
      builder: (context) => OltVlansDialog(olt: olt),
    );
  }

  Future<void> _deleteOlt(OltModel olt) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text('Excluir OLT', style: TextStyle(color: AppColors.statusDanger)),
        content: Text('Tem certeza que deseja excluir a OLT ${olt.name}? Isso removerá a OLT do inventário.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar', style: TextStyle(color: AppColors.textSecondary)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Excluir', style: TextStyle(color: AppColors.statusDanger)),
          ),
        ],
      ),
    );

    if (confirm == true && mounted) {
      final success = await context.read<AppState>().deleteOlt(olt.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(success ? 'OLT removida com sucesso' : 'Falha ao remover OLT'),
            backgroundColor: success ? AppColors.statusOnline : AppColors.statusDanger,
          ),
        );
      }
    }
  }

  Future<void> _testConnection(OltModel olt) async {
    setState(() {
      _isTestingConnection[olt.id] = true;
      _connectionResults.remove(olt.id);
    });

    try {
      final result = await context.read<AppState>().apiClient.testOltConnection(olt.id);
      if (mounted) {
        setState(() {
          _connectionResults[olt.id] =
              result.reachable ? 'Online (${result.latencyMs?.toStringAsFixed(1)}ms)' : 'Offline';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _connectionResults[olt.id] = 'Falha no teste';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isTestingConnection[olt.id] = false;
        });
      }
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
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 16,
            runSpacing: 12,
            children: [
              const Text(
                'Inventário de OLTs',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              Wrap(
                spacing: 12,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: _showOnboardWizard,
                    icon: const Icon(Icons.auto_fix_high, size: 18),
                    label: const Text('Wizard Zero-Touch'),
                  ),
                  ElevatedButton.icon(
                    onPressed: () => _showOltForm(),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Nova OLT'),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 24),
          if (isLoading)
            const Center(child: CircularProgressIndicator())
          else if (olts.isEmpty)
            const Center(
              child: Padding(
                padding: EdgeInsets.only(top: 60),
                child: Text(
                  'Nenhuma OLT cadastrada.',
                  style: TextStyle(color: AppColors.textSecondary),
                ),
              ),
            )
          else
            Expanded(
              child: GridView.builder(
                gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                  maxCrossAxisExtent: 420,
                  mainAxisExtent: 295,
                  crossAxisSpacing: 16,
                  mainAxisSpacing: 16,
                ),
                itemCount: olts.length,
                itemBuilder: (context, index) {
                  final olt = olts[index];
                  final isTesting = _isTestingConnection[olt.id] ?? false;
                  final testResult = _connectionResults[olt.id];

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
                              PopupMenuButton<String>(
                                icon: const Icon(Icons.more_vert, color: AppColors.textSecondary),
                                color: AppColors.surfaceHover,
                                onSelected: (val) {
                                  if (val == 'xray') _showXRayDialog(olt);
                                  if (val == 'vlans') _showVlansDialog(olt);
                                  if (val == 'edit') _showOltForm(olt);
                                  if (val == 'delete') _deleteOlt(olt);
                                },
                                itemBuilder: (context) => [
                                  const PopupMenuItem(
                                    value: 'xray',
                                    child: Row(
                                      children: [
                                        Icon(Icons.radar, size: 18, color: AppColors.primary),
                                        SizedBox(width: 8),
                                        Text('Raio-X & Sync', style: TextStyle(color: AppColors.textPrimary)),
                                      ],
                                    ),
                                  ),
                                  const PopupMenuItem(
                                    value: 'vlans',
                                    child: Row(
                                      children: [
                                        Icon(Icons.lan, size: 18, color: AppColors.primary),
                                        SizedBox(width: 8),
                                        Text('Catálogo de VLANs', style: TextStyle(color: AppColors.textPrimary)),
                                      ],
                                    ),
                                  ),
                                  const PopupMenuItem(
                                    value: 'edit',
                                    child: Row(
                                      children: [
                                        Icon(Icons.edit, size: 18, color: AppColors.textPrimary),
                                        SizedBox(width: 8),
                                        Text('Editar OLT', style: TextStyle(color: AppColors.textPrimary)),
                                      ],
                                    ),
                                  ),
                                  const PopupMenuItem(
                                    value: 'delete',
                                    child: Row(
                                      children: [
                                        Icon(Icons.delete, size: 18, color: AppColors.statusDanger),
                                        SizedBox(width: 8),
                                        Text('Excluir OLT', style: TextStyle(color: AppColors.statusDanger)),
                                      ],
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Expanded(
                            child: SingleChildScrollView(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Fabricante: ${olt.vendor.toUpperCase()} | Modelo: ${olt.model}',
                                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  Text(
                                    'Gerência: ${olt.host}:${olt.port} (${olt.protocol.toUpperCase()})',
                                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  const SizedBox(height: 10),
                                  Wrap(
                                    spacing: 8,
                                    runSpacing: 6,
                                    children: [
                                      ActionChip(
                                        avatar: const Icon(Icons.radar, size: 15, color: AppColors.primary),
                                        label: const Text(
                                          'Raio-X & Sync',
                                          style: TextStyle(color: AppColors.textPrimary, fontSize: 12),
                                        ),
                                        backgroundColor: AppColors.background,
                                        side: const BorderSide(color: AppColors.surfaceBorder),
                                        onPressed: () => _showXRayDialog(olt),
                                      ),
                                      ActionChip(
                                        avatar: const Icon(Icons.lan, size: 15, color: AppColors.primary),
                                        label: const Text(
                                          'VLANs',
                                          style: TextStyle(color: AppColors.textPrimary, fontSize: 12),
                                        ),
                                        backgroundColor: AppColors.background,
                                        side: const BorderSide(color: AppColors.surfaceBorder),
                                        onPressed: () => _showVlansDialog(olt),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            ),
                          ),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              if (isTesting)
                                const SizedBox(
                                  width: 16,
                                  height: 16,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              else if (testResult != null)
                                Flexible(
                                  child: Text(
                                    testResult,
                                    style: TextStyle(
                                      color: testResult.startsWith('Online')
                                          ? AppColors.statusOnline
                                          : AppColors.statusDanger,
                                      fontSize: 13,
                                      fontWeight: FontWeight.bold,
                                    ),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                )
                              else
                                const SizedBox(),
                              TextButton.icon(
                                onPressed: isTesting ? null : () => _testConnection(olt),
                                icon: const Icon(Icons.wifi, size: 16),
                                label: const Text('Testar Conexão'),
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
