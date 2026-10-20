import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/onu_model.dart';
import '../../providers/app_state.dart';
import '../../providers/settings_provider.dart';
import 'onu_detail_dialog.dart';

class ConfiguredScreen extends StatefulWidget {
  const ConfiguredScreen({super.key});

  @override
  State<ConfiguredScreen> createState() => _ConfiguredScreenState();
}

class _ConfiguredScreenState extends State<ConfiguredScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _selectedStatus =
      'ALL'; // ALL, ACTIVE, SUSPENDED, PRE_PROVISIONED, DEGRADED
  final Set<String> _selectedSerials = {};
  final Set<String> _degradedRadarSerials = {};
  bool _isBatchRunning = false;
  bool _isCollectingTelemetry = false;

  Future<void> _refreshDegradedRadar() async {
    final settings = context.read<SettingsProvider>();
    final oltId = context.read<AppState>().selectedOlt?.id;
    try {
      final list = await settings.apiClient.getDegradedOnus(oltId: oltId);
      if (!mounted) return;
      setState(() {
        _degradedRadarSerials
          ..clear()
          ..addAll(list.map((d) => d.serial.toUpperCase()));
      });
    } catch (_) {}
  }

  @override
  void initState() {
    super.initState();
    final qParam = Uri.base.queryParameters['q'];
    if (qParam != null && qParam.isNotEmpty) {
      _searchController.text = qParam;
    }
    final onuParam = Uri.base.queryParameters['onu'];
    if (onuParam != null && onuParam.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _checkAndOpenOnuParam(onuParam);
      });
    }
  }

  void _checkAndOpenOnuParam(String serial) async {
    for (int i = 0; i < 25; i++) {
      if (!mounted) return;
      final appState = context.read<AppState>();
      if (appState.configuredOnus.isNotEmpty) {
        final matches = appState.configuredOnus
            .where((o) => o.serial.toUpperCase() == serial.toUpperCase());
        if (matches.isNotEmpty) {
          _openDetailDialog(context, matches.first);
          break;
        }
      }
      await Future.delayed(const Duration(milliseconds: 200));
    }
  }

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

  Future<void> _collectOpticalTelemetry() async {
    final appState = context.read<AppState>();
    final oltId = appState.selectedOlt?.id;
    if (oltId == null || oltId.isEmpty) return;

    setState(() => _isCollectingTelemetry = true);
    final settings = context.read<SettingsProvider>();
    try {
      final summary = await settings.apiClient.collectOpticalTelemetry(oltId);
      await appState.loadConfiguredOnus();
      await _refreshDegradedRadar();
      if (!mounted) return;
      final collected =
          summary['collected_count'] ?? summary['collected_samples'] ?? 0;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusOnline,
          content: Text(
            'Coleta óptica concluída: $collected ONUs lidas (${summary["degraded_count"] ?? 0} em alerta).',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Falha ao coletar telemetria óptica: $e'),
        ),
      );
    } finally {
      if (mounted) setState(() => _isCollectingTelemetry = false);
    }
  }

  Future<void> _executeBatchAction(String action) async {
    if (_selectedSerials.isEmpty) return;
    int? targetVlan;

    if (action == 'change_vlan') {
      final vlanCtrl = TextEditingController();
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: Text('Trocar VLAN em Lote (${_selectedSerials.length} ONUs)'),
          content: TextField(
            controller: vlanCtrl,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Nova VLAN (2 a 4094)',
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Aplicar em Lote'),
            ),
          ],
        ),
      );
      if (ok != true || !mounted) return;
      targetVlan = int.tryParse(vlanCtrl.text.trim());
      if (targetVlan == null || targetVlan < 2 || targetVlan > 4094) return;
    }

    if (!mounted) return;
    setState(() => _isBatchRunning = true);
    final settings = context.read<SettingsProvider>();
    final appState = context.read<AppState>();
    try {
      final selectedOnus = appState.configuredOnus
          .where((o) => _selectedSerials.contains(o.serial))
          .toList();
      final oltId = appState.selectedOlt?.id ??
          selectedOnus
              .where((o) => o.currentOltId != null && o.currentOltId!.isNotEmpty)
              .map((o) => o.currentOltId!)
              .firstOrNull ??
          '';
      if (oltId.isEmpty) {
        throw Exception('Selecione uma OLT para executar ações em lote.');
      }

      final targets = _selectedSerials.map((serial) {
        final match = selectedOnus.where((o) => o.serial == serial).firstOrNull;
        return {
          'serial': serial,
          if (match?.currentPort != null) 'port': match!.currentPort,
          if (match?.currentOnuId != null) 'onu_id': match!.currentOnuId,
        };
      }).toList();

      final payload = <String, dynamic>{
        'action': action,
        'targets': targets,
      };
      if (targetVlan != null) payload['target_vlan'] = targetVlan;

      final res = await settings.apiClient.batchOnuAction(oltId, payload);
      await appState.loadConfiguredOnus();
      if (!mounted) return;
      setState(() => _selectedSerials.clear());
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: res.failed == 0
              ? AppColors.statusOnline
              : AppColors.statusWarning,
          content: Text(
            'Ação em lote (${res.action}): ${res.succeeded}/${res.totalRequested} concluídas com sucesso.',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Erro na operação em lote: $e'),
        ),
      );
    } finally {
      if (mounted) setState(() => _isBatchRunning = false);
    }
  }

  Widget _buildOpticalAndCauseCell(ConfiguredOnu onu) {
    final rx = onu.lastRxPowerDbm;
    final cause = (onu.lastDownCause ?? '').toLowerCase();
    final rxColor = AppColors.getOpticalSignalColor(rx);

    String? causeBadge;
    Color causeColor = AppColors.textMuted;
    if (cause == 'dying_gasp') {
      causeBadge = '⚡ Dying Gasp';
      causeColor = AppColors.statusWarning;
    } else if (cause == 'los' || cause == 'lof') {
      causeBadge = '✂️ LoS Óptico';
      causeColor = AppColors.statusDanger;
    }

    return Wrap(
      spacing: 6,
      runSpacing: 4,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text(
          rx != null ? '${rx.toStringAsFixed(1)} dBm' : '-- dBm',
          style: TextStyle(
            fontFamily: 'monospace',
            fontSize: 12,
            fontWeight: FontWeight.bold,
            color: rxColor,
          ),
        ),
        if (causeBadge != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: causeColor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: causeColor.withValues(alpha: 0.5)),
            ),
            child: Text(
              causeBadge,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                color: causeColor,
              ),
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final allOnus = appState.configuredOnus;
    final isLoading = appState.isLoadingConfigured;

    final query = _searchController.text.trim().toLowerCase();
    final filteredOnus = allOnus.where((onu) {
      final matchesQuery = query.isEmpty ||
          onu.serial.toLowerCase().contains(query) ||
          (onu.subscriberName?.toLowerCase().contains(query) ?? false) ||
          (onu.currentPort?.toLowerCase().contains(query) ?? false) ||
          (onu.vlan?.toString().contains(query) ?? false);

      bool matchesStatus = true;
      if (_selectedStatus == 'DEGRADED') {
        final isLowRx =
            onu.lastRxPowerDbm != null && onu.lastRxPowerDbm! <= -25.5;
        final isLos = (onu.lastDownCause ?? '').toLowerCase() == 'los';
        final inRadar =
            _degradedRadarSerials.contains(onu.serial.toUpperCase());
        matchesStatus = isLowRx || isLos || inRadar;
      } else if (_selectedStatus != 'ALL') {
        matchesStatus =
            onu.contractStatus.toUpperCase() == _selectedStatus.toUpperCase();
      }

      return matchesQuery && matchesStatus;
    }).toList();

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Wrap(
            spacing: 16,
            runSpacing: 12,
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisSize: MainAxisSize.min,
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
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 3),
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
                    'Inventário unificado com telemetria óptica, causa de queda e ações em lote',
                    style: TextStyle(
                      fontSize: 14,
                      color: AppColors.textSecondary,
                    ),
                  ),
                ],
              ),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: _isCollectingTelemetry
                        ? null
                        : _collectOpticalTelemetry,
                    icon: _isCollectingTelemetry
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: AppColors.accentCyan,
                            ),
                          )
                        : const Icon(Icons.radar, size: 16),
                    label: const Text('Coletar Sinal Óptico'),
                  ),
                  ElevatedButton.icon(
                    onPressed:
                        isLoading ? null : () => appState.loadConfiguredOnus(),
                    icon: isLoading
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.refresh, size: 16),
                    label: const Text('Atualizar Lista'),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Fase 3: Barra de Ações em Lote quando há ONUs selecionadas
          if (_selectedSerials.isNotEmpty)
            Container(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.14),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AppColors.primaryLight),
              ),
              child: Wrap(
                spacing: 10,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(
                    '${_selectedSerials.length} ONU(s) selecionada(s):',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  OutlinedButton.icon(
                    onPressed: _isBatchRunning
                        ? null
                        : () => _executeBatchAction('reboot'),
                    icon: const Icon(Icons.restart_alt, size: 15),
                    label: const Text('Reboot'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _isBatchRunning
                        ? null
                        : () => _executeBatchAction('suspend'),
                    icon: const Icon(Icons.pause_circle_outline, size: 15),
                    label: const Text('Suspender'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _isBatchRunning
                        ? null
                        : () => _executeBatchAction('resume'),
                    icon: const Icon(Icons.play_circle_outline, size: 15),
                    label: const Text('Reativar'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _isBatchRunning
                        ? null
                        : () => _executeBatchAction('change_vlan'),
                    icon: const Icon(Icons.lan_outlined, size: 15),
                    label: const Text('Trocar VLAN'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _isBatchRunning
                        ? null
                        : () => _executeBatchAction('deprovision'),
                    icon: const Icon(Icons.delete_outline,
                        size: 15, color: AppColors.statusDanger),
                    label: const Text('Desprovisionar'),
                  ),
                  TextButton(
                    onPressed: () => setState(() => _selectedSerials.clear()),
                    child: const Text('Limpar Seleção'),
                  ),
                ],
              ),
            ),

          // Barra de Busca e Filtros
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  onChanged: (_) => setState(() {}),
                  decoration: InputDecoration(
                    hintText: 'Buscar por serial, assinante, porta ou VLAN...',
                    prefixIcon: const Icon(Icons.search,
                        color: AppColors.textSecondary, size: 20),
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
                    style: const TextStyle(
                        color: AppColors.textPrimary, fontSize: 13),
                    items: const [
                      DropdownMenuItem(
                          value: 'ALL', child: Text('Todos os Status')),
                      DropdownMenuItem(
                          value: 'ACTIVE', child: Text('Ativas (Online)')),
                      DropdownMenuItem(
                          value: 'SUSPENDED',
                          child: Text('Suspensas / Bloqueadas')),
                      DropdownMenuItem(
                          value: 'PRE_PROVISIONED',
                          child: Text('Pré-Provisionadas (Estoque)')),
                      DropdownMenuItem(
                          value: 'DEGRADED',
                          child: Text('Sinal Crítico / LoS Óptico')),
                    ],
                    onChanged: (val) {
                      if (val != null) {
                        setState(() => _selectedStatus = val);
                        if (val == 'DEGRADED') {
                          _refreshDegradedRadar();
                        }
                      }
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
                      child: CircularProgressIndicator(
                          color: AppColors.primaryLight),
                    )
                  : filteredOnus.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(
                                Icons.inbox_outlined,
                                size: 54,
                                color: AppColors.textMuted
                                    .withValues(alpha: 0.5),
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
                              constraints: const BoxConstraints(minWidth: 960),
                              child: DataTable(
                                showCheckboxColumn: true,
                                columns: const [
                                  DataColumn(label: Text('Nº DE SÉRIE (SN)')),
                                  DataColumn(
                                      label: Text('ASSINANTE / DESCRIÇÃO')),
                                  DataColumn(label: Text('PORTA')),
                                  DataColumn(label: Text('VLAN')),
                                  DataColumn(
                                      label: Text('SINAL / CAUSA QUEDA')),
                                  DataColumn(label: Text('STATUS')),
                                  DataColumn(label: Text('AÇÕES')),
                                ],
                                rows: filteredOnus.map((onu) {
                                  final statusUpper =
                                      onu.contractStatus.toUpperCase();
                                  final isSuspended =
                                      statusUpper == 'SUSPENDED';
                                  final isPreProv =
                                      statusUpper == 'PRE_PROVISIONED';
                                  final isSelected =
                                      _selectedSerials.contains(onu.serial);

                                  final statusColor = isSuspended
                                      ? AppColors.statusWarning
                                      : isPreProv
                                          ? AppColors.accentCyan
                                          : AppColors.statusOnline;

                                  return DataRow(
                                    selected: isSelected,
                                    onSelectChanged: (checked) {
                                      setState(() {
                                        if (checked == true) {
                                          _selectedSerials.add(onu.serial);
                                        } else {
                                          _selectedSerials.remove(onu.serial);
                                        }
                                      });
                                    },
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
                                          constraints: const BoxConstraints(
                                              maxWidth: 200),
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
                                          onu.currentPort != null
                                              ? '${onu.currentPort}:${onu.currentOnuId ?? "-"}'
                                              : 'Aguardando PON',
                                          style: const TextStyle(
                                            color: AppColors.textPrimary,
                                            fontWeight: FontWeight.w500,
                                          ),
                                        ),
                                      ),
                                      DataCell(
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: AppColors.surfaceHover,
                                            borderRadius:
                                                BorderRadius.circular(4),
                                            border: Border.all(
                                                color:
                                                    AppColors.surfaceBorder),
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
                                      DataCell(_buildOpticalAndCauseCell(onu)),
                                      DataCell(
                                        Container(
                                          padding: const EdgeInsets.symmetric(
                                              horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(
                                            color: statusColor
                                                .withValues(alpha: 0.15),
                                            borderRadius:
                                                BorderRadius.circular(6),
                                            border:
                                                Border.all(color: statusColor),
                                          ),
                                          child: Text(
                                            onu.contractStatus,
                                            style: TextStyle(
                                              fontSize: 11,
                                              fontWeight: FontWeight.bold,
                                              color: statusColor,
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
                                          onPressed: () =>
                                              _openDetailDialog(context, onu),
                                          icon: const Icon(
                                              Icons.analytics_outlined,
                                              size: 14),
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

