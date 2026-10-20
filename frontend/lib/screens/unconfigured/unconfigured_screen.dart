import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/onu_model.dart';
import '../../models/pon_policy_model.dart';
import '../../providers/app_state.dart';
import '../../providers/settings_provider.dart';
import 'authorize_onu_dialog.dart';

class UnconfiguredScreen extends StatefulWidget {
  const UnconfiguredScreen({super.key});

  @override
  State<UnconfiguredScreen> createState() => _UnconfiguredScreenState();
}

class _UnconfiguredScreenState extends State<UnconfiguredScreen> {
  List<AutoProvisionTaskModel> _activeTasks = [];
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadActiveTasks();
    });
    _refreshTimer = Timer.periodic(const Duration(seconds: 10), (_) {
      if (mounted) _loadActiveTasks();
    });
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadActiveTasks() async {
    final appState = context.read<AppState>();
    final settings = context.read<SettingsProvider>();
    final selectedOlt = appState.selectedOlt;
    if (selectedOlt == null) {
      if (mounted) setState(() => _activeTasks = []);
      return;
    }

    try {
      final tasks = await settings.apiClient.listAutoProvisionTasks(selectedOlt.id);
      if (mounted) {
        setState(() {
          _activeTasks = tasks.where((t) => t.status == 'active' && t.remainingSeconds > 0).toList();
        });
      }
    } catch (_) {
      // Ignore background network errors
    }
  }

  Future<void> _cancelTask(AutoProvisionTaskModel task) async {
    final appState = context.read<AppState>();
    final settings = context.read<SettingsProvider>();
    final selectedOlt = appState.selectedOlt;
    if (selectedOlt == null) return;

    try {
      await settings.apiClient.cancelAutoProvisionTask(selectedOlt.id, task.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.statusWarning,
            content: Text('Janela de cutover para PON ${task.port} encerrada.'),
          ),
        );
        _loadActiveTasks();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppColors.statusDanger,
            content: Text('Erro ao encerrar cutover: $e'),
          ),
        );
      }
    }
  }

  Future<void> _openAuthorizeDialog(BuildContext context, UnauthorizedOnu onu) async {
    final appState = context.read<AppState>();
    final settings = context.read<SettingsProvider>();
    final selectedOlt = appState.selectedOlt;

    int? initialVlan;
    String? initialProfile;

    if (selectedOlt != null) {
      try {
        final policy = await settings.apiClient.getPonPolicy(selectedOlt.id, onu.port);
        initialVlan = policy.defaultVlan;
        initialProfile = policy.defaultProfile;
      } catch (_) {
        // No custom policy configured for this port
      }
    }

    if (!context.mounted) return;

    showDialog(
      context: context,
      builder: (ctx) => AuthorizeOnuDialog(
        onu: onu,
        initialVlan: initialVlan,
        initialProfile: initialProfile,
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

  Future<void> _showPreProvisionDialog() async {
    final settings = context.read<SettingsProvider>();
    final appState = context.read<AppState>();

    List<ProvisioningPresetModel> presets = [];
    List<NetworkZoneModel> zones = [];
    List<OpticalDistributionBoxModel> odbs = [];
    try {
      final results = await Future.wait([
        settings.apiClient
            .getPresets()
            .catchError((_) => <ProvisioningPresetModel>[]),
        settings.apiClient
            .getNetworkZones()
            .catchError((_) => <NetworkZoneModel>[]),
        settings.apiClient
            .getOdbs()
            .catchError((_) => <OpticalDistributionBoxModel>[]),
      ]);
      presets = results[0] as List<ProvisioningPresetModel>;
      zones = results[1] as List<NetworkZoneModel>;
      odbs = results[2] as List<OpticalDistributionBoxModel>;
    } catch (_) {}

    if (!mounted) return;

    final defPreset = presets.where((p) => p.isDefault).firstOrNull;
    String? selectedPresetId = defPreset?.id;
    String? selectedZoneId;
    String? selectedOdbId;

    final serialCtrl = TextEditingController();
    final subCtrl = TextEditingController();
    final contractCtrl = TextEditingController();
    final vlanCtrl = TextEditingController(
      text: (defPreset?.defaultVlan ?? 100).toString(),
    );
    final profileCtrl = TextEditingController(
      text: defPreset?.defaultProfile ?? 'DEFAULT',
    );
    final splitterPortCtrl = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) => AlertDialog(
          title: const Text('Pré-Provisionar ONU (Estoque / Plug-and-Play)'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  'Cadastre o serial antes da instalação física. Quando o técnico conectar a fibra, o Scanner Autônomo provisionará automaticamente.',
                  style:
                      TextStyle(fontSize: 12, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 12),
                if (presets.isNotEmpty) ...[
                  DropdownButtonFormField<String?>(
                    initialValue: selectedPresetId,
                    decoration: const InputDecoration(
                      labelText: 'Preset Universal (Auto-preenchimento)',
                      prefixIcon: Icon(Icons.auto_awesome_outlined, size: 18),
                    ),
                    items: [
                      const DropdownMenuItem<String?>(
                        value: null,
                        child: Text('Manual / Personalizado'),
                      ),
                      ...presets.map(
                        (p) => DropdownMenuItem<String?>(
                          value: p.id,
                          child: Text(
                            '${p.name} (VLAN ${p.defaultVlan} • ${p.defaultProfile})',
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ),
                    ],
                    onChanged: (val) {
                      setModalState(() {
                        selectedPresetId = val;
                        final chosen =
                            presets.where((p) => p.id == val).firstOrNull;
                        if (chosen != null) {
                          vlanCtrl.text = chosen.defaultVlan.toString();
                          profileCtrl.text = chosen.defaultProfile;
                        }
                      });
                    },
                  ),
                  const SizedBox(height: 10),
                ],
                TextField(
                  controller: serialCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Serial da ONU (SN) *',
                    hintText: 'Ex: FHTT99887766',
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: subCtrl,
                  decoration: const InputDecoration(
                    labelText: 'Nome do Assinante *',
                  ),
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: contractCtrl,
                  decoration: const InputDecoration(
                    labelText: 'ID do Contrato (CRM/ERP)',
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: vlanCtrl,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: 'VLAN *'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: profileCtrl,
                        decoration: const InputDecoration(labelText: 'Perfil'),
                      ),
                    ),
                  ],
                ),
                if (zones.isNotEmpty || odbs.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  if (zones.isNotEmpty)
                    DropdownButtonFormField<String?>(
                      initialValue: selectedZoneId,
                      decoration: const InputDecoration(
                        labelText: 'Zona FTTH / Bairro (Opcional)',
                      ),
                      items: [
                        const DropdownMenuItem<String?>(
                          value: null,
                          child: Text('Sem Zona'),
                        ),
                        ...zones.map(
                          (z) => DropdownMenuItem<String?>(
                            value: z.id,
                            child: Text(z.name),
                          ),
                        ),
                      ],
                      onChanged: (val) =>
                          setModalState(() => selectedZoneId = val),
                    ),
                  const SizedBox(height: 10),
                  if (odbs.isNotEmpty)
                    Row(
                      children: [
                        Expanded(
                          flex: 2,
                          child: DropdownButtonFormField<String?>(
                            initialValue: selectedOdbId,
                            decoration: const InputDecoration(
                              labelText: 'CTO / ODB (Opcional)',
                            ),
                            items: [
                              const DropdownMenuItem<String?>(
                                value: null,
                                child: Text('Sem CTO'),
                              ),
                              ...odbs.map(
                                (o) => DropdownMenuItem<String?>(
                                  value: o.id,
                                  child: Text(
                                    '${o.code} (${o.splitterRatio})',
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                              ),
                            ],
                            onChanged: (val) =>
                                setModalState(() => selectedOdbId = val),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextField(
                            controller: splitterPortCtrl,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Porta Splitter',
                            ),
                          ),
                        ),
                      ],
                    ),
                ],
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
              child: const Text('Salvar Pré-Registro'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    final serial = serialCtrl.text.trim().toUpperCase();
    if (serial.length < 4) return;

    try {
      await settings.apiClient.preProvisionOnu({
        'serial': serial,
        'subscriber_name': subCtrl.text.trim().isNotEmpty
            ? subCtrl.text.trim()
            : 'Assinante $serial',
        'contract_id': contractCtrl.text.trim().isNotEmpty
            ? contractCtrl.text.trim()
            : null,
        if (selectedPresetId != null) 'preset_id': selectedPresetId,
        'vlan': int.tryParse(vlanCtrl.text.trim()) ?? 100,
        'profile': profileCtrl.text.trim().isNotEmpty
            ? profileCtrl.text.trim()
            : 'DEFAULT',
        if (appState.selectedOlt?.id != null)
          'olt_id': appState.selectedOlt!.id,
        if (selectedZoneId != null) 'zone_id': selectedZoneId,
        if (selectedOdbId != null) 'odb_id': selectedOdbId,
        if (int.tryParse(splitterPortCtrl.text.trim()) != null)
          'odb_splitter_port': int.parse(splitterPortCtrl.text.trim()),
      });
      await appState.loadConfiguredOnus();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusOnline,
          content: Text(
            'ONU $serial pré-provisionada com sucesso (status PRE_PROVISIONED)!',
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text('Erro ao pré-provisionar: $e'),
        ),
      );
    }
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
                        'Aguardando Autorização',
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
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: _showPreProvisionDialog,
                    icon: const Icon(Icons.inventory_2_outlined, size: 16),
                    label: const Text('Pré-Provisionar Serial'),
                  ),
                  ElevatedButton.icon(
                    onPressed: isLoading || selectedOlt == null
                        ? null
                        : () {
                            appState.loadUnauthorizedOnus();
                            _loadActiveTasks();
                          },
                    icon: isLoading
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.refresh, size: 16),
                    label: const Text('Escanear PON'),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Active Cutover Tasks Banner
          if (_activeTasks.isNotEmpty) ...[
            ..._activeTasks.map((task) {
              final minutes = task.remainingSeconds ~/ 60;
              final seconds = task.remainingSeconds % 60;
              final timeStr = '${minutes}m ${seconds}s';
              return Container(
                margin: const EdgeInsets.only(bottom: 16),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: BoxDecoration(
                  color: AppColors.statusWarning.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.statusWarning.withValues(alpha: 0.5)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.bolt, color: AppColors.statusWarning, size: 24),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              const Text(
                                'Modo Cutover Zero-Touch Ativo',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: AppColors.statusWarning,
                                  fontSize: 14,
                                ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: AppColors.surface,
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  'PON ${task.port}',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 2),
                          Text(
                            'Tempo restante: $timeStr • ${task.onusProvisionedCount} ONU(s) auto-provisionadas • '
                            'VLAN: ${task.defaultVlan} • Perfil: ${task.defaultProfile ?? "Nenhum"}',
                            style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                          ),
                        ],
                      ),
                    ),
                    OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.statusDanger,
                        side: const BorderSide(color: AppColors.statusDanger),
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                      ),
                      onPressed: () => _cancelTask(task),
                      icon: const Icon(Icons.stop_circle_outlined, size: 16),
                      label: const Text('Encerrar Cutover', style: TextStyle(fontSize: 12)),
                    ),
                  ],
                ),
              );
            }),
          ],

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
