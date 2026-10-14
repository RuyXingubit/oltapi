import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../models/vlan_model.dart';
import '../../providers/app_state.dart';

class OltVlansDialog extends StatefulWidget {
  final OltModel olt;

  const OltVlansDialog({super.key, required this.olt});

  @override
  State<OltVlansDialog> createState() => _OltVlansDialogState();
}

class _OltVlansDialogState extends State<OltVlansDialog> {
  final _createFormKey = GlobalKey<FormState>();
  final _vlanIdCtrl = TextEditingController();
  final _nameCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _uplinksCtrl = TextEditingController();

  List<VlanMetricsModel> _vlans = [];
  bool _isLoading = true;
  bool _isCreating = false;
  bool _isEnriching = false;
  bool _showCreateForm = false;
  String? _error;
  String? _infoMessage;

  int? _selectedVlanForHistory;
  List<VlanHistoryModel> _historyItems = [];
  bool _isLoadingHistory = false;

  @override
  void initState() {
    super.initState();
    _loadVlans();
  }

  @override
  void dispose() {
    _vlanIdCtrl.dispose();
    _nameCtrl.dispose();
    _descCtrl.dispose();
    _uplinksCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadVlans() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final api = context.read<AppState>().apiClient;
      final list = await api.getOltVlanMetrics(widget.olt.id);
      if (mounted) {
        setState(() {
          _vlans = list;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Falha ao carregar catálogo de VLANs: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _createVlan() async {
    if (!_createFormKey.currentState!.validate()) return;

    setState(() {
      _isCreating = true;
      _error = null;
      _infoMessage = null;
    });

    try {
      final vlanId = int.parse(_vlanIdCtrl.text.trim());
      final uplinks = _uplinksCtrl.text
          .split(',')
          .map((s) => s.trim())
          .where((s) => s.isNotEmpty)
          .toList();

      final payload = <String, dynamic>{
        'vlan_id': vlanId,
        if (_nameCtrl.text.trim().isNotEmpty) 'name': _nameCtrl.text.trim(),
        if (_descCtrl.text.trim().isNotEmpty) 'description': _descCtrl.text.trim(),
        if (uplinks.isNotEmpty) 'tagged_uplink_ports': uplinks,
      };

      final api = context.read<AppState>().apiClient;
      await api.createOltVlan(widget.olt.id, payload);

      _vlanIdCtrl.clear();
      _nameCtrl.clear();
      _descCtrl.clear();
      _uplinksCtrl.clear();

      if (mounted) {
        setState(() {
          _showCreateForm = false;
          _infoMessage = 'VLAN $vlanId criada e gravada no Flash com sucesso.';
        });
      }
      await _loadVlans();
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Erro ao criar VLAN: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isCreating = false);
      }
    }
  }

  Future<void> _enrichVlans() async {
    setState(() {
      _isEnriching = true;
      _error = null;
      _infoMessage = null;
    });
    try {
      final api = context.read<AppState>().apiClient;
      final res = await api.enrichOltVlans(widget.olt.id, force: true);
      if (mounted) {
        setState(() {
          _infoMessage = res['message']?.toString() ?? 'Enriquecimento de VLANs em segundo plano agendado.';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Falha ao disparar enriquecimento de VLANs: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isEnriching = false);
      }
    }
  }

  Future<void> _loadHistory(int vlanId) async {
    setState(() {
      _selectedVlanForHistory = vlanId;
      _isLoadingHistory = true;
      _historyItems = [];
    });
    try {
      final api = context.read<AppState>().apiClient;
      final history = await api.getOltVlanHistory(widget.olt.id, vlanId);
      if (mounted) {
        setState(() {
          _historyItems = history;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Falha ao buscar histórico da VLAN $vlanId: $e';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isLoadingHistory = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 840, maxHeight: 720),
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
                  child: Text(_error!, style: const TextStyle(color: AppColors.statusDanger, fontSize: 13)),
                ),
                const SizedBox(height: 12),
              ],
              if (_infoMessage != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.statusOnline.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.statusOnline.withValues(alpha: 0.4)),
                  ),
                  child: Text(_infoMessage!, style: const TextStyle(color: AppColors.statusOnline, fontSize: 13)),
                ),
                const SizedBox(height: 12),
              ],
              if (_showCreateForm) ...[
                _buildCreateVlanPanel(),
                const SizedBox(height: 16),
              ],
              Flexible(
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _buildVlansTableOrList(),
                      if (_selectedVlanForHistory != null) ...[
                        const SizedBox(height: 18),
                        _buildHistorySection(),
                      ],
                    ],
                  ),
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
              const Icon(Icons.lan, color: AppColors.primary),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Catálogo Flash de VLANs & Ocupação — ${widget.olt.name}',
                      style: const TextStyle(
                        fontSize: 19,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                    Text(
                      '${widget.olt.vendor.toUpperCase()} ${widget.olt.model} • Métricas de ONUs por VLAN e Auditoria',
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

  Widget _buildCreateVlanPanel() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.primary.withValues(alpha: 0.4)),
      ),
      child: Form(
        key: _createFormKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Nova VLAN na OLT (Hardware + Banco)',
              style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold, fontSize: 14),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  flex: 1,
                  child: TextFormField(
                    controller: _vlanIdCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'VLAN ID (1-4094)'),
                    validator: (v) {
                      final id = int.tryParse(v?.trim() ?? '');
                      if (id == null || id < 1 || id > 4094) return '1-4094';
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    controller: _nameCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Nome da VLAN (Opcional)'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: TextFormField(
                    controller: _uplinksCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Uplinks Tagged (ex: 19/1, 20/1)'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _descCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Descrição / Observação Operacional'),
                  ),
                ),
                const SizedBox(width: 12),
                TextButton(
                  onPressed: _isCreating ? null : () => setState(() => _showCreateForm = false),
                  child: const Text('Cancelar', style: TextStyle(color: AppColors.textSecondary)),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: _isCreating ? null : _createVlan,
                  icon: _isCreating
                      ? const SizedBox(
                          width: 14,
                          height: 14,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.save, size: 16),
                  label: const Text('Aplicar na OLT'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVlansTableOrList() {
    if (_isLoading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 48),
        child: Center(child: CircularProgressIndicator()),
      );
    }

    if (_vlans.isEmpty) {
      return Container(
        padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 16),
        decoration: BoxDecoration(
          color: AppColors.background,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: AppColors.surfaceBorder),
        ),
        child: const Center(
          child: Text(
            'Nenhuma VLAN registrada no catálogo desta OLT. Execute uma Sincronização Brownfield no Raio-X ou crie uma nova VLAN.',
            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return Column(
      children: _vlans.map((v) {
        final isSelected = _selectedVlanForHistory == v.vlanId;
        return Card(
          color: isSelected ? AppColors.surfaceHover : AppColors.background,
          margin: const EdgeInsets.only(bottom: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: BorderSide(
              color: isSelected ? AppColors.primary : AppColors.surfaceBorder,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 12,
              runSpacing: 8,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: AppColors.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        'VLAN ${v.vlanId}',
                        style: const TextStyle(
                          color: AppColors.primary,
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 260),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            v.name != null && v.name!.isNotEmpty ? v.name! : 'Sem nome configurado',
                            style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontWeight: FontWeight.w600,
                              fontSize: 14,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                          if (v.description != null && v.description!.isNotEmpty)
                            Text(
                              v.description!,
                              style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    _buildMiniCounter('Provisionadas', v.totalProvisionedOnus, AppColors.textPrimary),
                    _buildMiniCounter('Ativas', v.totalActiveOnus, AppColors.statusOnline),
                    if (v.taggedPorts.isNotEmpty)
                      _buildMiniCounter('Uplinks', v.taggedPorts.length, AppColors.primary),
                    TextButton.icon(
                      onPressed: () => _loadHistory(v.vlanId),
                      icon: const Icon(Icons.history, size: 16),
                      label: const Text('Histórico'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildMiniCounter(String label, int count, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Text(
        '$label: $count',
        style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
      ),
    );
  }

  Widget _buildHistorySection() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Histórico de Auditoria — VLAN $_selectedVlanForHistory',
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.close, size: 18, color: AppColors.textSecondary),
                onPressed: () => setState(() => _selectedVlanForHistory = null),
              ),
            ],
          ),
          const SizedBox(height: 8),
          if (_isLoadingHistory)
            const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_historyItems.isEmpty)
            const Text(
              'Nenhum evento de histórico registrado para esta VLAN.',
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            )
          else
            ..._historyItems.map(
              (item) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Icon(
                      item.isCurrent ? Icons.check_circle : Icons.history,
                      size: 15,
                      color: item.isCurrent ? AppColors.statusOnline : AppColors.textSecondary,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        '[${item.reason.toUpperCase()}] ONU ${item.serial} '
                        '(${item.subscriberName ?? "Sem assinante"}) • Porta: ${item.port ?? "-"}',
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 12),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text(
                      item.startedAt?.toIso8601String() ?? '-',
                      style: const TextStyle(color: AppColors.textSecondary, fontSize: 11),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildFooter() {
    return Wrap(
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 12,
      runSpacing: 8,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            ElevatedButton.icon(
              onPressed: _isLoading
                  ? null
                  : () => setState(() => _showCreateForm = !_showCreateForm),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Nova VLAN na OLT'),
            ),
            OutlinedButton.icon(
              onPressed: (_isLoading || _isEnriching) ? null : _enrichVlans,
              icon: _isEnriching
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.auto_awesome, size: 18),
              label: const Text('Enriquecer VLANs das ONUs'),
            ),
          ],
        ),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextButton.icon(
              onPressed: _isLoading ? null : _loadVlans,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Atualizar'),
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
