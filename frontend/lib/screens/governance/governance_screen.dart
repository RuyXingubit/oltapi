import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/governance_models.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';

class GovernanceScreen extends StatefulWidget {
  const GovernanceScreen({super.key});

  @override
  State<GovernanceScreen> createState() => _GovernanceScreenState();
}

class _GovernanceScreenState extends State<GovernanceScreen> {
  int _activeTab = 0;

  // Scanner & Timeline state
  ScannerStatusModel? _scannerStatus;
  ScannerRunResultModel? _lastScannerRun;
  List<OnuMigrationEventModel> _migrationEvents = [];
  bool _loadingScanner = false;
  String? _scannerError;
  final TextEditingController _historySerialCtrl = TextEditingController();

  // Webhooks state
  List<WebhookSubscriptionModel> _webhooks = [];
  List<WebhookDeliveryLogModel> _deliveries = [];
  bool _loadingWebhooks = false;
  String? _webhooksError;

  // Tenants state
  List<TenantModel> _tenants = [];
  bool _loadingTenants = false;
  String? _tenantsError;

  // Users & API Keys state
  List<UserAccountModel> _users = [];
  List<ApiKeyModel> _apiKeys = [];
  bool _loadingRbac = false;
  String? _rbacError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadCurrentTab();
    });
  }

  @override
  void dispose() {
    _historySerialCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadCurrentTab() async {
    switch (_activeTab) {
      case 0:
        await _loadScannerAndTimeline();
        break;
      case 1:
        await _loadWebhooksData();
        break;
      case 2:
        await _loadTenantsData();
        break;
      case 3:
        await _loadRbacData();
        break;
    }
  }

  Future<void> _loadScannerAndTimeline() async {
    if (!mounted) return;
    setState(() {
      _loadingScanner = true;
      _scannerError = null;
    });
    final api = context.read<AppState>().apiClient;
    try {
      final status = await api.getScannerStatus();
      final history = await api.getOnuHistory(
        serial: _historySerialCtrl.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _scannerStatus = status;
        _migrationEvents = history;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _scannerError = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _loadingScanner = false);
      }
    }
  }

  Future<void> _loadWebhooksData() async {
    if (!mounted) return;
    setState(() {
      _loadingWebhooks = true;
      _webhooksError = null;
    });
    final api = context.read<AppState>().apiClient;
    try {
      final subs = await api.getWebhooks();
      final logs = await api.getWebhookDeliveries();
      if (!mounted) return;
      setState(() {
        _webhooks = subs;
        _deliveries = logs;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _webhooksError = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _loadingWebhooks = false);
      }
    }
  }

  Future<void> _loadTenantsData() async {
    if (!mounted) return;
    setState(() {
      _loadingTenants = true;
      _tenantsError = null;
    });
    final api = context.read<AppState>().apiClient;
    try {
      final list = await api.getTenants();
      if (!mounted) return;
      setState(() {
        _tenants = list;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _tenantsError = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _loadingTenants = false);
      }
    }
  }

  Future<void> _loadRbacData() async {
    if (!mounted) return;
    setState(() {
      _loadingRbac = true;
      _rbacError = null;
    });
    final api = context.read<AppState>().apiClient;
    try {
      final users = await api.getUsers();
      final keys = await api.getApiKeys();
      if (!mounted) return;
      setState(() {
        _users = users;
        _apiKeys = keys;
      });
      if (_tenants.isEmpty) {
        try {
          final t = await api.getTenants();
          if (mounted) setState(() => _tenants = t);
        } catch (_) {}
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _rbacError = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _loadingRbac = false);
      }
    }
  }

  void _showSnack(String msg, {bool isError = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: isError ? AppColors.statusDanger : AppColors.statusOnline,
      ),
    );
  }

  // ==================== SCANNER & TIMELINE ACTIONS ====================

  Future<void> _handleToggleScanner(bool start) async {
    final api = context.read<AppState>().apiClient;
    try {
      final updated = start ? await api.startScanner() : await api.stopScanner();
      if (!mounted) return;
      setState(() => _scannerStatus = updated);
      _showSnack(start ? 'Scanner autônomo iniciado.' : 'Scanner autônomo parado.');
    } catch (e) {
      _showSnack('Erro ao alterar estado do scanner: $e', isError: true);
    }
  }

  Future<void> _handleRunScannerNow() async {
    setState(() => _loadingScanner = true);
    final api = context.read<AppState>().apiClient;
    try {
      final res = await api.runScannerNow();
      final status = await api.getScannerStatus();
      final history = await api.getOnuHistory(
        serial: _historySerialCtrl.text.trim(),
      );
      if (!mounted) return;
      setState(() {
        _lastScannerRun = res;
        _scannerStatus = status;
        _migrationEvents = history;
      });
      _showSnack(
        'Varredura concluída: ${res.detectedOnusCount} detectadas, ${res.reconciledOnusCount} reconciliadas.',
      );
    } catch (e) {
      _showSnack('Falha ao executar ciclo imediato: $e', isError: true);
    } finally {
      if (mounted) setState(() => _loadingScanner = false);
    }
  }

  Future<void> _showUpdateIntervalDialog() async {
    final ctrl = TextEditingController(
      text: (_scannerStatus?.intervalSeconds ?? 60).toString(),
    );
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text(
          'Ajustar Intervalo do Scanner',
          style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
        ),
        content: TextField(
          controller: ctrl,
          keyboardType: TextInputType.number,
          style: const TextStyle(color: AppColors.textPrimary),
          decoration: const InputDecoration(
            labelText: 'Intervalo em segundos (mín. 10s)',
            hintText: '60',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Salvar Intervalo'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    final val = int.tryParse(ctrl.text.trim());
    if (val == null || val < 10) {
      _showSnack('Informe um intervalo válido (mínimo 10 segundos).', isError: true);
      return;
    }
    try {
      final updated = await context.read<AppState>().apiClient.updateScannerInterval(val);
      if (!mounted) return;
      setState(() => _scannerStatus = updated);
      _showSnack('Intervalo atualizado para ${updated.intervalSeconds}s.');
    } catch (e) {
      _showSnack('Erro ao atualizar intervalo: $e', isError: true);
    }
  }

  Future<void> _showReconcileFieldModal() async {
    final olts = context.read<AppState>().olts;
    String? selectedOltId = olts.isNotEmpty ? olts.first.id : null;
    final serialCtrl = TextEditingController();
    final portCtrl = TextEditingController(text: '0/1/1');
    final onuIdCtrl = TextEditingController();
    final reasonCtrl = TextEditingController(text: 'field_maintenance');

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: const Text(
            'Reconciliar Evento de Campo (TR-101)',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 440,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: serialCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Serial da ONU *',
                      hintText: 'Ex: ZTEGC1234567',
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selectedOltId,
                    dropdownColor: AppColors.surface,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'OLT de Destino Detectada *',
                    ),
                    items: olts
                        .map(
                          (o) => DropdownMenuItem(
                            value: o.id,
                            child: Text('${o.name} (${o.host})'),
                          ),
                        )
                        .toList(),
                    onChanged: (v) => setModalState(() => selectedOltId = v),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: portCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Porta PON Detectada *',
                      hintText: 'Ex: 0/1/1 ou 1/1/1',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: onuIdCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'ONU ID (Opcional)',
                      hintText: 'Ex: 10',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: reasonCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Motivo Operacional',
                      hintText: 'field_maintenance / splitter_swap',
                    ),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Executar Reconciliação'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    if (serialCtrl.text.trim().isEmpty ||
        selectedOltId == null ||
        portCtrl.text.trim().isEmpty) {
      _showSnack('Preencha Serial, OLT e Porta PON.', isError: true);
      return;
    }

    try {
      final payload = <String, dynamic>{
        'serial': serialCtrl.text.trim(),
        'detected_olt_id': selectedOltId,
        'detected_port': portCtrl.text.trim(),
        'reason': reasonCtrl.text.trim(),
      };
      final parsedOnuId = int.tryParse(onuIdCtrl.text.trim());
      if (parsedOnuId != null) {
        payload['detected_onu_id'] = parsedOnuId;
      }
      final res = await context.read<AppState>().apiClient.reconcileFieldEvent(payload);
      if (!mounted) return;
      _showSnack('${res.actionTaken}: ${res.message}');
      await _loadScannerAndTimeline();
    } catch (e) {
      _showSnack('Falha na reconciliação: $e', isError: true);
    }
  }

  // ==================== WEBHOOKS ACTIONS ====================

  Future<void> _showCreateWebhookModal() async {
    final urlCtrl = TextEditingController();
    final secretCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final availableEvents = [
      '*',
      'onu.discovered',
      'onu.migrated',
      'onu.provisioned',
      'onu.deprovisioned',
      'olt.offline',
      'olt.online',
    ];
    final selectedEvents = <String>{'*'};

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: const Text(
            'Cadastrar Webhook ERP (HMAC-SHA256)',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 480,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: urlCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'URL de Destino (HTTPS/HTTP) *',
                      hintText: 'https://erp.provedor.com.br/webhooks/oltapi',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: secretCtrl,
                    obscureText: true,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Segredo HMAC-SHA256 (X-OLTAPI-Signature)',
                      hintText: 'Chave secreta para validação no ERP',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: descCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Descrição (Opcional)',
                      hintText: 'Ex: Integração IXC / SGP / Voalle',
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Eventos Assinados:',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: availableEvents.map((ev) {
                      final isSel = selectedEvents.contains(ev);
                      return FilterChip(
                        label: Text(ev, style: const TextStyle(fontSize: 12)),
                        selected: isSel,
                        onSelected: (val) {
                          setModalState(() {
                            if (val) {
                              selectedEvents.add(ev);
                            } else if (selectedEvents.length > 1) {
                              selectedEvents.remove(ev);
                            }
                          });
                        },
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Criar Webhook'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    if (urlCtrl.text.trim().isEmpty) {
      _showSnack('Informe a URL do Webhook.', isError: true);
      return;
    }

    try {
      await context.read<AppState>().apiClient.createWebhook({
        'url': urlCtrl.text.trim(),
        if (secretCtrl.text.trim().isNotEmpty) 'secret': secretCtrl.text.trim(),
        'events': selectedEvents.toList(),
        'is_active': true,
        if (descCtrl.text.trim().isNotEmpty) 'description': descCtrl.text.trim(),
      });
      if (!mounted) return;
      _showSnack('Webhook cadastrado com sucesso.');
      await _loadWebhooksData();
    } catch (e) {
      _showSnack('Erro ao cadastrar webhook: $e', isError: true);
    }
  }

  Future<void> _handlePingWebhook(WebhookSubscriptionModel sub) async {
    try {
      final log = await context.read<AppState>().apiClient.pingWebhook(sub.id);
      if (!mounted) return;
      _showSnack(
        log.success
            ? 'Ping entregue com sucesso (HTTP ${log.statusCode ?? 200}).'
            : 'Falha no Ping: ${log.errorMessage ?? "Status ${log.statusCode}"}',
        isError: !log.success,
      );
      await _loadWebhooksData();
    } catch (e) {
      _showSnack('Erro ao disparar ping: $e', isError: true);
    }
  }

  Future<void> _handleDeleteWebhook(WebhookSubscriptionModel sub) async {
    try {
      await context.read<AppState>().apiClient.deleteWebhook(sub.id);
      if (!mounted) return;
      _showSnack('Webhook removido.');
      await _loadWebhooksData();
    } catch (e) {
      _showSnack('Erro ao remover webhook: $e', isError: true);
    }
  }

  // ==================== TENANTS & NEUTRAL NETWORK ACTIONS ====================

  Future<void> _showCreateTenantModal() async {
    final nameCtrl = TextEditingController();
    String tenantType = 'NEUTRAL_OPERATOR';

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: const Text(
            'Novo Inquilino (Rede Neutra / Operador)',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameCtrl,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Nome do Inquilino (ISP) *',
                    hintText: 'Ex: FibraSul Telecom',
                  ),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: tenantType,
                  dropdownColor: AppColors.surface,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Classificação do Inquilino',
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: 'NEUTRAL_OPERATOR',
                      child: Text('NEUTRAL_OPERATOR (Locatário Rede Neutra)'),
                    ),
                    DropdownMenuItem(
                      value: 'PROVIDER_OWNER',
                      child: Text('PROVIDER_OWNER (Detentor da Infraestrutura)'),
                    ),
                  ],
                  onChanged: (v) {
                    if (v != null) setModalState(() => tenantType = v);
                  },
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
              child: const Text('Criar Inquilino'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    if (nameCtrl.text.trim().isEmpty) {
      _showSnack('Informe o nome do inquilino.', isError: true);
      return;
    }

    try {
      await context.read<AppState>().apiClient.createTenant({
        'name': nameCtrl.text.trim(),
        'type': tenantType,
        'is_active': true,
      });
      if (!mounted) return;
      _showSnack('Inquilino criado com sucesso.');
      await _loadTenantsData();
    } catch (e) {
      _showSnack('Erro ao criar inquilino: $e', isError: true);
    }
  }

  Future<void> _showAllocateVlanModal(TenantModel tenant) async {
    final olts = context.read<AppState>().olts;
    String? selectedOltId = olts.isNotEmpty ? olts.first.id : null;
    final vlanCtrl = TextEditingController();
    final descCtrl = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: Text(
            'Alocar VLAN • ${tenant.name}',
            style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 420,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                DropdownButtonFormField<String>(
                  initialValue: selectedOltId,
                  dropdownColor: AppColors.surface,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(labelText: 'OLT *'),
                  items: olts
                      .map(
                        (o) => DropdownMenuItem(
                          value: o.id,
                          child: Text('${o.name} (${o.host})'),
                        ),
                      )
                      .toList(),
                  onChanged: (v) => setModalState(() => selectedOltId = v),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: vlanCtrl,
                  keyboardType: TextInputType.number,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'VLAN ID (1-4094) *',
                    hintText: 'Ex: 210',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: descCtrl,
                  style: const TextStyle(color: AppColors.textPrimary),
                  decoration: const InputDecoration(
                    labelText: 'Descrição da Alocação',
                    hintText: 'Ex: Tráfego PPPoE Inquilino',
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
              child: const Text('Alocar VLAN'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    final vlanId = int.tryParse(vlanCtrl.text.trim());
    if (selectedOltId == null || vlanId == null || vlanId < 1 || vlanId > 4094) {
      _showSnack('Selecione uma OLT e informe uma VLAN válida (1-4094).', isError: true);
      return;
    }

    try {
      await context.read<AppState>().apiClient.allocateTenantVlan(tenant.id, {
        'olt_id': selectedOltId,
        'vlan_id': vlanId,
        if (descCtrl.text.trim().isNotEmpty) 'description': descCtrl.text.trim(),
      });
      if (!mounted) return;
      _showSnack('VLAN $vlanId alocada para ${tenant.name}.');
      await _loadTenantsData();
    } catch (e) {
      _showSnack('Erro ao alocar VLAN: $e', isError: true);
    }
  }

  Future<void> _handleRevokeVlan(
    TenantModel tenant,
    TenantVlanAllocationModel alloc,
  ) async {
    try {
      await context
          .read<AppState>()
          .apiClient
          .revokeTenantVlan(tenant.id, alloc.id);
      if (!mounted) return;
      _showSnack('Alocação VLAN ${alloc.vlanId} revogada.');
      await _loadTenantsData();
    } catch (e) {
      _showSnack('Erro ao revogar VLAN: $e', isError: true);
    }
  }

  // ==================== USERS & API KEYS ACTIONS ====================

  Future<void> _showCreateUserModal() async {
    final nameCtrl = TextEditingController();
    final emailCtrl = TextEditingController();
    final passCtrl = TextEditingController();
    String selectedRole = 'NOC';
    String? selectedTenantId = _tenants.isNotEmpty ? _tenants.first.id : null;
    final olts = context.read<AppState>().olts;
    final selectedOltIds = <String>{};

    final roles = [
      'SUPER_ADMIN',
      'NOC',
      'FIELD_TECH',
      'TENANT_ADMIN',
      'TENANT_TECH',
    ];

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: const Text(
            'Novo Usuário RBAC',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 460,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Nome Completo *'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: emailCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'E-mail *'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: passCtrl,
                    obscureText: true,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Senha Inicial (mín. 8 caracteres) *',
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: selectedRole,
                    dropdownColor: AppColors.surface,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(labelText: 'Papel (Role) *'),
                    items: roles
                        .map((r) => DropdownMenuItem(value: r, child: Text(r)))
                        .toList(),
                    onChanged: (v) {
                      if (v != null) setModalState(() => selectedRole = v);
                    },
                  ),
                  if (selectedRole.startsWith('TENANT_') && _tenants.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: selectedTenantId,
                      dropdownColor: AppColors.surface,
                      style: const TextStyle(color: AppColors.textPrimary),
                      decoration: const InputDecoration(
                        labelText: 'Inquilino Vinculado (Tenant)',
                      ),
                      items: _tenants
                          .map(
                            (t) => DropdownMenuItem(
                              value: t.id,
                              child: Text(t.name),
                            ),
                          )
                          .toList(),
                      onChanged: (v) => setModalState(() => selectedTenantId = v),
                    ),
                  ],
                  if (olts.isNotEmpty) ...[
                    const SizedBox(height: 16),
                    const Text(
                      'Escopo de OLTs Permitidas (vazio = todas):',
                      style: TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: olts.map((o) {
                        final isSel = selectedOltIds.contains(o.id);
                        return FilterChip(
                          label: Text(o.name, style: const TextStyle(fontSize: 12)),
                          selected: isSel,
                          onSelected: (val) {
                            setModalState(() {
                              if (val) {
                                selectedOltIds.add(o.id);
                              } else {
                                selectedOltIds.remove(o.id);
                              }
                            });
                          },
                        );
                      }).toList(),
                    ),
                  ],
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Criar Usuário'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    if (nameCtrl.text.trim().isEmpty ||
        emailCtrl.text.trim().isEmpty ||
        passCtrl.text.length < 8) {
      _showSnack(
        'Preencha nome, e-mail e senha com pelo menos 8 caracteres.',
        isError: true,
      );
      return;
    }

    try {
      await context.read<AppState>().apiClient.createUser({
        'name': nameCtrl.text.trim(),
        'email': emailCtrl.text.trim(),
        'password': passCtrl.text,
        'role': selectedRole,
        if (selectedRole.startsWith('TENANT_') && selectedTenantId != null)
          'tenant_id': selectedTenantId,
        'allowed_olt_ids': selectedOltIds.toList(),
      });
      if (!mounted) return;
      _showSnack('Usuário criado com sucesso.');
      await _loadRbacData();
    } catch (e) {
      _showSnack('Erro ao criar usuário: $e', isError: true);
    }
  }

  Future<void> _handleToggleUserActive(UserAccountModel user) async {
    try {
      await context.read<AppState>().apiClient.updateUser(user.id, {
        'is_active': !user.isActive,
      });
      if (!mounted) return;
      _showSnack(
        !user.isActive ? 'Usuário ativado.' : 'Usuário desativado.',
      );
      await _loadRbacData();
    } catch (e) {
      _showSnack('Erro ao atualizar usuário: $e', isError: true);
    }
  }

  Future<void> _handleDeleteUser(UserAccountModel user) async {
    try {
      await context.read<AppState>().apiClient.deleteUser(user.id);
      if (!mounted) return;
      _showSnack('Usuário removido.');
      await _loadRbacData();
    } catch (e) {
      _showSnack('Erro ao remover usuário: $e', isError: true);
    }
  }

  Future<void> _showCreateApiKeyModal() async {
    final nameCtrl = TextEditingController();
    final expiresCtrl = TextEditingController();
    final availableScopes = [
      '*',
      'olts:read',
      'olts:admin',
      'onus:read',
      'onus:discover',
      'onus:provision',
      'onus:deprovision',
      'onus:actions',
      'diagnostics:read',
      'backups:read',
      'backups:create',
      'vlans:read',
      'api_keys:manage',
    ];
    final selectedScopes = <String>{'*'};

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setModalState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: const Text(
            'Gerar Nova Chave de API (M2M / ERP)',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 16),
          ),
          content: SizedBox(
            width: 480,
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Identificação da Chave *',
                      hintText: 'Ex: Integração ERP IXC Produção',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: expiresCtrl,
                    keyboardType: TextInputType.number,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Expiração em Dias (Opcional)',
                      hintText: 'Ex: 365 (vazio = sem expiração)',
                    ),
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    'Escopos de Permissão:',
                    style: TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: availableScopes.map((sc) {
                      final isSel = selectedScopes.contains(sc);
                      return FilterChip(
                        label: Text(sc, style: const TextStyle(fontSize: 12)),
                        selected: isSel,
                        onSelected: (val) {
                          setModalState(() {
                            if (val) {
                              selectedScopes.add(sc);
                            } else if (selectedScopes.length > 1) {
                              selectedScopes.remove(sc);
                            }
                          });
                        },
                      );
                    }).toList(),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Gerar Chave'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || !mounted) return;
    if (nameCtrl.text.trim().isEmpty) {
      _showSnack('Informe o nome da chave de API.', isError: true);
      return;
    }

    try {
      final expDays = int.tryParse(expiresCtrl.text.trim());
      final created = await context.read<AppState>().apiClient.createApiKey({
        'name': nameCtrl.text.trim(),
        'scopes': selectedScopes.toList(),
        if (expDays != null && expDays > 0) 'expires_in_days': expDays,
      });
      if (!mounted) return;
      await _loadRbacData();
      if (!mounted) return;
      await _showCreatedKeyDialog(created);
    } catch (e) {
      _showSnack('Erro ao gerar API Key: $e', isError: true);
    }
  }

  Future<void> _showCreatedKeyDialog(ApiKeyCreatedModel created) async {
    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text(
          'Chave Gerada (Exibição Única)',
          style: TextStyle(color: AppColors.statusWarning, fontSize: 16),
        ),
        content: SizedBox(
          width: 480,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Copie e armazene esta chave em local seguro agora. Por segurança (hash SHA-256), ela nunca mais será exibida em texto limpo:',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
              ),
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppColors.codeBackground,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: AppColors.surfaceBorder),
                ),
                child: SelectableText(
                  created.key,
                  style: const TextStyle(
                    color: AppColors.accentCyan,
                    fontFamily: 'monospace',
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ),
        actions: [
          OutlinedButton.icon(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: created.key));
              _showSnack('Chave copiada para a área de transferência.');
            },
            icon: const Icon(Icons.copy, size: 16),
            label: const Text('Copiar Chave'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Entendi e Salvei'),
          ),
        ],
      ),
    );
  }

  Future<void> _handleRevokeApiKey(ApiKeyModel keyModel) async {
    try {
      await context.read<AppState>().apiClient.revokeApiKey(keyModel.id);
      if (!mounted) return;
      _showSnack('Chave ${keyModel.keyPrefix}... revogada.');
      await _loadRbacData();
    } catch (e) {
      _showSnack('Erro ao revogar chave: $e', isError: true);
    }
  }

  // ==================== UI BUILDERS ====================

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header + Sub-tabs
          Wrap(
            spacing: 16,
            runSpacing: 12,
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Governança, Automação & RBAC',
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Supervisão autônoma PON (Scanner), Timeline TR-101, Webhooks HMAC e controle multi-inquilino',
                    style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
                  ),
                ],
              ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _buildSubTabButton(
                    index: 0,
                    label: 'Scanner & Timeline TR-101',
                    icon: Icons.radar_outlined,
                  ),
                  _buildSubTabButton(
                    index: 1,
                    label: 'Webhooks ERP (HMAC)',
                    icon: Icons.webhook_outlined,
                  ),
                  _buildSubTabButton(
                    index: 2,
                    label: 'Inquilinos & Rede Neutra',
                    icon: Icons.domain_outlined,
                  ),
                  _buildSubTabButton(
                    index: 3,
                    label: 'Usuários & API Keys',
                    icon: Icons.shield_outlined,
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),

          Expanded(
            child: IndexedStack(
              index: _activeTab,
              children: [
                _buildScannerAndTimelineTab(),
                _buildWebhooksTab(),
                _buildTenantsTab(),
                _buildRbacTab(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSubTabButton({
    required int index,
    required String label,
    required IconData icon,
  }) {
    final isSelected = _activeTab == index;
    return InkWell(
      onTap: () {
        setState(() => _activeTab = index);
        _loadCurrentTab();
      },
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary : AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? AppColors.primaryLight : AppColors.surfaceBorder,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? Colors.white : AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected ? Colors.white : AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // -------------------- TAB 0: SCANNER & TIMELINE --------------------

  Widget _buildScannerAndTimelineTab() {
    final status = _scannerStatus;
    final isRunning = status?.isRunning ?? false;

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_scannerError != null)
            _buildErrorBanner(_scannerError!, _loadScannerAndTimeline),

          // Scanner Control Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.radar,
                          color: AppColors.accentCyan,
                          size: 20,
                        ),
                        const SizedBox(width: 10),
                        const Flexible(
                          child: Text(
                            'Worker de Supervisão Autônoma PON (Background Scanner)',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        const SizedBox(width: 10),
                        _buildBadge(
                          isRunning ? 'RODANDO' : 'PARADO',
                          isRunning ? AppColors.statusOnline : AppColors.statusOffline,
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: _loadingScanner
                              ? null
                              : () => _handleToggleScanner(!isRunning),
                          icon: Icon(
                            isRunning ? Icons.stop_circle_outlined : Icons.play_arrow,
                            size: 16,
                          ),
                          label: Text(
                            isRunning ? 'Parar Scanner' : 'Iniciar Scanner',
                          ),
                        ),
                        OutlinedButton.icon(
                          onPressed:
                              _loadingScanner ? null : _showUpdateIntervalDialog,
                          icon: const Icon(Icons.timer_outlined, size: 16),
                          label: Text(
                            'Intervalo (${status?.intervalSeconds ?? 60}s)',
                          ),
                        ),
                        ElevatedButton.icon(
                          onPressed: _loadingScanner ? null : _handleRunScannerNow,
                          icon: const Icon(Icons.bolt, size: 16),
                          label: const Text('Executar Ciclo Agora'),
                        ),
                        IconButton(
                          onPressed:
                              _loadingScanner ? null : _loadScannerAndTimeline,
                          icon: const Icon(Icons.refresh, size: 18),
                          tooltip: 'Atualizar Scanner e Timeline',
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    _buildMetricTile(
                      'Ciclos Executados',
                      '${status?.totalCycles ?? 0}',
                      Icons.repeat,
                    ),
                    _buildMetricTile(
                      'ONUs Detectadas',
                      '${status?.totalOnusDetected ?? 0}',
                      Icons.sensors,
                    ),
                    _buildMetricTile(
                      'Reconciliadas (TR-101)',
                      '${status?.totalOnusReconciled ?? 0}',
                      Icons.swap_horiz,
                    ),
                    _buildMetricTile(
                      'ONUs Virgens',
                      '${status?.totalVirginOnus ?? 0}',
                      Icons.fiber_new_outlined,
                    ),
                    _buildMetricTile(
                      'Falhas de Varredura',
                      '${status?.totalErrors ?? 0}',
                      Icons.warning_amber_outlined,
                    ),
                    _buildMetricTile(
                      'Último Ciclo',
                      status?.lastRunDurationMs != null
                          ? '${status!.lastRunDurationMs} ms'
                          : 'N/A',
                      Icons.speed,
                    ),
                  ],
                ),
                if (_lastScannerRun != null &&
                    _lastScannerRun!.oltResults.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  const Divider(color: AppColors.surfaceBorder),
                  const SizedBox(height: 8),
                  Text(
                    'Resultado do Último Ciclo Manual (#${_lastScannerRun!.cycleId} • ${_lastScannerRun!.durationMs}ms):',
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 10,
                    runSpacing: 8,
                    children: _lastScannerRun!.oltResults.map((r) {
                      return Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.inputBackground,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppColors.surfaceBorder),
                        ),
                        child: Text(
                          '${r.oltName}: ${r.detectedOnusCount} detectadas (${r.reconciledSerials.length} migradas, ${r.virginSerials.length} virgens)${r.errorMessage != null ? " • ERRO: ${r.errorMessage}" : ""}',
                          style: const TextStyle(
                            fontSize: 12,
                            color: AppColors.textPrimary,
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ],
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Timeline TR-101 Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.timeline,
                          color: AppColors.primaryLight,
                          size: 20,
                        ),
                        SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            'Timeline de Migrações & Eventos Ópticos (TR-101)',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        SizedBox(
                          width: 220,
                          child: TextField(
                            controller: _historySerialCtrl,
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.textPrimary,
                            ),
                            decoration: const InputDecoration(
                              isDense: true,
                              hintText: 'Filtrar por Serial ONU...',
                              prefixIcon: Icon(Icons.search, size: 16),
                            ),
                            onSubmitted: (_) => _loadScannerAndTimeline(),
                          ),
                        ),
                        OutlinedButton(
                          onPressed: _loadScannerAndTimeline,
                          child: const Text('Filtrar'),
                        ),
                        ElevatedButton.icon(
                          onPressed: _showReconcileFieldModal,
                          icon: const Icon(Icons.build_circle_outlined, size: 16),
                          label: const Text('Reconciliar Evento de Campo'),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (_loadingScanner && _migrationEvents.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_migrationEvents.isEmpty)
                  _buildEmptyBox(
                    'Nenhum evento de migração ou reconciliação TR-101 registrado até o momento.',
                  )
                else
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _migrationEvents.length,
                    separatorBuilder: (_, __) =>
                        const Divider(color: AppColors.surfaceBorder),
                    itemBuilder: (ctx, idx) {
                      final ev = _migrationEvents[idx];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          alignment: WrapAlignment.spaceBetween,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                _buildBadge(
                                  ev.reason,
                                  AppColors.accentCyan,
                                ),
                                const SizedBox(width: 10),
                                SelectableText(
                                  ev.serial,
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                              ],
                            ),
                            Text(
                              'Origem: ${ev.fromPort ?? "N/A"} (${ev.fromCircuitId ?? "-"})  →  Destino: ${ev.toPort} (${ev.toCircuitId})',
                              style: const TextStyle(
                                fontSize: 12,
                                color: AppColors.textSecondary,
                              ),
                            ),
                            Text(
                              ev.timestamp?.toIso8601String() ?? '',
                              style: const TextStyle(
                                fontSize: 11,
                                color: AppColors.textMuted,
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // -------------------- TAB 1: WEBHOOKS ERP --------------------

  Widget _buildWebhooksTab() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_webhooksError != null)
            _buildErrorBanner(_webhooksError!, _loadWebhooksData),

          // Subscriptions Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.webhook,
                          color: AppColors.accentCyan,
                          size: 20,
                        ),
                        SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            'Assinaturas de Webhooks Ativas (HMAC-SHA256)',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        ElevatedButton.icon(
                          onPressed: _showCreateWebhookModal,
                          icon: const Icon(Icons.add, size: 16),
                          label: const Text('Novo Webhook'),
                        ),
                        IconButton(
                          onPressed: _loadingWebhooks ? null : _loadWebhooksData,
                          icon: const Icon(Icons.refresh, size: 18),
                          tooltip: 'Atualizar Webhooks',
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (_loadingWebhooks && _webhooks.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_webhooks.isEmpty)
                  _buildEmptyBox(
                    'Nenhum Webhook configurado. Cadastre uma URL para notificar o ERP em tempo real.',
                  )
                else
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _webhooks.length,
                    separatorBuilder: (_, __) =>
                        const Divider(color: AppColors.surfaceBorder),
                    itemBuilder: (ctx, idx) {
                      final sub = _webhooks[idx];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          alignment: WrapAlignment.spaceBetween,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Wrap(
                                  spacing: 8,
                                  runSpacing: 4,
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  children: [
                                    _buildBadge(
                                      sub.isActive ? 'ATIVO' : 'INATIVO',
                                      sub.isActive
                                          ? AppColors.statusOnline
                                          : AppColors.statusOffline,
                                    ),
                                    if (sub.secret.isNotEmpty)
                                      _buildBadge(
                                        'HMAC-SHA256',
                                        AppColors.primaryLight,
                                      ),
                                    SelectableText(
                                      sub.url,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                        color: AppColors.textPrimary,
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Eventos: ${sub.events.join(", ")}${sub.description != null ? " • ${sub.description}" : ""}',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                            Wrap(
                              spacing: 8,
                              children: [
                                OutlinedButton.icon(
                                  onPressed: () => _handlePingWebhook(sub),
                                  icon: const Icon(Icons.send_outlined, size: 14),
                                  label: const Text('Testar Ping'),
                                ),
                                IconButton(
                                  onPressed: () => _handleDeleteWebhook(sub),
                                  icon: const Icon(
                                    Icons.delete_outline,
                                    color: AppColors.statusDanger,
                                    size: 18,
                                  ),
                                  tooltip: 'Remover Webhook',
                                ),
                              ],
                            ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // Delivery History Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Histórico de Entregas Recentes (Auditorias HTTP)',
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 12),
                if (_deliveries.isEmpty)
                  _buildEmptyBox('Nenhuma entrega de Webhook registrada ainda.')
                else
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _deliveries.length,
                    separatorBuilder: (_, __) =>
                        const Divider(color: AppColors.surfaceBorder),
                    itemBuilder: (ctx, idx) {
                      final d = _deliveries[idx];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        child: Wrap(
                          spacing: 12,
                          runSpacing: 6,
                          alignment: WrapAlignment.spaceBetween,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Wrap(
                              spacing: 8,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                _buildBadge(
                                  d.success
                                      ? 'HTTP ${d.statusCode ?? 200}'
                                      : 'FALHA ${d.statusCode ?? ""}',
                                  d.success
                                      ? AppColors.statusOnline
                                      : AppColors.statusDanger,
                                ),
                                Text(
                                  d.event,
                                  style: const TextStyle(
                                    fontFamily: 'monospace',
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                                Text(
                                  d.url,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                            Text(
                              'Latência: ${d.durationMs}ms${d.errorMessage != null ? " • ${d.errorMessage}" : ""} • ${d.timestamp?.toIso8601String() ?? ""}',
                              style: const TextStyle(
                                fontSize: 11,
                                color: AppColors.textMuted,
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // -------------------- TAB 2: TENANTS & NEUTRAL NETWORK --------------------

  Widget _buildTenantsTab() {
    final olts = context.watch<AppState>().olts;
    final oltMap = <String, OltModel>{for (final o in olts) o.id: o};

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_tenantsError != null)
            _buildErrorBanner(_tenantsError!, _loadTenantsData),

          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.domain,
                          color: AppColors.accentCyan,
                          size: 20,
                        ),
                        SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            'Inquilinos (Tenants) & Alocação de VLANs em Rede Neutra',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        ElevatedButton.icon(
                          onPressed: _showCreateTenantModal,
                          icon: const Icon(Icons.add_business_outlined, size: 16),
                          label: const Text('Novo Inquilino'),
                        ),
                        IconButton(
                          onPressed: _loadingTenants ? null : _loadTenantsData,
                          icon: const Icon(Icons.refresh, size: 18),
                          tooltip: 'Atualizar Inquilinos',
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (_loadingTenants && _tenants.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_tenants.isEmpty)
                  _buildEmptyBox(
                    'Nenhum inquilino cadastrado. Crie operadores de Rede Neutra e aloque suas respectivas VLANs por OLT.',
                  )
                else
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _tenants.length,
                    separatorBuilder: (_, __) =>
                        const Divider(color: AppColors.surfaceBorder),
                    itemBuilder: (ctx, idx) {
                      final t = _tenants[idx];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Wrap(
                              spacing: 12,
                              runSpacing: 8,
                              alignment: WrapAlignment.spaceBetween,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                Wrap(
                                  spacing: 8,
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  children: [
                                    Text(
                                      t.name,
                                      style: const TextStyle(
                                        fontSize: 15,
                                        fontWeight: FontWeight.bold,
                                        color: AppColors.textPrimary,
                                      ),
                                    ),
                                    _buildBadge(
                                      t.type,
                                      t.type == 'PROVIDER_OWNER'
                                          ? AppColors.primaryLight
                                          : AppColors.accentCyan,
                                    ),
                                    _buildBadge(
                                      t.isActive ? 'ATIVO' : 'INATIVO',
                                      t.isActive
                                          ? AppColors.statusOnline
                                          : AppColors.statusOffline,
                                    ),
                                  ],
                                ),
                                OutlinedButton.icon(
                                  onPressed: () => _showAllocateVlanModal(t),
                                  icon: const Icon(Icons.lan_outlined, size: 15),
                                  label: const Text('Alocar VLAN na OLT'),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            if (t.vlans.isEmpty)
                              const Text(
                                'Nenhuma VLAN exclusiva alocada a este inquilino.',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: AppColors.textMuted,
                                ),
                              )
                            else
                              Wrap(
                                spacing: 8,
                                runSpacing: 8,
                                children: t.vlans.map((alloc) {
                                  final oltName =
                                      oltMap[alloc.oltId]?.name ?? alloc.oltId;
                                  return Chip(
                                    backgroundColor: AppColors.inputBackground,
                                    label: Text(
                                      'VLAN ${alloc.vlanId} • $oltName${alloc.description != null ? " (${alloc.description})" : ""}',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: AppColors.textPrimary,
                                      ),
                                    ),
                                    deleteIcon: const Icon(
                                      Icons.close,
                                      size: 15,
                                      color: AppColors.statusDanger,
                                    ),
                                    onDeleted: () => _handleRevokeVlan(t, alloc),
                                  );
                                }).toList(),
                              ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // -------------------- TAB 3: RBAC USERS & API KEYS --------------------

  Widget _buildRbacTab() {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_rbacError != null) _buildErrorBanner(_rbacError!, _loadRbacData),

          // Users RBAC Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.people_outline,
                          color: AppColors.accentCyan,
                          size: 20,
                        ),
                        SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            'Contas de Operadores & Controle RBAC',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        ElevatedButton.icon(
                          onPressed: _showCreateUserModal,
                          icon: const Icon(Icons.person_add_outlined, size: 16),
                          label: const Text('Novo Usuário'),
                        ),
                        IconButton(
                          onPressed: _loadingRbac ? null : _loadRbacData,
                          icon: const Icon(Icons.refresh, size: 18),
                          tooltip: 'Atualizar Usuários e Chaves',
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (_loadingRbac && _users.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (_users.isEmpty)
                  _buildEmptyBox('Nenhum usuário RBAC retornado pela API.')
                else
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _users.length,
                    separatorBuilder: (_, __) =>
                        const Divider(color: AppColors.surfaceBorder),
                    itemBuilder: (ctx, idx) {
                      final u = _users[idx];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          alignment: WrapAlignment.spaceBetween,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Wrap(
                              spacing: 10,
                              runSpacing: 6,
                              crossAxisAlignment: WrapCrossAlignment.center,
                              children: [
                                _buildBadge(u.role, AppColors.primaryLight),
                                _buildBadge(
                                  u.isActive ? 'ATIVO' : 'INATIVO',
                                  u.isActive
                                      ? AppColors.statusOnline
                                      : AppColors.statusDanger,
                                ),
                                Text(
                                  u.name,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.bold,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                                Text(
                                  u.email,
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textSecondary,
                                  ),
                                ),
                                Text(
                                  u.allowedOltIds.isEmpty
                                      ? '• Escopo: Todas as OLTs'
                                      : '• Escopo: ${u.allowedOltIds.length} OLT(s)',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textMuted,
                                  ),
                                ),
                              ],
                            ),
                            Wrap(
                              spacing: 8,
                              children: [
                                OutlinedButton(
                                  onPressed: () => _handleToggleUserActive(u),
                                  child: Text(
                                    u.isActive ? 'Desativar' : 'Ativar',
                                  ),
                                ),
                                IconButton(
                                  onPressed: () => _handleDeleteUser(u),
                                  icon: const Icon(
                                    Icons.delete_outline,
                                    color: AppColors.statusDanger,
                                    size: 18,
                                  ),
                                  tooltip: 'Excluir Usuário',
                                ),
                              ],
                            ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          // API Keys Card
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.surfaceBorder),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 10,
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.vpn_key_outlined,
                          color: AppColors.statusWarning,
                          size: 20,
                        ),
                        SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            'Chaves de API M2M (X-API-Key / SHA-256)',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              color: AppColors.textPrimary,
                            ),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                    ElevatedButton.icon(
                      onPressed: _showCreateApiKeyModal,
                      icon: const Icon(Icons.add_moderator_outlined, size: 16),
                      label: const Text('Nova API Key'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                if (_apiKeys.isEmpty)
                  _buildEmptyBox(
                    'Nenhuma chave de API ativa. Gere chaves com escopos granulares para integrações de ERP.',
                  )
                else
                  ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _apiKeys.length,
                    separatorBuilder: (_, __) =>
                        const Divider(color: AppColors.surfaceBorder),
                    itemBuilder: (ctx, idx) {
                      final k = _apiKeys[idx];
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        child: Wrap(
                          spacing: 12,
                          runSpacing: 8,
                          alignment: WrapAlignment.spaceBetween,
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Wrap(
                                  spacing: 8,
                                  crossAxisAlignment: WrapCrossAlignment.center,
                                  children: [
                                    Text(
                                      k.name,
                                      style: const TextStyle(
                                        fontWeight: FontWeight.bold,
                                        color: AppColors.textPrimary,
                                      ),
                                    ),
                                    _buildBadge(
                                      '${k.keyPrefix}***',
                                      AppColors.accentCyan,
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Escopos: ${k.scopes.join(", ")}${k.expiresAt != null ? " • Expira: ${k.expiresAt}" : ""}',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: AppColors.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                            OutlinedButton.icon(
                              onPressed: () => _handleRevokeApiKey(k),
                              icon: const Icon(
                                Icons.block,
                                size: 15,
                                color: AppColors.statusDanger,
                              ),
                              label: const Text(
                                'Revogar',
                                style: TextStyle(color: AppColors.statusDanger),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // -------------------- SHARED WIDGET HELPERS --------------------

  Widget _buildMetricTile(String label, String value, IconData icon) {
    return Container(
      width: 190,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.inputBackground,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18, color: AppColors.primaryLight),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  value,
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textSecondary,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: color,
        ),
      ),
    );
  }

  Widget _buildEmptyBox(String text) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.inputBackground,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.surfaceBorder),
      ),
      child: Text(
        text,
        textAlign: TextAlign.center,
        style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
      ),
    );
  }

  Widget _buildErrorBanner(String error, VoidCallback onRetry) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: AppColors.statusDanger.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppColors.statusDanger.withValues(alpha: 0.4)),
      ),
      child: Wrap(
        spacing: 12,
        runSpacing: 8,
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(
            error,
            style: const TextStyle(color: AppColors.statusDanger, fontSize: 12),
          ),
          TextButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh, size: 14),
            label: const Text('Tentar Novamente'),
          ),
        ],
      ),
    );
  }
}
