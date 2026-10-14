import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';

class _WizardServiceDraft {
  final TextEditingController vlanIdCtrl = TextEditingController();
  final TextEditingController nameCtrl = TextEditingController();
  final TextEditingController uplinkPortCtrl = TextEditingController();
  final TextEditingController testPortCtrl = TextEditingController();
  String purpose = 'pppoe_router';
  bool tagged = true;

  void dispose() {
    vlanIdCtrl.dispose();
    nameCtrl.dispose();
    uplinkPortCtrl.dispose();
    testPortCtrl.dispose();
  }
}

class OltOnboardWizardDialog extends StatefulWidget {
  const OltOnboardWizardDialog({super.key});

  @override
  State<OltOnboardWizardDialog> createState() => _OltOnboardWizardDialogState();
}

class _OltOnboardWizardDialogState extends State<OltOnboardWizardDialog> {
  final _phase1FormKey = GlobalKey<FormState>();
  final _phase2FormKey = GlobalKey<FormState>();

  // Phase 1 Controllers
  final _nameCtrl = TextEditingController();
  final _hostCtrl = TextEditingController();
  final _customPortCtrl = TextEditingController();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();

  // Phase 2 Inband Controllers
  bool _configureInband = false;
  final _inbandVlanCtrl = TextEditingController();
  final _inbandNameCtrl = TextEditingController(text: 'MGMT_INBAND');
  final _inbandUplinkCtrl = TextEditingController();
  final _inbandIpCidrCtrl = TextEditingController();
  final _inbandGatewayCtrl = TextEditingController();
  bool _inbandTagged = true;

  // Phase 2 Services & QoS
  final List<_WizardServiceDraft> _services = [];
  String _qosPolicyType = 'transparent_1g';
  final _upstreamKbpsCtrl = TextEditingController(text: '1000000');
  final _downstreamKbpsCtrl = TextEditingController(text: '1000000');

  int _currentPhase = 1; // 1 = Inspect/Creds, 2 = Configure Wizard, 3 = Result Summary
  bool _isLoading = false;
  String? _error;

  OltInspectResultModel? _inspectResult;
  OltOnboardResultModel? _onboardResult;

  static const Map<String, String> _purposeLabels = {
    'pppoe_router': 'PPPoE Router (NAT/Wi-Fi)',
    'pppoe_bridge': 'PPPoE Bridge',
    'ipoe': 'IPoE / DHCP',
    'rede_neutra': 'Rede Neutra (Wholesale)',
    'lan_to_lan': 'LAN-to-LAN (Corporativo)',
  };

  @override
  void dispose() {
    _nameCtrl.dispose();
    _hostCtrl.dispose();
    _customPortCtrl.dispose();
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    _inbandVlanCtrl.dispose();
    _inbandNameCtrl.dispose();
    _inbandUplinkCtrl.dispose();
    _inbandIpCidrCtrl.dispose();
    _inbandGatewayCtrl.dispose();
    _upstreamKbpsCtrl.dispose();
    _downstreamKbpsCtrl.dispose();
    for (final s in _services) {
      s.dispose();
    }
    super.dispose();
  }

  Map<String, dynamic> _buildBaseCredentialsPayload({bool includeName = true}) {
    final map = <String, dynamic>{
      'host': _hostCtrl.text.trim(),
      'username': _usernameCtrl.text.trim(),
      'password': _passwordCtrl.text.trim(),
    };
    if (includeName) {
      map['name'] = _nameCtrl.text.trim();
    }
    final customPort = int.tryParse(_customPortCtrl.text.trim());
    if (customPort != null && customPort > 0) {
      map['custom_port'] = customPort;
    }
    return map;
  }

  Future<void> _runPhase1Inspect() async {
    if (!_phase1FormKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final apiClient = context.read<AppState>().apiClient;
      final res = await apiClient.inspectOlt(
        _buildBaseCredentialsPayload(includeName: false),
      );
      if (!mounted) return;
      setState(() {
        _inspectResult = res;
        _configureInband = res.accessScenario == 'aux_only';
        if (res.gateway != null && res.gateway!.isNotEmpty) {
          _inbandGatewayCtrl.text = res.gateway!;
        }
        _currentPhase = 2;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Falha na inspeção (Fase 1): $e';
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _runZeroTouchOnboard() async {
    if (!_phase1FormKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final appState = context.read<AppState>();
      final res = await appState.apiClient.onboardOltZeroTouch(
        _buildBaseCredentialsPayload(includeName: true),
      );
      await appState.loadOlts();
      if (!mounted) return;
      setState(() {
        _onboardResult = res;
        _currentPhase = 3;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Falha no Onboarding Zero-Touch: $e';
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _runPhase2WizardOnboard() async {
    if (!_phase2FormKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final payload = _buildBaseCredentialsPayload(includeName: true);

      if (_configureInband) {
        payload['inband_config'] = {
          'vlan_id': int.parse(_inbandVlanCtrl.text.trim()),
          'name': _inbandNameCtrl.text.trim().isEmpty
              ? 'MGMT_INBAND'
              : _inbandNameCtrl.text.trim(),
          'uplink_port': _inbandUplinkCtrl.text.trim(),
          'ip_cidr': _inbandIpCidrCtrl.text.trim(),
          'gateway': _inbandGatewayCtrl.text.trim(),
          'tagged': _inbandTagged,
        };
      }

      payload['services'] = _services.map((s) {
        final item = <String, dynamic>{
          'vlan_id': int.parse(s.vlanIdCtrl.text.trim()),
          'name': s.nameCtrl.text.trim(),
          'purpose': s.purpose,
          'uplink_port': s.uplinkPortCtrl.text.trim(),
          'tagged': s.tagged,
        };
        if (s.testPortCtrl.text.trim().isNotEmpty) {
          item['test_port'] = s.testPortCtrl.text.trim();
        }
        return item;
      }).toList();

      payload['qos_policy'] = {
        'policy_type': _qosPolicyType,
        'upstream_kbps': int.tryParse(_upstreamKbpsCtrl.text.trim()) ?? 1000000,
        'downstream_kbps': int.tryParse(_downstreamKbpsCtrl.text.trim()) ?? 1000000,
      };

      final appState = context.read<AppState>();
      final res = await appState.apiClient.onboardOltWizard(payload);
      await appState.loadOlts();

      if (!mounted) return;
      setState(() {
        _onboardResult = res;
        _currentPhase = 3;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Falha no Comissionamento (Fase 2): $e';
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _addServiceDraft() {
    setState(() {
      _services.add(_WizardServiceDraft());
    });
  }

  void _removeServiceDraft(int index) {
    setState(() {
      final removed = _services.removeAt(index);
      removed.dispose();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 780, maxHeight: 720),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _buildHeader(),
              const SizedBox(height: 12),
              _buildStepIndicator(),
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
                const SizedBox(height: 16),
              ],
              Flexible(
                child: SingleChildScrollView(
                  child: _buildPhaseContent(),
                ),
              ),
              const SizedBox(height: 20),
              _buildFooterActions(),
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
        const Expanded(
          child: Row(
            children: [
              Icon(Icons.auto_fix_high, color: AppColors.primary),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Onboarding Wizard & Descoberta Zero-Touch',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ),
        IconButton(
          icon: const Icon(Icons.close, color: AppColors.textSecondary),
          onPressed: _isLoading ? null : () => Navigator.of(context).pop(_onboardResult != null),
        ),
      ],
    );
  }

  Widget _buildStepIndicator() {
    return Wrap(
      spacing: 12,
      runSpacing: 8,
      children: [
        _buildStepChip(1, 'Fase 1: Inspeção / Acesso'),
        _buildStepChip(2, 'Fase 2: Arquitetura & VLANs'),
        _buildStepChip(3, 'Resultado do Comissionamento'),
      ],
    );
  }

  Widget _buildStepChip(int phase, String label) {
    final isActive = _currentPhase == phase;
    final isDone = _currentPhase > phase;
    final bgColor = isActive
        ? AppColors.primary.withValues(alpha: 0.2)
        : (isDone ? AppColors.statusOnline.withValues(alpha: 0.15) : AppColors.background);
    final borderColor = isActive
        ? AppColors.primary
        : (isDone ? AppColors.statusOnline : AppColors.surfaceBorder);
    final textColor = isActive
        ? AppColors.primary
        : (isDone ? AppColors.statusOnline : AppColors.textSecondary);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: borderColor),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            isDone ? Icons.check_circle : Icons.circle,
            size: 14,
            color: textColor,
          ),
          const SizedBox(width: 6),
          Text(
            label,
            style: TextStyle(
              color: textColor,
              fontSize: 12,
              fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPhaseContent() {
    if (_currentPhase == 1) {
      return _buildPhase1Form();
    } else if (_currentPhase == 2) {
      return _buildPhase2Form();
    } else {
      return _buildPhase3Summary();
    }
  }

  Widget _buildPhase1Form() {
    return Form(
      key: _phase1FormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Informe os dados de acesso da OLT. Você pode inspecionar a arquitetura de gerência e VLANs antes de comissionar (2 Fases) ou executar o Onboarding Zero-Touch em 1 clique.',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _nameCtrl,
            style: const TextStyle(color: AppColors.textPrimary),
            decoration: const InputDecoration(
              labelText: 'Nome de Identificação da OLT',
              prefixIcon: Icon(Icons.label, color: AppColors.textSecondary, size: 20),
            ),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o nome da OLT' : null,
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                flex: 3,
                child: TextFormField(
                  controller: _hostCtrl,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Endereço IP / Host da OLT',
                    prefixIcon: Icon(Icons.computer, color: AppColors.textSecondary, size: 20),
                  ),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o IP ou Host' : null,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                flex: 2,
                child: TextFormField(
                  controller: _customPortCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Porta Customizada (Opcional)',
                    prefixIcon: Icon(Icons.numbers, color: AppColors.textSecondary, size: 20),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextFormField(
                  controller: _usernameCtrl,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Usuário Admin CLI',
                    prefixIcon: Icon(Icons.person, color: AppColors.textSecondary, size: 20),
                  ),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe o usuário' : null,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: TextFormField(
                  controller: _passwordCtrl,
                  obscureText: true,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Senha CLI',
                    prefixIcon: Icon(Icons.lock, color: AppColors.textSecondary, size: 20),
                  ),
                  validator: (v) => (v == null || v.trim().isEmpty) ? 'Informe a senha' : null,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPhase2Form() {
    final inspect = _inspectResult!;
    return Form(
      key: _phase2FormKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.background,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 16,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      'Hardware Detectado: ${inspect.vendor.toUpperCase()} — ${inspect.model}',
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        'Cenário: ${inspect.accessScenario}',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontSize: 12,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  inspect.promptMessage,
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 16,
                  runSpacing: 6,
                  children: [
                    Text(
                      'ONUs Detectadas: ${inspect.totalOnusDetected}',
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                    ),
                    if (inspect.auxIp != null && inspect.auxIp!.isNotEmpty)
                      Text(
                        'IP Aux: ${inspect.auxIp}',
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                      ),
                    if (inspect.gateway != null && inspect.gateway!.isNotEmpty)
                      Text(
                        'Gateway: ${inspect.gateway}',
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                      ),
                    Text(
                      'VLANs no Flash: ${inspect.existingVlans.isEmpty ? "Nenhuma" : inspect.existingVlans.join(", ")}',
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                    ),
                  ],
                ),
                if (inspect.existingSvis.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  const Text(
                    'SVIs L3 Existentes:',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: inspect.existingSvis
                        .map(
                          (svi) => Chip(
                            backgroundColor: AppColors.surface,
                            label: Text(
                              'VLAN ${svi.vlanId}${svi.name != null ? " (${svi.name})" : ""}: ${svi.ipCidr ?? "-"}',
                              style: const TextStyle(color: AppColors.textPrimary, fontSize: 11),
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text(
              'Configurar Gerência Inband (VLAN + SVI L3)',
              style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
            ),
            subtitle: const Text(
              'Cria VLAN de gerência, aplica tag no uplink e configura IP/Gateway na OLT',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
            value: _configureInband,
            onChanged: (val) => setState(() => _configureInband = val),
          ),
          if (_configureInband) ...[
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _inbandVlanCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'VLAN ID Inband'),
                    validator: (v) {
                      if (!_configureInband) return null;
                      final id = int.tryParse(v?.trim() ?? '');
                      if (id == null || id < 1 || id > 4094) return 'VLAN 1-4094';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _inbandNameCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Nome da VLAN'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _inbandUplinkCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Porta Uplink (ex: 19/1)'),
                    validator: (v) {
                      if (!_configureInband) return null;
                      if (v == null || v.trim().isEmpty) return 'Obrigatório';
                      return null;
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    controller: _inbandIpCidrCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'IP/CIDR (ex: 10.250.0.2/24)'),
                    validator: (v) {
                      if (!_configureInband) return null;
                      if (v == null || !v.contains('/')) return 'Informe IP/CIDR';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    controller: _inbandGatewayCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Gateway (ex: 10.250.0.1)'),
                    validator: (v) {
                      if (!_configureInband) return null;
                      if (v == null || v.trim().isEmpty) return 'Obrigatório';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 1,
                  child: CheckboxListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Tagged', style: TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                    value: _inbandTagged,
                    onChanged: (v) => setState(() => _inbandTagged = v ?? true),
                  ),
                ),
              ],
            ),
          ],
          const Divider(color: AppColors.surfaceBorder, height: 28),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Expanded(
                child: Text(
                  'VLANs de Serviço e Perfis de Provisionamento',
                  style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
                ),
              ),
              TextButton.icon(
                onPressed: _addServiceDraft,
                icon: const Icon(Icons.add_circle_outline, size: 18),
                label: const Text('Adicionar VLAN de Serviço'),
              ),
            ],
          ),
          if (_services.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'Nenhuma VLAN de serviço adicional configurada para criação imediata.',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
              ),
            )
          else
            ..._services.asMap().entries.map((entry) {
              final idx = entry.key;
              final draft = entry.value;
              return Container(
                margin: const EdgeInsets.only(bottom: 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.background,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          flex: 1,
                          child: TextFormField(
                            controller: draft.vlanIdCtrl,
                            keyboardType: TextInputType.number,
                            style: const TextStyle(color: AppColors.textPrimary),
                            decoration: const InputDecoration(labelText: 'VLAN ID'),
                            validator: (v) {
                              final id = int.tryParse(v?.trim() ?? '');
                              if (id == null || id < 1 || id > 4094) return '1-4094';
                              return null;
                            },
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          flex: 2,
                          child: TextFormField(
                            controller: draft.nameCtrl,
                            style: const TextStyle(color: AppColors.textPrimary),
                            decoration: const InputDecoration(labelText: 'Nome da VLAN'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Obrigatório' : null,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          flex: 2,
                          child: DropdownButtonFormField<String>(
                            initialValue: draft.purpose,
                            dropdownColor: AppColors.surfaceHover,
                            decoration: const InputDecoration(labelText: 'Finalidade'),
                            items: _purposeLabels.entries
                                .map(
                                  (e) => DropdownMenuItem(
                                    value: e.key,
                                    child: Text(
                                      e.value,
                                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                )
                                .toList(),
                            onChanged: (v) {
                              if (v != null) setState(() => draft.purpose = v);
                            },
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline, color: AppColors.statusDanger),
                          onPressed: () => _removeServiceDraft(idx),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: TextFormField(
                            controller: draft.uplinkPortCtrl,
                            style: const TextStyle(color: AppColors.textPrimary),
                            decoration: const InputDecoration(labelText: 'Porta Uplink (ex: 19/1)'),
                            validator: (v) => (v == null || v.trim().isEmpty) ? 'Obrigatório' : null,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: TextFormField(
                            controller: draft.testPortCtrl,
                            style: const TextStyle(color: AppColors.textPrimary),
                            decoration: const InputDecoration(labelText: 'Porta Teste PON (Opcional)'),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: CheckboxListTile(
                            contentPadding: EdgeInsets.zero,
                            title: const Text('Tagged', style: TextStyle(color: AppColors.textPrimary, fontSize: 13)),
                            value: draft.tagged,
                            onChanged: (v) => setState(() => draft.tagged = v ?? true),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              );
            }),
          const Divider(color: AppColors.surfaceBorder, height: 28),
          const Text(
            'Política de Banda / QoS Padrão',
            style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                flex: 2,
                child: DropdownButtonFormField<String>(
                  initialValue: _qosPolicyType,
                  dropdownColor: AppColors.surfaceHover,
                  decoration: const InputDecoration(labelText: 'Modo de QoS'),
                  items: const [
                    DropdownMenuItem(
                      value: 'transparent_1g',
                      child: Text('1 Gbps Transparente', style: TextStyle(color: AppColors.textPrimary)),
                    ),
                    DropdownMenuItem(
                      value: 'custom_limits',
                      child: Text('Limites Customizados (Kbps)', style: TextStyle(color: AppColors.textPrimary)),
                    ),
                  ],
                  onChanged: (v) {
                    if (v != null) setState(() => _qosPolicyType = v);
                  },
                ),
              ),
              if (_qosPolicyType == 'custom_limits') ...[
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _upstreamKbpsCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Upstream (Kbps)'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextFormField(
                    controller: _downstreamKbpsCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Downstream (Kbps)'),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildPhase3Summary() {
    final res = _onboardResult!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.statusOnline.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: AppColors.statusOnline.withValues(alpha: 0.4)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.verified, color: AppColors.statusOnline),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'OLT "${res.name}" integrada com sucesso!',
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 16,
                runSpacing: 8,
                children: [
                  Text(
                    'Fabricante/Modelo: ${res.vendor.toUpperCase()} ${res.model}',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                  ),
                  Text(
                    'Protocolo: ${res.protocol.toUpperCase()}:${res.port}',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                  ),
                  Text(
                    'SNMP: ${res.snmpActive ? "Ativo (${res.snmpCommunity})" : "Pendente"}',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                  ),
                  Text(
                    'ONUs Detectadas: ${res.totalOnusDetected} (Novas: ${res.newOnusRegistered})',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                  ),
                  Text(
                    'Portas Ativas: ${res.activePorts}/${res.totalPorts}',
                    style: const TextStyle(color: AppColors.textPrimary, fontSize: 13),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        const Text(
          'Trilha de Auditoria do Onboarding',
          style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        ...res.steps.map(
          (step) => Card(
            color: AppColors.background,
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              dense: true,
              leading: Icon(
                step.status == 'ok' || step.status == 'success' || step.status == 'completed'
                    ? Icons.check_circle
                    : (step.status == 'skipped' ? Icons.remove_circle_outline : Icons.warning_amber),
                color: step.status == 'ok' || step.status == 'success' || step.status == 'completed'
                    ? AppColors.statusOnline
                    : (step.status == 'skipped' ? AppColors.textSecondary : AppColors.statusWarning),
                size: 20,
              ),
              title: Text(
                step.title.isNotEmpty ? step.title : step.stepKey,
                style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w600),
              ),
              subtitle: step.details != null && step.details!.isNotEmpty
                  ? Text(
                      step.details!,
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                    )
                  : null,
              trailing: Text(
                step.status.toUpperCase(),
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFooterActions() {
    if (_currentPhase == 3) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          ElevatedButton.icon(
            onPressed: () => Navigator.of(context).pop(true),
            icon: const Icon(Icons.check),
            label: const Text('Concluir'),
          ),
        ],
      );
    }

    return Wrap(
      alignment: WrapAlignment.end,
      spacing: 12,
      runSpacing: 8,
      children: [
        TextButton(
          onPressed: _isLoading ? null : () => Navigator.of(context).pop(false),
          child: const Text('Cancelar', style: TextStyle(color: AppColors.textSecondary)),
        ),
        if (_currentPhase == 2)
          OutlinedButton.icon(
            onPressed: _isLoading ? null : () => setState(() => _currentPhase = 1),
            icon: const Icon(Icons.arrow_back, size: 16),
            label: const Text('Voltar'),
          ),
        if (_currentPhase == 1) ...[
          OutlinedButton.icon(
            onPressed: _isLoading ? null : _runZeroTouchOnboard,
            icon: const Icon(Icons.bolt, size: 18),
            label: const Text('Zero-Touch 1-Clique'),
          ),
          ElevatedButton.icon(
            onPressed: _isLoading ? null : _runPhase1Inspect,
            icon: _isLoading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.search, size: 18),
            label: const Text('Inspecionar Arquitetura (Fase 1)'),
          ),
        ],
        if (_currentPhase == 2)
          ElevatedButton.icon(
            onPressed: _isLoading ? null : _runPhase2WizardOnboard,
            icon: _isLoading
                ? const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.rocket_launch, size: 18),
            label: const Text('Comissionar OLT (Fase 2)'),
          ),
      ],
    );
  }
}
