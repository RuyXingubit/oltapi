import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/onu_model.dart';
import '../../providers/app_state.dart';
import 'onu_detail_dialog.dart';

class ConfiguredScreen extends StatefulWidget {
  const ConfiguredScreen({super.key});

  @override
  State<ConfiguredScreen> createState() => _ConfiguredScreenState();
}

class _ConfiguredScreenState extends State<ConfiguredScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _selectedStatus = 'ALL'; // ALL, ACTIVE, SUSPENDED

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  void _openDetailDialog(BuildContext context, ConfiguredOnu onu) {
    showDialog(
      context: context,
      builder: (ctx) => OnuDetailDialog(onu: onu),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final allOnus = appState.configuredOnus;
    final isLoading = appState.isLoadingConfigured;

    // Filtros
    final query = _searchController.text.trim().toLowerCase();
    final filteredOnus = allOnus.where((onu) {
      final matchesQuery = query.isEmpty ||
          onu.serial.toLowerCase().contains(query) ||
          (onu.subscriberName?.toLowerCase().contains(query) ?? false) ||
          (onu.currentPort?.toLowerCase().contains(query) ?? false) ||
          (onu.vlan?.toString().contains(query) ?? false);

      final matchesStatus = _selectedStatus == 'ALL' ||
          onu.contractStatus.toUpperCase() == _selectedStatus.toUpperCase();

      return matchesQuery && matchesStatus;
    }).toList();

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
                        'ONUs Autorizadas (Configured)',
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
                          '${filteredOnus.length} de ${allOnus.length}',
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
                    'Inventário unificado de ONUs em operação na rede FTTH',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: isLoading ? null : () => appState.loadConfiguredOnus(),
                icon: isLoading
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.refresh, size: 16),
                label: const Text('Atualizar Lista'),
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Barra de Busca e Filtros
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Buscar por serial, assinante, porta ou VLAN...',
                    prefixIcon: const Icon(Icons.search, color: AppColors.textSecondary, size: 20),
                    suffixIcon: _searchController.text.isNotEmpty
                        ? IconButton(
                            icon: const Icon(Icons.clear, size: 18),
                            onPressed: () {
                              _searchController.clear();
                              setState(() {});
                            },
                          )
                        : null,
                    isDense: true,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12),
                decoration: BoxDecoration(
                  color: AppColors.inputBackground,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: DropdownButtonHideUnderline(
                  child: DropdownButton<String>(
                    value: _selectedStatus,
                    dropdownColor: AppColors.surface,
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                    items: const [
                      DropdownMenuItem(value: 'ALL', child: Text('Todos os Status')),
                      DropdownMenuItem(value: 'ACTIVE', child: Text('Ativas (Online)')),
                      DropdownMenuItem(value: 'SUSPENDED', child: Text('Suspensas / Bloqueadas')),
                    ],
                    onChanged: (val) {
                      if (val != null) setState(() => _selectedStatus = val);
                    },
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

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
                  : filteredOnus.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.inbox_outlined,
                                size: 54,
                                color: AppColors.textMuted.withValues(alpha: 0.5),
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'Nenhuma ONU encontrada',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  color: AppColors.textSecondary,
                                ),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                _searchController.text.isNotEmpty
                                    ? 'Nenhum resultado para o filtro "${_searchController.text}".'
                                    : 'Ainda não há ONUs cadastradas no inventário.',
                                style: const TextStyle(
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
                              constraints: const BoxConstraints(minWidth: 900),
                              child: DataTable(
                                columns: const [
                                  DataColumn(label: Text('Nº DE SÉRIE (SN)')),
                                  DataColumn(label: Text('ASSINANTE / DESCRIÇÃO')),
                                  DataColumn(label: Text('PORTA')),
                                  DataColumn(label: Text('ONU ID')),
                                  DataColumn(label: Text('VLAN')),
                                  DataColumn(label: Text('STATUS')),
                                  DataColumn(label: Text('AÇÕES')),
                                ],
                                rows: filteredOnus.map((onu) {
                                  final isSuspended =
                                      onu.contractStatus.toUpperCase() == 'SUSPENDED';

                                  return DataRow(
                                    cells: [
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
                                        ConstrainedBox(
                                          constraints: const BoxConstraints(maxWidth: 220),
                                          child: Text(
                                            onu.subscriberName ??
                                                onu.description ??
                                                'Sem identificação',
                                            style: const TextStyle(
                                              color: AppColors.textPrimary,
                                              fontWeight: FontWeight.w500,
                                            ),
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        Text(
                                          onu.currentPort ?? 'N/A',
                                          style: const TextStyle(
                                            color: AppColors.textPrimary,
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        Text(
                                          onu.currentOnuId?.toString() ?? 'N/A',
                                          style: const TextStyle(color: AppColors.textSecondary),
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
                                            onu.vlan?.toString() ?? 'N/A',
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w600,
                                              fontSize: 12,
                                              color: AppColors.textPrimary,
                                            ),
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: isSuspended
                                                ? AppColors.statusWarning.withValues(alpha: 0.15)
                                                : AppColors.statusOnline.withValues(alpha: 0.15),
                                            borderRadius: BorderRadius.circular(6),
                                            border: Border.all(
                                              color: isSuspended
                                                  ? AppColors.statusWarning
                                                  : AppColors.statusOnline,
                                            ),
                                          ),
                                          child: Text(
                                            onu.contractStatus,
                                            style: TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.bold,
                                              color: isSuspended
                                                  ? AppColors.statusWarning
                                                  : AppColors.statusOnline,
                                            ),
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        OutlinedButton.icon(
                                          style: OutlinedButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(
                                                horizontal: 10, vertical: 6),
                                          ),
                                          onPressed: () => _openDetailDialog(context, onu),
                                          icon: const Icon(Icons.analytics_outlined, size: 14),
                                          label: const Text(
                                            'Diagnóstico',
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
