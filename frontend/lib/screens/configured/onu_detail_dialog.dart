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
  OpticalTelemetryHistoryModel? _opticalHistory;
  Tr069DeviceSummaryModel? _tr069Summary;
  List<OpticalDistributionBoxModel> _odbs = [];
  List<NetworkZoneModel> _zones = [];
  bool _isLoadingDiagnostics = true;
  String? _diagError;
  bool _isActionRunning = false;

  String? _currentZoneId;
  String? _currentOdbId;
  int? _currentSplitterPort;

  @override
  void initState() {
    super.initState();
    _currentZoneId = widget.onu.zoneId;
    _currentOdbId = widget.onu.odbId;
    _currentSplitterPort = widget.onu.odbSplitterPort;
    _fetchDiagnostics();
    _fetchExtendedData();
  }

  Future<void> _fetchExtendedData() async {
    final settings = context.read<SettingsProvider>();
    try {
      final histFuture = settings.apiClient
          .getOnuOpticalHistory(widget.onu.serial, limit: 15)
          .catchError((_) => OpticalTelemetryHistoryModel(
                serial: widget.onu.serial,
                isDegraded: false,
                samples: const [],
              ));
      final odbsFuture = settings.apiClient
          .getOdbs()
          .catchError((_) => <OpticalDistributionBoxModel>[]);
      final zonesFuture = settings.apiClient
          .getNetworkZones()
          .catchError((_) => <NetworkZoneModel>[]);
      final tr069Future = settings.apiClient
          .getOnuTr069Summary(widget.onu.serial)
          .catchError((_) => Tr069DeviceSummaryModel(
                serial: widget.onu.serial,
                onlineInAcs: false,
              ));

      final results = await Future.wait([
        histFuture,
        odbsFuture,
        zonesFuture,
        tr069Future,
      ]);

      if (mounted) {
        setState(() {
          _opticalHistory = results[0] as OpticalTelemetryHistoryModel;
          _odbs = results[1] as List<OpticalDistributionBoxModel>;
          _zones = results[2] as List<NetworkZoneModel>;
          _tr069Summary = results[3] as Tr069DeviceSummaryModel;
        });
      }
    } catch (_) {}
  }

  Future<void> _fetchDiagnostics() async {
    final settings = context.read<SettingsProvider>();
    final oltId = widget.onu.currentOltId;

    if (oltId == null || oltId.isEmpty) {
      setState(() {
        _isLoadingDiagnostics = false;
        _diagError =
            'OLT de origem não identificada (ONU pode estar pré-provisionada aguardando conexão física).';
      });
      return;
    }

    setState(() {
      _isLoadingDiagnostics = true;
      _diagError = null;
    });

    try {
      var diag =
          await settings.apiClient.getOnuDiagnostics(oltId, widget.onu.serial);
      if (diag.macTable.isEmpty) {
        try {
          final fdbMacs = await settings.apiClient.getOnuMacTable(
            oltId,
            widget.onu.serial,
            port: widget.onu.currentPort,
            onuId: widget.onu.currentOnuId,
          );
          if (fdbMacs.isNotEmpty) {
            diag = OnuDiagnostics(
              port: diag.port,
              onuId: diag.onuId,
              serial: diag.serial,
              status: diag.status,
              rxPowerDbm: diag.rxPowerDbm,
              txPowerDbm: diag.txPowerDbm,
              oltRxPowerDbm: diag.oltRxPowerDbm,
              vlan: diag.vlan,
              lastDownCause: diag.lastDownCause,
              lastDownTime: diag.lastDownTime,
              macTable: fdbMacs,
            );
          }
        } catch (_) {}
      }
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

  Future<void> _showTopologyAssignDialog() async {
    String? selectedZone = _currentZoneId;
    String? selectedOdb = _currentOdbId;
    final portCtrl = TextEditingController(
      text: _currentSplitterPort?.toString() ?? '',
    );

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) {
          return AlertDialog(
            title: const Text('Vincular Topologia Passiva (CTO/ODB)'),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String?>(
                    initialValue: _zones.any((z) => z.id == selectedZone)
                        ? selectedZone
                        : null,
                    decoration: const InputDecoration(labelText: 'Zona / Bairro'),
                    items: [
                      const DropdownMenuItem<String?>(
                        value: null,
                        child: Text('Sem Zona'),
                      ),
                      ..._zones.map(
                        (z) => DropdownMenuItem<String?>(
                          value: z.id,
                          child: Text(z.name),
                        ),
                      ),
                    ],
                    onChanged: (val) => setModalState(() => selectedZone = val),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String?>(
                    initialValue: _odbs.any((o) => o.id == selectedOdb)
                        ? selectedOdb
                        : null,
                    decoration:
                        const InputDecoration(labelText: 'Caixa Óptica (CTO/ODB)'),
                    items: [
                      const DropdownMenuItem<String?>(
                        value: null,
                        child: Text('Sem CTO vinculada'),
                      ),
                      ..._odbs.map(
                        (o) => DropdownMenuItem<String?>(
                          value: o.id,
                          child: Text('${o.code} - ${o.name} (${o.splitterRatio})'),
                        ),
                      ),
                    ],
                    onChanged: (val) => setModalState(() => selectedOdb = val),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: portCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Porta do Splitter (ex: 1 a 16)',
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancelar'),
              ),
              ElevatedButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Salvar Vínculo'),
              ),
            ],
          );
        },
      ),
    );

    if (saved != true || !mounted) return;
    final settings = context.read<SettingsProvider>();
    final appState = context.read<AppState>();
    try {
      final parsedPort = int.tryParse(portCtrl.text.trim());
      await settings.apiClient.assignOnuTopology(widget.onu.serial, {
        'zone_id': selectedZone,
        'odb_id': selectedOdb,
        'odb_splitter_port': parsedPort,
      });
      if (!mounted) return;
      setState(() {
        _currentZoneId = selectedZone;
        _currentOdbId = selectedOdb;
        _currentSplitterPort = parsedPort;
      });
      await appState.loadConfiguredOnus();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppColors.statusOnline,
          content: Text('Vínculo de CTO/Splitter atualizado com sucesso!'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Erro ao vincular CTO: $e'),
        ),
      );
    }
  }

  Future<void> _showTr069WifiDialog() async {
    final ssid24Ctrl =
        TextEditingController(text: _tr069Summary?.ssid24g ?? '');
    final pass24Ctrl = TextEditingController();
    final ssid5Ctrl = TextEditingController(text: _tr069Summary?.ssid5g ?? '');
    final pass5Ctrl = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Configurar Wi-Fi via TR-069 (CWMP)'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: ssid24Ctrl,
                decoration: const InputDecoration(labelText: 'SSID 2.4 GHz'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: pass24Ctrl,
                decoration: const InputDecoration(
                  labelText: 'Nova Senha 2.4 GHz (mín. 8 caracteres)',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: ssid5Ctrl,
                decoration: const InputDecoration(labelText: 'SSID 5 GHz'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: pass5Ctrl,
                decoration: const InputDecoration(
                  labelText: 'Nova Senha 5 GHz (mín. 8 caracteres)',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Aplicar via ACS'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    final settings = context.read<SettingsProvider>();
    try {
      final payload = <String, dynamic>{};
      if (ssid24Ctrl.text.trim().isNotEmpty) {
        payload['ssid_24g'] = ssid24Ctrl.text.trim();
      }
      if (pass24Ctrl.text.trim().length >= 8) {
        payload['password_24g'] = pass24Ctrl.text.trim();
      }
      if (ssid5Ctrl.text.trim().isNotEmpty) {
        payload['ssid_5g'] = ssid5Ctrl.text.trim();
      }
      if (pass5Ctrl.text.trim().length >= 8) {
        payload['password_5g'] = pass5Ctrl.text.trim();
      }
      final res = await settings.apiClient
          .configureOnuTr069Wifi(widget.onu.serial, payload);
      if (!mounted) return;
      await _fetchExtendedData();
      if (!mounted) return;
      final ok = res['task_queued'] == true || res['success'] == true;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor:
              ok ? AppColors.statusOnline : AppColors.statusWarning,
          content: Text(res['message']?.toString() ?? 'Tarefa TR-069 enviada.'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Falha TR-069 Wi-Fi: $e'),
        ),
      );
    }
  }

  Future<void> _showTr069WanDialog() async {
    String selectedMode = _tr069Summary?.wanMode ?? 'pppoe';
    if (!['pppoe', 'dhcp', 'bridge', 'static'].contains(selectedMode)) {
      selectedMode = 'pppoe';
    }
    String selectedIpVersion = 'dual_stack';
    final pppoeUserCtrl = TextEditingController(
      text: _tr069Summary?.pppoeUsername ?? '',
    );
    final pppoePassCtrl = TextEditingController();
    final vlanCtrl = TextEditingController(
      text: widget.onu.vlan?.toString() ?? '',
    );

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) => AlertDialog(
          title: const Text('Configurar WAN / PPPoE via TR-069 (CWMP)'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: selectedMode,
                  decoration: const InputDecoration(labelText: 'Modo WAN *'),
                  items: const [
                    DropdownMenuItem(value: 'pppoe', child: Text('PPPoE')),
                    DropdownMenuItem(
                        value: 'dhcp', child: Text('DHCP / IPoE')),
                    DropdownMenuItem(
                        value: 'bridge', child: Text('Bridge Transparente')),
                    DropdownMenuItem(
                        value: 'static', child: Text('IP Estático')),
                  ],
                  onChanged: (v) {
                    if (v != null) setModalState(() => selectedMode = v);
                  },
                ),
                const SizedBox(height: 10),
                if (selectedMode == 'pppoe') ...[
                  TextField(
                    controller: pppoeUserCtrl,
                    decoration: const InputDecoration(
                      labelText: 'Usuário PPPoE *',
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: pppoePassCtrl,
                    obscureText: true,
                    decoration: const InputDecoration(
                      labelText: 'Senha PPPoE',
                    ),
                  ),
                  const SizedBox(height: 10),
                ],
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: vlanCtrl,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'VLAN WAN',
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: DropdownButtonFormField<String>(
                        initialValue: selectedIpVersion,
                        decoration:
                            const InputDecoration(labelText: 'Pilha IP'),
                        items: const [
                          DropdownMenuItem(
                            value: 'dual_stack',
                            child: Text('IPv4 + IPv6'),
                          ),
                          DropdownMenuItem(
                              value: 'ipv4', child: Text('Somente IPv4')),
                          DropdownMenuItem(
                              value: 'ipv6', child: Text('Somente IPv6')),
                        ],
                        onChanged: (v) {
                          if (v != null) {
                            setModalState(() => selectedIpVersion = v);
                          }
                        },
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Aplicar WAN via ACS'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    final settings = context.read<SettingsProvider>();
    try {
      final payload = <String, dynamic>{
        'mode': selectedMode,
        'ip_version': selectedIpVersion,
        if (pppoeUserCtrl.text.trim().isNotEmpty)
          'pppoe_username': pppoeUserCtrl.text.trim(),
        if (pppoePassCtrl.text.trim().isNotEmpty)
          'pppoe_password': pppoePassCtrl.text.trim(),
        if (int.tryParse(vlanCtrl.text.trim()) != null)
          'vlan_id': int.parse(vlanCtrl.text.trim()),
      };
      final res = await settings.apiClient
          .configureOnuTr069Wan(widget.onu.serial, payload);
      if (!mounted) return;
      await _fetchExtendedData();
      if (!mounted) return;
      final ok = res['task_queued'] == true || res['success'] == true;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor:
              ok ? AppColors.statusOnline : AppColors.statusWarning,
          content:
              Text(res['message']?.toString() ?? 'Configuração WAN enviada.'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Falha TR-069 WAN: $e'),
        ),
      );
    }
  }

  Future<void> _showTr069FirmwareDialog() async {
    final fileCtrl = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Upgrade de Firmware OTA via TR-069'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Versão atual: ${_tr069Summary?.firmwareVersion ?? "Desconhecida"}',
                style: const TextStyle(
                  fontSize: 12,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: fileCtrl,
                decoration: const InputDecoration(
                  labelText: 'Nome do Arquivo de Firmware no ACS *',
                  hintText: 'Ex: EG8145V5_V5R020C10S202.bin',
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Agendar Download OTA'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    final filename = fileCtrl.text.trim();
    if (filename.length < 3) return;
    final settings = context.read<SettingsProvider>();
    try {
      final res =
          await settings.apiClient.pushOnuTr069Firmware(widget.onu.serial, {
        'firmware_filename': filename,
        'file_type': '1 Firmware Upgrade Image',
      });
      if (!mounted) return;
      await _fetchExtendedData();
      if (!mounted) return;
      final ok = res['task_queued'] == true || res['success'] == true;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor:
              ok ? AppColors.statusOnline : AppColors.statusWarning,
          content: Text(
              res['message']?.toString() ?? 'Upgrade OTA agendado no ACS.'),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Falha TR-069 Firmware OTA: $e'),
        ),
      );
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
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.statusWarning),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Reiniciar Agora'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _isActionRunning = true);
    final appState = context.read<AppState>();
    final success =
        await appState.rebootOnu(widget.onu.currentOltId ?? '', widget.onu.serial);
    if (!mounted) return;
    setState(() => _isActionRunning = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor:
            success ? AppColors.statusOnline : AppColors.statusDanger,
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
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor:
                  isSuspended ? AppColors.statusOnline : AppColors.statusWarning,
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
        ? await appState.resumeOnu(
            widget.onu.currentOltId ?? '', widget.onu.serial)
        : await appState.suspendOnu(
            widget.onu.currentOltId ?? '', widget.onu.serial);

    if (!mounted) return;
    setState(() => _isActionRunning = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor:
            success ? AppColors.statusOnline : AppColors.statusDanger,
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
                    style:
                        TextStyle(color: AppColors.textSecondary, fontSize: 13),
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
              TextButton(
                  onPressed: () => Navigator.pop(ctx, false),
                  child: const Text('Cancelar')),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.statusDanger),
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
    final success = await appState.deprovisionOnu(
        widget.onu.currentOltId ?? '', widget.onu.serial);

    if (!mounted) return;
    setState(() => _isActionRunning = false);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor:
            success ? AppColors.statusOnline : AppColors.statusDanger,
        content: Text(
          success
              ? 'ONU ${widget.onu.serial} desprovisionada com sucesso!'
              : 'Falha ao desprovisionar ONU.',
        ),
      ),
    );
    Navigator.of(context).pop();
  }

  Widget _buildDownCauseBadge(String? cause) {
    final normalized = (cause ?? widget.onu.lastDownCause ?? '').toLowerCase();
    if (normalized.isEmpty || normalized == 'none') {
      return const SizedBox.shrink();
    }
    Color color = AppColors.textSecondary;
    String label = 'Última Queda: $normalized';
    IconData icon = Icons.info_outline;

    if (normalized == 'dying_gasp') {
      color = AppColors.statusWarning;
      label = '⚡ Queda Elétrica no Cliente (Dying Gasp)';
      icon = Icons.flash_off_rounded;
    } else if (normalized == 'los' || normalized == 'lof') {
      color = AppColors.statusDanger;
      label = '✂️ Rompimento / Perda de Luz Óptica (LoS)';
      icon = Icons.content_cut_rounded;
    } else if (normalized == 'admin_down') {
      color = AppColors.textMuted;
      label = '🔒 Desativada Administrativamente';
      icon = Icons.lock_outline;
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isSuspended = widget.onu.contractStatus.toUpperCase() == 'SUSPENDED';
    final effectiveDownCause =
        _diagnostics?.lastDownCause ?? widget.onu.lastDownCause;
    final macs = _diagnostics?.macTable ?? const <OnuMacEntryModel>[];
    final currentOdb =
        _odbs.where((o) => o.id == _currentOdbId).firstOrNull;

    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.surfaceBorder, width: 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680),
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
                    icon: const Icon(Icons.close,
                        color: AppColors.textSecondary, size: 20),
                    onPressed: () => Navigator.of(context).pop(),
                    splashRadius: 20,
                  ),
                ],
              ),
              const SizedBox(height: 16),

              // Fase 1: Badge Semântico de Última Causa de Queda (Dying Gasp vs LoS)
              _buildDownCauseBadge(effectiveDownCause),

              // Informações Gerais
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: AppColors.surfaceHover,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: Wrap(
                  spacing: 24,
                  runSpacing: 12,
                  alignment: WrapAlignment.spaceBetween,
                  children: [
                    _InfoItem(
                      label: 'PORTA PON',
                      value: widget.onu.currentPort ?? 'Aguardando PON',
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
                      valueColor: isSuspended
                          ? AppColors.statusWarning
                          : AppColors.statusOnline,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // Seção de Sinal Óptico em Tempo Real
              const Text(
                'Diagnóstico Óptico em Tempo Real',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 8),

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
                                  Icon(Icons.info_outline,
                                      color: AppColors.statusWarning, size: 16),
                                  SizedBox(width: 6),
                                  Text(
                                    'Telemetria em tempo real indisponível',
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
                        : Wrap(
                            spacing: 20,
                            runSpacing: 12,
                            alignment: WrapAlignment.spaceAround,
                            children: [
                              _OpticalCard(
                                label: 'Rx ONU (Downlink)',
                                dbm: _diagnostics?.rxPowerDbm ??
                                    widget.onu.lastRxPowerDbm,
                              ),
                              _OpticalCard(
                                label: 'Tx ONU (Uplink)',
                                dbm: _diagnostics?.txPowerDbm ??
                                    widget.onu.lastTxPowerDbm,
                              ),
                              _OpticalCard(
                                label: 'Rx OLT (Retorno)',
                                dbm: _diagnostics?.oltRxPowerDbm ??
                                    widget.onu.lastOltRxPowerDbm,
                              ),
                            ],
                          ),
              ),
              const SizedBox(height: 18),

              // Fase 2: Histórico & Deriva Óptica (Série Temporal)
              if (_opticalHistory != null &&
                  _opticalHistory!.samples.isNotEmpty) ...[
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      'Histórico de Sinal & Deriva Óptica (Fase 2)',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w600,
                        color: AppColors.textSecondary,
                      ),
                    ),
                    if (_opticalHistory!.driftDb != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: (_opticalHistory!.isDegraded
                                  ? AppColors.statusDanger
                                  : AppColors.statusOnline)
                              .withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          'Variação: ${_opticalHistory!.driftDb!.toStringAsFixed(2)} dB (${_opticalHistory!.samples.length} amostras)',
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: _opticalHistory!.isDegraded
                                ? AppColors.statusDanger
                                : AppColors.statusOnline,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.surfaceHover,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.surfaceBorder),
                  ),
                  child: Wrap(
                    spacing: 16,
                    runSpacing: 8,
                    alignment: WrapAlignment.spaceBetween,
                    children: [
                      _InfoItem(
                        label: 'MÍNIMO RX',
                        value: _opticalHistory!.minRxPowerDbm != null
                            ? '${_opticalHistory!.minRxPowerDbm!.toStringAsFixed(2)} dBm'
                            : '--',
                      ),
                      _InfoItem(
                        label: 'MÉDIO RX',
                        value: _opticalHistory!.avgRxPowerDbm != null
                            ? '${_opticalHistory!.avgRxPowerDbm!.toStringAsFixed(2)} dBm'
                            : '--',
                      ),
                      _InfoItem(
                        label: 'MÁXIMO RX',
                        value: _opticalHistory!.maxRxPowerDbm != null
                            ? '${_opticalHistory!.maxRxPowerDbm!.toStringAsFixed(2)} dBm'
                            : '--',
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),
              ],

              // Fase 1: Tabela MAC Aprendida (FDB/LAN)
              const Text(
                'Tabela MAC Aprendida na ONU (FDB / LAN)',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.surfaceHover,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: macs.isEmpty
                    ? const Text(
                        'Nenhum endereço MAC detectado atrás desta ONU no momento.',
                        style: TextStyle(
                            color: AppColors.textMuted, fontSize: 12),
                      )
                    : Wrap(
                        spacing: 10,
                        runSpacing: 8,
                        children: macs
                            .map(
                              (m) => Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: AppColors.codeBackground,
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(
                                      color: AppColors.surfaceBorder),
                                ),
                                child: Text(
                                  '${m.macAddress}${m.vlan != null ? " (VLAN ${m.vlan})" : ""}${m.servicePortOrEth != null ? " • ${m.servicePortOrEth}" : ""}',
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontSize: 12,
                                    color: AppColors.accentCyan,
                                  ),
                                ),
                              ),
                            )
                            .toList(),
                      ),
              ),
              const SizedBox(height: 18),

              // Fase 4 & 5: Topologia Passiva (CTO) e TR-069 CWMP
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceHover,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.surfaceBorder),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.account_tree_outlined,
                            size: 18, color: AppColors.accentCyan),
                        const SizedBox(width: 8),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'CAIXA ÓPTICA (CTO/ODB)',
                              style: TextStyle(
                                  fontSize: 10, color: AppColors.textSecondary),
                            ),
                            Text(
                              currentOdb != null
                                  ? '${currentOdb.code} (Porta ${_currentSplitterPort ?? "-"})'
                                  : 'Não vinculada',
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(width: 12),
                        TextButton(
                          onPressed: _showTopologyAssignDialog,
                          child: const Text('Vincular CTO'),
                        ),
                      ],
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceHover,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.surfaceBorder),
                    ),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Icon(
                          Icons.wifi_tethering,
                          size: 18,
                          color: _tr069Summary?.onlineInAcs == true
                              ? AppColors.statusOnline
                              : AppColors.textMuted,
                        ),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'GERÊNCIA TR-069 / CWMP',
                              style: TextStyle(
                                  fontSize: 10, color: AppColors.textSecondary),
                            ),
                            Text(
                              _tr069Summary?.onlineInAcs == true
                                  ? 'SSID: ${_tr069Summary?.ssid24g ?? "Ativo"} • WAN: ${_tr069Summary?.wanIp ?? _tr069Summary?.wanMode ?? "N/A"}'
                                  : 'Aguardando Inform ACS',
                              style: const TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.bold,
                                color: AppColors.textPrimary,
                              ),
                            ),
                          ],
                        ),
                        TextButton(
                          onPressed: _showTr069WifiDialog,
                          child: const Text('Wi-Fi TR-069'),
                        ),
                        TextButton(
                          onPressed: _showTr069WanDialog,
                          child: const Text('WAN / PPPoE'),
                        ),
                        TextButton(
                          onPressed: _showTr069FirmwareDialog,
                          child: const Text('Firmware OTA'),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 22),

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
                    child: CircularProgressIndicator(
                        color: AppColors.primaryLight),
                  ),
                )
              else
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _handleReboot,
                      icon: const Icon(Icons.restart_alt,
                          size: 16, color: AppColors.statusWarning),
                      label: const Text('Reiniciar ONU'),
                    ),
                    OutlinedButton.icon(
                      onPressed: () => _handleToggleSuspension(isSuspended),
                      icon: Icon(
                        isSuspended ? Icons.play_arrow : Icons.pause,
                        size: 16,
                        color: isSuspended
                            ? AppColors.statusOnline
                            : AppColors.statusWarning,
                      ),
                      label:
                          Text(isSuspended ? 'Reativar ONU' : 'Suspender ONU'),
                    ),
                    ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                          backgroundColor: AppColors.statusDanger),
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

