import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';

class OltXRayDialog extends StatefulWidget {
  final OltModel olt;

  const OltXRayDialog({super.key, required this.olt});

  @override
  State<OltXRayDialog> createState() => _OltXRayDialogState();
}

class _OltXRayDialogState extends State<OltXRayDialog> {
  OltXRayModel? _xray;
  SyncOltResultModel? _syncResult;
  bool _isLoadingTelemetry = true;
  bool _isSyncing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadTelemetry();
  }

  Future<void> _loadTelemetry() async {
    setState(() {
      _isLoadingTelemetry = true;
      _error = null;
    });
    try {
      final api = context.read<AppState>().apiClient;
      final xray = await api.getOltTelemetry(widget.olt.id);
      if (mounted) {
        setState(() {
          _xray = xray;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Falha ao coletar Raio-X e telemetria da OLT: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isLoadingTelemetry = false);
      }
    }
  }

  Future<void> _runBrownfieldSync() async {
    setState(() {
      _isSyncing = true;
      _error = null;
    });
    try {
      final appState = context.read<AppState>();
      final res = await appState.apiClient.syncOlt(widget.olt.id);
      await appState.loadConfiguredOnus();
      if (mounted) {
        setState(() {
          _syncResult = res;
        });
      }
      await _loadTelemetry();
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Falha na sincronização Brownfield: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isSyncing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 820, maxHeight: 720),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeader(),
              const SizedBox(height: 16),
              if (_error != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.statusDanger.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.statusDanger.withValues(alpha: 0.4)),
                  ),
                  child: Text(
                    _error!,
                    style: const TextStyle(color: AppColors.statusDanger, fontSize: 13),
                  ),
                ),
                const SizedBox(height: 12),
              ],
              if (_syncResult != null) ...[
                _buildSyncResultBanner(_syncResult!),
                const SizedBox(height: 12),
              ],
              if (_isLoadingTelemetry)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 48),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_xray == null)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 32),
                  child: Center(
                    child: Text(
                      'Nenhum dado de telemetria retornado.',
                      style: TextStyle(color: AppColors.textSecondary),
                    ),
                  ),
                )
              else
                Flexible(
                  child: SingleChildScrollView(
                    child: _buildXRayBody(_xray!),
                  ),
                ),
              const SizedBox(height: 16),
              _buildFooter(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Row(
            children: [
              const Icon(Icons.radar, color: AppColors.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Raio-X de Chassi & Telemetria — ${widget.olt.name}',
                      style: const TextStyle(
                        fontSize: 19,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      '${widget.olt.vendor.toUpperCase()} ${widget.olt.model} • ${widget.olt.host}:${widget.olt.port}',
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        IconButton(
          icon: const Icon(Icons.close, color: AppColors.textSecondary),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ],
    );
  }

  Widget _buildSyncResultBanner(SyncOltResultModel sync) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.statusOnline.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.statusOnline.withValues(alpha: 0.4)),
      ),
      child: Wrap(
        spacing: 16,
        runSpacing: 6,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.sync, color: AppColors.statusOnline, size: 18),
              SizedBox(width: 6),
              Text(
                'Sincronização Brownfield Concluída:',
                style: TextStyle(color: AppColors.statusOnline, fontWeight: FontWeight.bold, fontSize: 13),
              ),
            ],
          ),
          Text(
            'ONUs na OLT: ${sync.totalOnusDiscovered}',
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
          ),
          Text(
            'Novas Importadas: ${sync.newOnusRegistered}',
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
          ),
          Text(
            'Atualizadas: ${sync.existingOnusUpdated}',
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
          ),
          Text(
            'VLANs Descobertas: ${sync.vlansDiscovered.length}',
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _buildXRayBody(OltXRayModel xray) {
    final ponPorts = xray.ports
        .where((p) => p.portType.toLowerCase().contains('pon') || p.portType.toLowerCase() == 'gpon')
        .toList();
    final uplinkPorts = xray.ports
        .where((p) => !p.portType.toLowerCase().contains('pon') && p.portType.toLowerCase() != 'gpon')
        .toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            _buildStatBadge(
              label: 'SNMP Status',
              value: xray.snmpActive ? 'Online' : xray.snmpStatus.toUpperCase(),
              color: xray.snmpActive ? AppColors.statusOnline : AppColors.statusWarning,
              icon: Icons.sensors,
            ),
            _buildStatBadge(
              label: 'Portas PON',
              value: '${ponPorts.length}',
              color: AppColors.primary,
              icon: Icons.settings_input_component,
            ),
            _buildStatBadge(
              label: 'Portas Uplink',
              value: '${uplinkPorts.length}',
              color: AppColors.primary,
              icon: Icons.swap_horiz,
            ),
            _buildStatBadge(
              label: 'VLANs no Chassi',
              value: '${xray.totalVlansDetected}',
              color: AppColors.primary,
              icon: Icons.lan,
            ),
            _buildStatBadge(
              label: 'ONUs Detectadas',
              value: '${xray.totalOnusDetected}',
              color: AppColors.statusOnline,
              icon: Icons.router,
            ),
            _buildStatBadge(
              label: 'Uptime',
              value: xray.uptimeHuman,
              color: AppColors.textSecondary,
              icon: Icons.schedule,
            ),
          ],
        ),
        if (xray.firmwareVersion != null ||
            xray.cpuUsagePct != null ||
            xray.memoryUsagePct != null ||
            xray.temperatureCelsius != null ||
            xray.snmpMessage != null) ...[
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Wrap(
              spacing: 16,
              runSpacing: 6,
              children: [
                if (xray.firmwareVersion != null && xray.firmwareVersion!.isNotEmpty)
                  Text(
                    'Firmware: ${xray.firmwareVersion}',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                  ),
                if (xray.cpuUsagePct != null)
                  Text(
                    'CPU: ${xray.cpuUsagePct!.toStringAsFixed(1)}%',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                  ),
                if (xray.memoryUsagePct != null)
                  Text(
                    'RAM: ${xray.memoryUsagePct!.toStringAsFixed(1)}%',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                  ),
                if (xray.temperatureCelsius != null)
                  Text(
                    'Temp: ${xray.temperatureCelsius!.toStringAsFixed(1)} °C',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                  ),
                if (xray.snmpMessage != null && xray.snmpMessage!.isNotEmpty)
                  Text(
                    'SNMP Info: ${xray.snmpMessage}',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  ),
              ],
            ),
          ),
        ],
        const SizedBox(height: 18),
        const Text(
          'Portas PON do Chassi',
          style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 15),
        ),
        const SizedBox(height: 8),
        _buildPortGrid(ponPorts, emptyMessage: 'Nenhuma porta PON reportada pelo chassi.'),
        const SizedBox(height: 18),
        const Text(
          'Portas de Uplink / GE / XGE',
          style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 15),
        ),
        const SizedBox(height: 8),
        _buildPortGrid(uplinkPorts, emptyMessage: 'Nenhuma porta Uplink reportada pelo chassi.'),
        const SizedBox(height: 18),
        const Text(
          'VLANs Ativas no Flash da OLT',
          style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 15),
        ),
        const SizedBox(height: 8),
        if (xray.vlans.isEmpty)
          const Text(
            'Nenhuma VLAN detectada no hardware.',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
          )
        else
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: xray.vlans
                .map(
                  (vlanId) => Chip(
                    backgroundColor: AppColors.background,
                    side: const BorderSide(color: AppColors.surfaceBorder),
                    label: Text(
                      'VLAN $vlanId',
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                    ),
                  ),
                )
                .toList(),
          ),
      ],
    );
  }

  Widget _buildStatBadge({
    required String label,
    required String value,
    required Color color,
    required IconData icon,
  }) {
    return Container(
      width: 145,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 15, color: color),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  label,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildPortGrid(List<OltPortStatusItem> ports, {required String emptyMessage}) {
    if (ports.isEmpty) {
      return Text(
        emptyMessage,
        style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
      );
    }

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: ports.map((p) {
        final isUp = p.operStatus.toLowerCase() == 'up' || p.operStatus.toLowerCase() == 'online';
        final statusColor = isUp ? AppColors.statusOnline : AppColors.textSecondary;
        return Container(
          width: 185,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: isUp ? AppColors.statusOnline.withValues(alpha: 0.4) : AppColors.surfaceBorder,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      p.portId,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: statusColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      p.operStatus.toUpperCase(),
                      style: TextStyle(
                        color: statusColor,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                p.portType.toLowerCase().contains('pon')
                    ? 'ONUs: ${p.onuCount}/${p.onuCapacity}'
                    : (p.speedDuplex ?? p.details ?? p.portType.toUpperCase()),
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildFooter() {
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 12,
      runSpacing: 8,
      children: [
        OutlinedButton.icon(
          onPressed: (_isLoadingTelemetry || _isSyncing) ? null : _runBrownfieldSync,
          icon: _isSyncing
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.sync, size: 18),
          label: const Text('Sincronizar Brownfield (Flash -> DB)'),
        ),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton.icon(
              onPressed: (_isLoadingTelemetry || _isSyncing) ? null : _loadTelemetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Atualizar Telemetria'),
            ),
            const SizedBox(width: 8),
            ElevatedButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Fechar'),
            ),
          ],
        ),
      ],
    );
  }
}
