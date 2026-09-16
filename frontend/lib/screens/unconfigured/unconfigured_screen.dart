import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/onu_model.dart';
import '../../providers/app_state.dart';
import 'authorize_onu_dialog.dart';

class UnconfiguredScreen extends StatelessWidget {
  const UnconfiguredScreen({super.key});

  void _openAuthorizeDialog(BuildContext context, UnauthorizedOnu onu) {
    final appState = context.read<AppState>();
    showDialog(
      context: context,
      builder: (ctx) => AuthorizeOnuDialog(
        onu: onu,
        onAuthorize: (vlan, profile, description) async {
          final success = await appState.provisionOnu(
            port: onu.port,
            serial: onu.serial,
            vlan: vlan,
            profile: profile,
            description: description,
          );

          if (!context.mounted) return;
          if (success) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                backgroundColor: AppColors.statusOnline,
                content: Text('ONU ${onu.serial} autorizada com sucesso na VLAN $vlan!'),
              ),
            );
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                backgroundColor: AppColors.statusDanger,
                content: Text(appState.errorMessage ?? 'Falha ao autorizar ONU'),
              ),
            );
          }
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final selectedOlt = appState.selectedOlt;
    final unconfigured = appState.unauthorizedOnus;
    final isLoading = appState.isLoadingUnauthorized;

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
                        'Aguardando Autorização',
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
                          color: unconfigured.isEmpty
                              ? AppColors.surfaceBorder
                              : AppColors.primary.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: unconfigured.isEmpty
                                ? AppColors.surfaceBorder
                                : AppColors.primaryLight,
                          ),
                        ),
                        child: Text(
                          '${unconfigured.length} pendentes',
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: unconfigured.isEmpty
                                ? AppColors.textSecondary
                                : AppColors.primaryLight,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    selectedOlt != null
                        ? 'ONUs descobertas na OLT: ${selectedOlt.name} (${selectedOlt.vendor.toUpperCase()} - ${selectedOlt.host})'
                        : 'Nenhuma OLT selecionada',
                    style: const TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: isLoading || selectedOlt == null
                    ? null
                    : () => appState.loadUnauthorizedOnus(),
                icon: isLoading
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.refresh, size: 16),
                label: const Text('Escanear PON'),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Tabela ou Empty State
          Expanded(
            child: Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.surfaceBorder),
              ),
              child: isLoading
                  ? const Center(
                      child: CircularProgressIndicator(color: AppColors.primaryLight),
                    )
                  : unconfigured.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.check_circle_outline,
                                size: 54,
                                color: AppColors.textMuted.withValues(alpha: 0.5),
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'Nenhuma ONU aguardando autorização',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                              const SizedBox(height: 6),
                              const Text(
                                'Todas as ONUs conectadas na OLT já foram homologadas e provisionadas.',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: AppColors.textMuted,
                                ),
                              ),
                            ],
                          ),
                        )
                      : SingleChildScrollView(
                          scrollDirection: Axis.vertical,
                          child: SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: ConstrainedBox(
                              constraints: const BoxConstraints(minWidth: 800),
                              child: DataTable(
                                columns: const [
                                  DataColumn(label: Text('PORTA PON')),
                                  DataColumn(label: Text('Nº DE SÉRIE (SN)')),
                                  DataColumn(label: Text('MODELO DETECTADO')),
                                  DataColumn(label: Text('DESCOBERTA EM')),
                                  DataColumn(label: Text('AÇÃO')),
                                ],
                                rows: unconfigured.map((onu) {
                                  final dateFormat = DateFormat('dd/MM/yyyy HH:mm:ss');
                                  final dateStr = onu.detectedAt != null
                                      ? dateFormat.format(onu.detectedAt!.toLocal())
                                      : 'Agora';

                                  return DataRow(
                                    cells: [
                                      DataCell(
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: AppColors.surfaceHover,
                                            borderRadius: BorderRadius.circular(4),
                                            border: Border.all(color: AppColors.surfaceBorder),
                                          ),
                                          child: Text(
                                            onu.port,
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w600,
                                              fontSize: 12,
                                              color: AppColors.textPrimary,
                                            ),
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        SelectableText(
                                          onu.serial,
                                          style: const TextStyle(
                                            fontFamily: 'monospace',
                                            fontWeight: FontWeight.bold,
                                            color: AppColors.accentCyan,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        Text(
                                          onu.model ?? 'Padrão / Desconhecido',
                                          style: const TextStyle(color: AppColors.textPrimary),
                                        ),
                                      ),
                                      DataCell(
                                        Text(
                                          dateStr,
                                          style: const TextStyle(
                                            color: AppColors.textSecondary,
                                            fontSize: 13,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        ElevatedButton.icon(
                                          style: ElevatedButton.styleFrom(
                                            backgroundColor: AppColors.primary,
                                            padding: const EdgeInsets.symmetric(
                                                horizontal: 12, vertical: 8),
                                          ),
                                          onPressed: () => _openAuthorizeDialog(context, onu),
                                          icon: const Icon(Icons.check, size: 14),
                                          label: const Text(
                                            'Autorizar',
                                            style: TextStyle(fontSize: 12),
                                          ),
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
