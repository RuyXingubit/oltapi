import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';
import 'olt_form_dialog.dart';

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
      setState(() {
        _connectionResults[olt.id] = result.reachable ? 'Online (${result.latencyMs?.toStringAsFixed(1)}ms)' : 'Offline';
      });
    } catch (e) {
      setState(() {
        _connectionResults[olt.id] = 'Falha no teste';
      });
    } finally {
      setState(() {
        _isTestingConnection[olt.id] = false;
      });
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
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Inventário de OLTs',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              ElevatedButton.icon(
                onPressed: () => _showOltForm(),
                icon: const Icon(Icons.add),
                label: const Text('Nova OLT'),
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
                child: Text('Nenhuma OLT cadastrada.', style: TextStyle(color: AppColors.textSecondary)),
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
                                  if (val == 'edit') _showOltForm(olt);
                                  if (val == 'delete') _deleteOlt(olt);
                                },
                                itemBuilder: (context) => [
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
                          const SizedBox(height: 8),
                          Text('Fabricante: ${olt.vendor.toUpperCase()} | Modelo: ${olt.model}',
                              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                          Text('Gerência: ${olt.host}:${olt.port} (${olt.protocol.toUpperCase()})',
                              style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                          const Spacer(),
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
                                Text(
                                  testResult,
                                  style: TextStyle(
                                    color: testResult.startsWith('Online') ? AppColors.statusOnline : AppColors.statusDanger,
                                    fontSize: 13,
                                    fontWeight: FontWeight.bold,
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
