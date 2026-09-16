import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../models/pon_policy_model.dart';
import '../../providers/settings_provider.dart';

class PonPoliciesDialog extends StatefulWidget {
  final OltModel olt;

  const PonPoliciesDialog({super.key, required this.olt});

  @override
  State<PonPoliciesDialog> createState() => _PonPoliciesDialogState();
}

class _PonPoliciesDialogState extends State<PonPoliciesDialog> {
  bool _isLoading = true;
  String? _errorMessage;
  ProvisioningSchemaModel? _schema;
  List<PonPolicyModel> _policies = [];
  String? _editingPort;

  final _vlanController = TextEditingController();
  final _lineProfileController = TextEditingController();
  final _srvProfileController = TextEditingController();
  String _selectedMode = 'transparent';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  @override
  void dispose() {
    _vlanController.dispose();
    _lineProfileController.dispose();
    _srvProfileController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    final settings = context.read<SettingsProvider>();
    try {
      final schemaFuture = settings.apiClient.getProvisioningSchema(widget.olt.id);
      final policiesFuture = settings.apiClient.getPonPolicies(widget.olt.id);

      final results = await Future.wait([schemaFuture, policiesFuture]);
      if (mounted) {
        setState(() {
          _schema = results[0] as ProvisioningSchemaModel;
          _policies = results[1] as List<PonPolicyModel>;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  void _startEditing(String port) {
    final existing = _policies.firstWhere(
      (p) => p.port == port,
      orElse: () => PonPolicyModel(
        id: '',
        oltId: widget.olt.id,
        port: port,
        defaultVlan: _schema?.availableVlans.isNotEmpty == true
            ? (_schema!.availableVlans[0]['id'] as int? ?? 100)
            : 100,
        defaultMode: 'transparent',
      ),
    );

    setState(() {
      _editingPort = port;
      _vlanController.text = existing.defaultVlan.toString();
      _selectedMode = existing.defaultMode;
      _lineProfileController.text = existing.defaultLineProfile ?? 'DEFAULT';
      _srvProfileController.text = existing.defaultSrvProfile ?? 'DEFAULT';
    });
  }

  Future<void> _savePolicy(String port) async {
    final settings = context.read<SettingsProvider>();
    final vlan = int.tryParse(_vlanController.text.trim()) ?? 100;

    final policyData = {
      'port': port,
      'default_vlan': vlan,
      'default_mode': _selectedMode,
      'default_line_profile': _lineProfileController.text.trim(),
      'default_srv_profile': _srvProfileController.text.trim(),
      'vendor_parameters': {},
      'auto_authorize_enabled': false,
    };

    try {
      await settings.apiClient.savePonPolicy(widget.olt.id, port, policyData);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Configuração da porta PON $port salva com sucesso!'),
            backgroundColor: AppColors.statusOnline,
          ),
        );
        setState(() => _editingPort = null);
        _loadData();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Erro ao salvar: $e'),
            backgroundColor: AppColors.statusDanger,
          ),
        );
      }
    }
  }

  Future<void> _startCutoverTask(String port) async {
    final settings = context.read<SettingsProvider>();
    int durationMinutes = 120;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: Row(
          children: [
            const Icon(Icons.flash_on, color: AppColors.statusWarning),
            const SizedBox(width: 8),
            Text('Iniciar Cutover na PON $port', style: const TextStyle(color: AppColors.textPrimary)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Durante a janela ativa, todas as novas ONUs detectadas nesta porta serão provisionadas automaticamente com os defaults da PON.',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
            ),
            const SizedBox(height: 16),
            const Text('Duração da Janela:', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            DropdownButtonFormField<int>(
              initialValue: durationMinutes,
              dropdownColor: AppColors.surface,
              style: const TextStyle(color: AppColors.textPrimary),
              decoration: const InputDecoration(border: OutlineInputBorder()),
              items: const [
                DropdownMenuItem(value: 30, child: Text('30 minutos')),
                DropdownMenuItem(value: 60, child: Text('1 hora')),
                DropdownMenuItem(value: 120, child: Text('2 horas (Recomendado)')),
                DropdownMenuItem(value: 240, child: Text('4 horas')),
              ],
              onChanged: (val) {
                if (val != null) durationMinutes = val;
              },
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Iniciar Janela'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        final existingPolicy = _policies.firstWhere((p) => p.port == port, orElse: () => PonPolicyModel(
          id: '',
          oltId: widget.olt.id,
          port: port,
          defaultVlan: 100,
        ));

        await settings.apiClient.createAutoProvisionTask(widget.olt.id, {
          'pon_port': port,
          'target_vlan': existingPolicy.defaultVlan,
          'duration_minutes': durationMinutes,
          'default_mode': existingPolicy.defaultMode,
          'default_line_profile': existingPolicy.defaultLineProfile,
          'default_srv_profile': existingPolicy.defaultSrvProfile,
          'created_by': 'Operador_NOC',
        });

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Janela de Cutover iniciada na PON $port por $durationMinutes min!'),
              backgroundColor: AppColors.statusOnline,
            ),
          );
          Navigator.of(context).pop();
        }
      } catch (e) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Erro ao iniciar janela de cutover: $e'),
              backgroundColor: AppColors.statusDanger,
            ),
          );
        }
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final ports = _schema?.ports.isNotEmpty == true
        ? _schema!.ports
        : ['0/1', '0/2', '0/3', '0/4'];

    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.surfaceBorder, width: 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 850, maxHeight: 680),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
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
                          child: const Icon(Icons.settings_input_component_outlined, color: AppColors.primaryLight, size: 22),
                        ),
                        const SizedBox(width: 12),
                        Flexible(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Políticas Padrão das Portas PON — ${widget.olt.name}',
                                style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                                overflow: TextOverflow.ellipsis,
                              ),
                              Text(
                                'Fabricante: ${widget.olt.vendor.toUpperCase()} • Modelo: ${widget.olt.model}',
                                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
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
                  ),
                ],
              ),
              const SizedBox(height: 16),
              const Divider(color: AppColors.surfaceBorder, height: 1),
              const SizedBox(height: 16),

              // Content
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator())
                    : _errorMessage != null
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                const Icon(Icons.error_outline, color: AppColors.statusDanger, size: 36),
                                const SizedBox(height: 8),
                                Text(_errorMessage!, style: const TextStyle(color: AppColors.textSecondary)),
                                const SizedBox(height: 12),
                                ElevatedButton(onPressed: _loadData, child: const Text('Tentar Novamente')),
                              ],
                            ),
                          )
                        : ListView.separated(
                            itemCount: ports.length,
                            separatorBuilder: (_, _) => const SizedBox(height: 12),
                            itemBuilder: (ctx, index) {
                              final port = ports[index];
                              final policy = _policies.firstWhere(
                                (p) => p.port == port,
                                orElse: () => PonPolicyModel(
                                  id: '',
                                  oltId: widget.olt.id,
                                  port: port,
                                  defaultVlan: 100,
                                ),
                              );

                              final isEditing = _editingPort == port;

                              return Container(
                                decoration: BoxDecoration(
                                  color: AppColors.background,
                                  borderRadius: BorderRadius.circular(8),
                                  border: Border.all(color: isEditing ? AppColors.primary : AppColors.surfaceBorder),
                                ),
                                padding: const EdgeInsets.all(16),
                                child: isEditing
                                    ? Column(
                                        crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Row(
                                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                            children: [
                                              Text('Configurando PON $port', style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.primaryLight)),
                                              IconButton(
                                                icon: const Icon(Icons.close, size: 16, color: AppColors.textSecondary),
                                                onPressed: () => setState(() => _editingPort = null),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 12),
                                          Wrap(
                                            spacing: 12,
                                            runSpacing: 12,
                                            crossAxisAlignment: WrapCrossAlignment.center,
                                            children: [
                                              SizedBox(
                                                width: 140,
                                                child: TextField(
                                                  controller: _vlanController,
                                                  keyboardType: TextInputType.number,
                                                  decoration: const InputDecoration(labelText: 'VLAN Padrão', isDense: true),
                                                ),
                                              ),
                                              SizedBox(
                                                width: 170,
                                                child: DropdownButtonFormField<String>(
                                                  initialValue: _selectedMode,
                                                  dropdownColor: AppColors.surface,
                                                  decoration: const InputDecoration(labelText: 'Modo', isDense: true),
                                                  items: const [
                                                    DropdownMenuItem(value: 'transparent', child: Text('Transparente')),
                                                    DropdownMenuItem(value: 'bridge', child: Text('Bridge')),
                                                    DropdownMenuItem(value: 'router', child: Text('Router')),
                                                  ],
                                                  onChanged: (val) {
                                                    if (val != null) setState(() => _selectedMode = val);
                                                  },
                                                ),
                                              ),
                                              SizedBox(
                                                width: 180,
                                                child: TextField(
                                                  controller: _lineProfileController,
                                                  decoration: const InputDecoration(labelText: 'Line Profile', isDense: true),
                                                ),
                                              ),
                                              SizedBox(
                                                width: 180,
                                                child: TextField(
                                                  controller: _srvProfileController,
                                                  decoration: const InputDecoration(labelText: 'Srv Profile', isDense: true),
                                                ),
                                              ),
                                            ],
                                          ),
                                          const SizedBox(height: 16),
                                          Row(
                                            mainAxisAlignment: MainAxisAlignment.end,
                                            children: [
                                              TextButton(
                                                onPressed: () => setState(() => _editingPort = null),
                                                child: const Text('Cancelar'),
                                              ),
                                              const SizedBox(width: 8),
                                              ElevatedButton.icon(
                                                style: ElevatedButton.styleFrom(backgroundColor: AppColors.primary),
                                                icon: const Icon(Icons.save, size: 16),
                                                label: const Text('Salvar Padrão'),
                                                onPressed: () => _savePolicy(port),
                                              ),
                                            ],
                                          ),
                                        ],
                                      )
                                    : Row(
                                        children: [
                                          Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                            decoration: BoxDecoration(
                                              color: AppColors.surfaceBorder.withValues(alpha: 0.5),
                                              borderRadius: BorderRadius.circular(6),
                                            ),
                                            child: Text('PON $port', style: const TextStyle(fontWeight: FontWeight.bold, color: AppColors.textPrimary)),
                                          ),
                                          const SizedBox(width: 16),
                                          Expanded(
                                            child: Wrap(
                                              spacing: 16,
                                              runSpacing: 4,
                                              children: [
                                                Text('VLAN Padrão: ${policy.defaultVlan}', style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600)),
                                                Text('Modo: ${policy.defaultMode}', style: const TextStyle(color: AppColors.textSecondary)),
                                                if (policy.defaultLineProfile != null)
                                                  Text('Line: ${policy.defaultLineProfile}', style: const TextStyle(color: AppColors.textSecondary)),
                                                if (policy.defaultSrvProfile != null)
                                                  Text('Srv: ${policy.defaultSrvProfile}', style: const TextStyle(color: AppColors.textSecondary)),
                                              ],
                                            ),
                                          ),
                                          OutlinedButton.icon(
                                            style: OutlinedButton.styleFrom(
                                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                              side: const BorderSide(color: AppColors.surfaceBorder),
                                            ),
                                            icon: const Icon(Icons.edit, size: 14, color: AppColors.textSecondary),
                                            label: const Text('Editar', style: TextStyle(fontSize: 12, color: AppColors.textPrimary)),
                                            onPressed: () => _startEditing(port),
                                          ),
                                          const SizedBox(width: 8),
                                          ElevatedButton.icon(
                                            style: ElevatedButton.styleFrom(
                                              backgroundColor: AppColors.primary.withValues(alpha: 0.8),
                                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                            ),
                                            icon: const Icon(Icons.flash_on, size: 14),
                                            label: const Text('Cutover', style: TextStyle(fontSize: 12)),
                                            onPressed: () => _startCutoverTask(port),
                                          ),
                                        ],
                                      ),
                              );
                            },
                          ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
