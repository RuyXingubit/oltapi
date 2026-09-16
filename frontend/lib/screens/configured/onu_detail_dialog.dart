import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/onu_model.dart';
import '../../providers/app_state.dart';
import '../../providers/settings_provider.dart';

class OnuDetailDialog extends StatefulWidget {
  final ConfiguredOnu onu;

  const OnuDetailDialog({super.key, required this.onu});

  @override
  State<OnuDetailDialog> createState() => _OnuDetailDialogState();
}

class _OnuDetailDialogState extends State<OnuDetailDialog> {
  OnuDiagnostics? _diagnostics;
  bool _isLoadingDiagnostics = true;
  String? _diagError;
  bool _isActionRunning = false;

  @override
  void initState() {
    super.initState();
    _fetchDiagnostics();
  }

  Future<void> _fetchDiagnostics() async {
    final settings = context.read<SettingsProvider>();
    final oltId = widget.onu.currentOltId;

    if (oltId == null || oltId.isEmpty) {
      setState(() {
        _isLoadingDiagnostics = false;
        _diagError = 'OLT de origem não identificada para leitura de sinal óptico.';
      });
      return;
    }

    setState(() {
      _isLoadingDiagnostics = true;
      _diagError = null;
    });

    try {
      final diag = await settings.apiClient.getOnuDiagnostics(oltId, widget.onu.serial);
      if (mounted) {
        setState(() {
          _diagnostics = diag;
          _isLoadingDiagnostics = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _diagError = e.toString();
          _isLoadingDiagnostics = false;
        });
      }
    }
  }

  Future<void> _handleReboot() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Reiniciar ONU?'),
        content: Text(
          'Deseja enviar o comando de reboot para a ONU ${widget.onu.serial}? O assinante sofrerá uma desconexão temporária.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.statusWarning),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Reiniciar Agora'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isActionRunning = true);
    final appState = context.read<AppState>();
    final success = await appState.rebootOnu(widget.onu.currentOltId ?? '', widget.onu.serial);
    if (!mounted) return;
    setState(() => _isActionRunning = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: success ? AppColors.statusOnline : AppColors.statusDanger,
        content: Text(
          success
              ? 'Comando de reboot enviado com sucesso para ${widget.onu.serial}!'
              : 'Falha ao reiniciar ONU.',
        ),
      ),
    );
  }

  Future<void> _handleToggleSuspension(bool isSuspended) async {
    final actionName = isSuspended ? 'reativar' : 'suspender';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('${isSuspended ? "Reativar" : "Suspender"} ONU?'),
        content: Text(
          'Deseja realmente $actionName a ONU ${widget.onu.serial} (${widget.onu.subscriberName ?? "Assinante"})?',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: isSuspended ? AppColors.statusOnline : AppColors.statusWarning,
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(isSuspended ? 'Reativar' : 'Suspender'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isActionRunning = true);
    final appState = context.read<AppState>();
    final success = isSuspended
        ? await appState.resumeOnu(widget.onu.currentOltId ?? '', widget.onu.serial)
        : await appState.suspendOnu(widget.onu.currentOltId ?? '', widget.onu.serial);

    if (!mounted) return;
    setState(() => _isActionRunning = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: success ? AppColors.statusOnline : AppColors.statusDanger,
        content: Text(
          success
              ? 'Operação de $actionName concluída com sucesso!'
              : 'Falha na operação de $actionName.',
        ),
      ),
    );
    Navigator.of(context).pop();
  }

  Future<void> _handleDeprovision() async {
    final confirmController = TextEditingController();
    final isConfirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          final isMatch = confirmController.text.trim().toUpperCase() ==
              widget.onu.serial.trim().toUpperCase();

          return AlertDialog(
            title: const Row(
              children: [
                Icon(Icons.warning_amber_rounded, color: AppColors.statusDanger),
                SizedBox(width: 8),
                Text('Excluir ONU da OLT'),
              ],
            ),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Esta ação removerá o provisionamento da ONU da porta PON e liberará o ONU ID.',
                    style: TextStyle(color: AppColors.textPrimary),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Para confirmar com segurança, digite o número de série da ONU abaixo:',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                  const SizedBox(height: 6),
                  SelectableText(
                    widget.onu.serial,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontWeight: FontWeight.bold,
                      color: AppColors.accentCyan,
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: confirmController,
                    onChanged: (_) => setModalState(() {}),
                    decoration: const InputDecoration(
                      hintText: 'Digite o serial exato para liberar',
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: AppColors.statusDanger),
                onPressed: isMatch ? () => Navigator.pop(ctx, true) : null,
                child: const Text('Confirmar Exclusão'),
              ),
            ],
          );
        },
      ),
    );

    if (isConfirmed != true || !mounted) return;

    setState(() => _isActionRunning = true);
    final appState = context.read<AppState>();
    final success =
        await appState.deprovisionOnu(widget.onu.currentOltId ?? '', widget.onu.serial);

    if (!mounted) return;
    setState(() => _isActionRunning = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: success ? AppColors.statusOnline : AppColors.statusDanger,
        content: Text(
          success
              ? 'ONU ${widget.onu.serial} desprovisionada com sucesso!'
              : 'Falha ao desprovisionar ONU.',
        ),
      ),
    );
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final isSuspended = widget.onu.contractStatus.toUpperCase() == 'SUSPENDED';

    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.surfaceBorder, width: 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 620),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AppColors.primary.withValues(alpha: 0.15),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(
                            Icons.router_outlined,
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
                                widget.onu.subscriberName ?? 'Assinante Sem Nome',
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.textPrimary,
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                              SelectableText(
                                widget.onu.serial,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 13,
                                  color: AppColors.accentCyan,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppColors.textSecondary, size: 20),
                    onPressed: () => Navigator.of(context).pop(),
                    splashRadius: 20,
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Informações Gerais
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surfaceHover,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _InfoItem(
                      label: 'PORTA PON',
                      value: widget.onu.currentPort ?? 'N/A',
                      isBold: true,
                    ),
                    _InfoItem(
                      label: 'ONU ID',
                      value: widget.onu.currentOnuId?.toString() ?? 'N/A',
                      isBold: true,
                    ),
                    _InfoItem(
                      label: 'VLAN',
                      value: widget.onu.vlan?.toString() ?? 'N/A',
                      isBold: true,
                    ),
                    _InfoItem(
                      label: 'STATUS CONTRATO',
                      value: widget.onu.contractStatus,
                      valueColor: isSuspended ? AppColors.statusWarning : AppColors.statusOnline,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // Seção de Sinal Óptico
              const Text(
                'Diagnóstico Óptico em Tempo Real',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 10),

              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.codeBackground,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: _isLoadingDiagnostics
                    ? const Center(
                        child: Padding(
                          padding: EdgeInsets.all(12.0),
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: AppColors.primaryLight,
                          ),
                        ),
                      )
                    : _diagError != null
                        ? Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Row(
                                children: [
                                  Icon(Icons.info_outline, color: AppColors.statusWarning, size: 16),
                                  SizedBox(width: 6),
                                  Text(
                                    'Telemetria indisponível no momento',
                                    style: TextStyle(
                                      color: AppColors.statusWarning,
                                      fontWeight: FontWeight.w600,
                                      fontSize: 13,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _diagError!,
                                style: const TextStyle(
                                  color: AppColors.textMuted,
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          )
                        : Row(
                            mainAxisAlignment: MainAxisAlignment.spaceAround,
                            children: [
                              _OpticalCard(
                                label: 'Rx ONU (Downlink)',
                                dbm: _diagnostics?.rxPowerDbm,
                              ),
                              _OpticalCard(
                                label: 'Tx ONU (Uplink)',
                                dbm: _diagnostics?.txPowerDbm,
                              ),
                              _OpticalCard(
                                label: 'Rx OLT',
                                dbm: _diagnostics?.oltRxPowerDbm,
                              ),
                            ],
                          ),
              ),
              const SizedBox(height: 24),

              // Barra de Ações Operacionais Seguras
              const Text(
                'Ações do Ciclo de Vida',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 12),

              if (_isActionRunning)
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(8.0),
                    child: CircularProgressIndicator(color: AppColors.primaryLight),
                  ),
                )
              else
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _handleReboot,
                      icon: const Icon(Icons.restart_alt, size: 16, color: AppColors.statusWarning),
                      label: const Text('Reiniciar ONU'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => _handleToggleSuspension(isSuspended),
                      icon: Icon(
                        isSuspended ? Icons.play_arrow : Icons.pause,
                        size: 16,
                        color: isSuspended ? AppColors.statusOnline : AppColors.statusWarning,
                      ),
                      label: Text(isSuspended ? 'Reativar ONU' : 'Suspender ONU'),
                    ),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(backgroundColor: AppColors.statusDanger),
                      onPressed: _handleDeprovision,
                      icon: const Icon(Icons.delete_outline, size: 16),
                      label: const Text('Excluir ONU'),
                    ),
                  ],
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoItem extends StatelessWidget {
  final String label;
  final String value;
  final bool isBold;
  final Color? valueColor;

  const _InfoItem({
    required this.label,
    required this.value,
    this.isBold = false,
    this.valueColor,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 11,
            color: AppColors.textSecondary,
            letterSpacing: 0.5,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          value,
          style: TextStyle(
            fontSize: 14,
            fontWeight: isBold ? FontWeight.bold : FontWeight.w500,
            color: valueColor ?? AppColors.textPrimary,
          ),
        ),
      ],
    );
  }
}

class _OpticalCard extends StatelessWidget {
  final String label;
  final double? dbm;

  const _OpticalCard({required this.label, required this.dbm});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.getOpticalSignalColor(dbm);
    final quality = AppColors.getOpticalSignalQuality(dbm);

    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
        ),
        const SizedBox(height: 6),
        Text(
          dbm != null ? '${dbm!.toStringAsFixed(2)} dBm' : '-- dBm',
          style: TextStyle(
            color: color,
            fontSize: 16,
            fontWeight: FontWeight.bold,
            fontFamily: 'monospace',
          ),
        ),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            quality,
            style: TextStyle(
              color: color,
              fontSize: 10,
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      ],
    );
  }
}
