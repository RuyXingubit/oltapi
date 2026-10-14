import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/backup_model.dart';
import '../../providers/app_state.dart';
import '../olts/olt_backups_dialog.dart';

class BackupsScreen extends StatefulWidget {
  const BackupsScreen({super.key});

  @override
  State<BackupsScreen> createState() => _BackupsScreenState();
}

class _BackupsScreenState extends State<BackupsScreen> {
  int _selectedSubTab = 0; // 0: Snapshots & Auditoria por OLT, 1: Servidores FTP Remotos

  bool _isLoadingAudits = false;
  bool _isRunningBatchBackup = false;
  Map<String, BackupAuditReportModel> _auditMap = {};

  bool _isLoadingFtp = false;
  List<FtpServerModel> _ftpServers = [];
  String? _testingFtpId;

  @override
  void initState() {
    super.initState();
    final backupParam = Uri.base.queryParameters['backup'];
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadInitialData();
      if (backupParam != null) {
        _checkAndOpenBackupModal(backupParam);
      }
    });
  }

  Future<void> _loadInitialData() async {
    await Future.wait([
      _loadAuditReports(),
      _loadFtpServers(),
    ]);
  }

  Future<void> _loadAuditReports() async {
    if (!mounted) return;
    setState(() => _isLoadingAudits = true);
    try {
      final api = context.read<AppState>().apiClient;
      final reports = await api.auditAllBackups();
      if (mounted) {
        setState(() {
          _auditMap = {for (final r in reports) r.oltId: r};
          _isLoadingAudits = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isLoadingAudits = false);
      }
    }
  }

  Future<void> _loadFtpServers() async {
    if (!mounted) return;
    setState(() => _isLoadingFtp = true);
    try {
      final api = context.read<AppState>().apiClient;
      final servers = await api.getFtpServers();
      if (mounted) {
        setState(() {
          _ftpServers = servers;
          _isLoadingFtp = false;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _isLoadingFtp = false);
      }
    }
  }

  Future<void> _checkAndOpenBackupModal(String oltId) async {
    final appState = context.read<AppState>();
    final targetOlt = appState.olts.where((o) => o.id == oltId).firstOrNull;
    if (targetOlt != null) {
      await showDialog(
        context: context,
        builder: (context) => OltBackupsDialog(olt: targetOlt),
      );
      _loadAuditReports();
    }
  }

  Future<void> _runAllBackups() async {
    setState(() => _isRunningBatchBackup = true);
    try {
      final api = context.read<AppState>().apiClient;
      final result = await api.runAllBackups(purgeAfter: true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Backup em lote concluído: ${result.successful}/${result.totalOlts} OLTs com sucesso (${result.failed} falhas).',
            ),
            backgroundColor:
                result.failed == 0 ? AppColors.statusOnline : AppColors.statusWarning,
          ),
        );
        _loadAuditReports();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erro no backup em lote: $e'), backgroundColor: AppColors.statusDanger),
        );
      }
    } finally {
      if (mounted) setState(() => _isRunningBatchBackup = false);
    }
  }

  Future<void> _showGlobalPurgeDialog() async {
    final maxBackupsCtrl = TextEditingController(text: '30');
    final maxAgeCtrl = TextEditingController(text: '90');

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppColors.surface,
        title: const Text(
          'Política de Retenção & Expurgo Global',
          style: TextStyle(color: AppColors.textPrimary),
        ),
        content: SizedBox(
          width: 420,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Aplica a política de retenção em todas as OLTs do parque, removendo arquivos excedentes ou antigos.',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: maxBackupsCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: const InputDecoration(
                  labelText: 'Máximo de snapshots mantidos por OLT',
                  hintText: 'Ex: 30',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: maxAgeCtrl,
                keyboardType: TextInputType.number,
                style: const TextStyle(color: AppColors.textPrimary),
                decoration: const InputDecoration(
                  labelText: 'Idade máxima em dias (opcional)',
                  hintText: 'Ex: 90',
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
          ElevatedButton.icon(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.statusDanger),
            icon: const Icon(Icons.cleaning_services, size: 16),
            label: const Text('Executar Expurgo Global'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;
    final maxBackups = int.tryParse(maxBackupsCtrl.text.trim()) ?? 30;
    final maxAge = int.tryParse(maxAgeCtrl.text.trim());

    try {
      final api = context.read<AppState>().apiClient;
      final res = await api.purgeAllBackups(
        maxBackupsPerOlt: maxBackups,
        maxAgeDays: maxAge,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Expurgo global concluído: ${res.deletedCount} snapshots removidos (${res.formattedFreedBytes}).'),
            backgroundColor: AppColors.statusOnline,
          ),
        );
        _loadAuditReports();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Falha no expurgo global: $e'), backgroundColor: AppColors.statusDanger),
        );
      }
    }
  }

  Future<void> _showFtpServerDialog({FtpServerModel? existing}) async {
    final nameCtrl = TextEditingController(text: existing?.name ?? '');
    final hostCtrl = TextEditingController(text: existing?.host ?? '');
    final portCtrl = TextEditingController(text: (existing?.port ?? 21).toString());
    final userCtrl = TextEditingController(text: existing?.username ?? '');
    final passCtrl = TextEditingController();
    final pathCtrl = TextEditingController(text: existing?.basePath ?? '/');
    bool isGlobalDefault = existing?.isGlobalDefault ?? false;
    bool isActive = existing?.isActive ?? true;

    final saved = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: Text(
            existing == null ? 'Novo Servidor FTP Remoto' : 'Editar Servidor FTP',
            style: const TextStyle(color: AppColors.textPrimary),
          ),
          content: SizedBox(
            width: 480,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  TextField(
                    controller: nameCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Nome do Servidor FTP',
                      hintText: 'Ex: FTP Datacenter Primário',
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        flex: 3,
                        child: TextField(
                          controller: hostCtrl,
                          style: const TextStyle(color: AppColors.textPrimary),
                          decoration: const InputDecoration(
                            labelText: 'Host / IP',
                            hintText: 'Ex: 10.50.50.10',
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 1,
                        child: TextField(
                          controller: portCtrl,
                          keyboardType: TextInputType.number,
                          style: const TextStyle(color: AppColors.textPrimary),
                          decoration: const InputDecoration(
                            labelText: 'Porta',
                            hintText: '21',
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: userCtrl,
                          style: const TextStyle(color: AppColors.textPrimary),
                          decoration: const InputDecoration(
                            labelText: 'Usuário FTP',
                          ),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: TextField(
                          controller: passCtrl,
                          obscureText: true,
                          style: const TextStyle(color: AppColors.textPrimary),
                          decoration: InputDecoration(
                            labelText: existing == null ? 'Senha FTP' : 'Nova Senha (opcional)',
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: pathCtrl,
                    style: const TextStyle(color: AppColors.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Diretório Base (Base Path)',
                      hintText: '/olt-backups',
                    ),
                  ),
                  const SizedBox(height: 12),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text(
                      'Destino Global Padrão (Global Default)',
                      style: TextStyle(color: AppColors.textPrimary, fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                    subtitle: const Text(
                      'Usado automaticamente por OLTs sem vínculo FTP específico.',
                      style: TextStyle(color: AppColors.textSecondary, fontSize: 11),
                    ),
                    value: isGlobalDefault,
                    onChanged: (val) => setDialogState(() => isGlobalDefault = val),
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text(
                      'Servidor Ativo',
                      style: TextStyle(color: AppColors.textPrimary, fontSize: 13, fontWeight: FontWeight.w600),
                    ),
                    value: isActive,
                    onChanged: (val) => setDialogState(() => isActive = val),
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
            ElevatedButton.icon(
              onPressed: () => Navigator.pop(ctx, true),
              icon: const Icon(Icons.save, size: 16),
              label: const Text('Salvar FTP'),
            ),
          ],
        ),
      ),
    );

    if (saved != true || !mounted) return;
    final name = nameCtrl.text.trim();
    final host = hostCtrl.text.trim();
    final port = int.tryParse(portCtrl.text.trim()) ?? 21;
    final username = userCtrl.text.trim();
    final password = passCtrl.text;
    final basePath = pathCtrl.text.trim().isEmpty ? '/' : pathCtrl.text.trim();

    if (name.isEmpty || host.isEmpty || username.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Preencha Nome, Host e Usuário do servidor FTP.'),
          backgroundColor: AppColors.statusWarning,
        ),
      );
      return;
    }

    try {
      final api = context.read<AppState>().apiClient;
      if (existing == null) {
        await api.createFtpServer({
          'name': name,
          'host': host,
          'port': port,
          'username': username,
          'password': password,
          'base_path': basePath,
          'is_global_default': isGlobalDefault,
          'is_active': isActive,
        });
      } else {
        final payload = <String, dynamic>{
          'name': name,
          'host': host,
          'port': port,
          'username': username,
          'base_path': basePath,
          'is_global_default': isGlobalDefault,
          'is_active': isActive,
        };
        if (password.isNotEmpty) {
          payload['password'] = password;
        }
        await api.updateFtpServer(existing.id, payload);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Servidor FTP salvo com sucesso.'),
            backgroundColor: AppColors.statusOnline,
          ),
        );
        _loadFtpServers();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Falha ao salvar FTP: $e'), backgroundColor: AppColors.statusDanger),
        );
      }
    }
  }

  Future<void> _testFtpServer(FtpServerModel server) async {
    setState(() => _testingFtpId = server.id);
    try {
      final api = context.read<AppState>().apiClient;
      final res = await api.testFtpServer(server.id);
      if (!mounted) return;
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          backgroundColor: AppColors.surface,
          title: Row(
            children: [
              Icon(
                res.success ? Icons.check_circle : Icons.error,
                color: res.success ? AppColors.statusOnline : AppColors.statusDanger,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  'Diagnóstico FTP — ${server.name}',
                  style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          content: SizedBox(
            width: 440,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  res.message,
                  style: TextStyle(
                    color: res.success ? AppColors.statusOnline : AppColors.statusDanger,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                if (res.latencyMs != null)
                  Text(
                    'Latência: ${res.latencyMs!.toStringAsFixed(1)} ms',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                if (res.workingDirectory != null)
                  Text(
                    'Diretório (PWD): ${res.workingDirectory}',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 13, fontFamily: 'monospace'),
                  ),
                if (res.banner != null && res.banner!.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.background,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: AppColors.surfaceBorder),
                    ),
                    child: Text(
                      res.banner!,
                      style: const TextStyle(color: AppColors.textPrimary, fontSize: 12, fontFamily: 'monospace'),
                    ),
                  ),
                ],
              ],
            ),
          ),
          actions: [
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Fechar'),
            ),
          ],
        ),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erro ao testar FTP: $e'), backgroundColor: AppColors.statusDanger),
        );
      }
    } finally {
      if (mounted) setState(() => _testingFtpId = null);
    }
  }

  Future<void> _deleteFtpServer(FtpServerModel server) async {
    try {
      final api = context.read<AppState>().apiClient;
      await api.deleteFtpServer(server.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Servidor FTP "${server.name}" removido.')),
        );
        _loadFtpServers();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Erro ao remover FTP: $e'), backgroundColor: AppColors.statusDanger),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();
    final olts = appState.olts;
    final isLoadingOlts = appState.isLoadingOlts;

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
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
                    'Disaster Recovery, Backups & Servidores FTP',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 4),
                  Text(
                    'Snapshots imutáveis com hash SHA-256, detecção de drift, comparação visual Unified Diff e destinos Multi-FTP.',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                  ),
                ],
              ),
              Wrap(
                spacing: 10,
                runSpacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: _isLoadingAudits ? null : _loadAuditReports,
                    icon: const Icon(Icons.verified_user_outlined, size: 16),
                    label: const Text('Auditar Parque (SHA-256)'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _showGlobalPurgeDialog,
                    icon: const Icon(Icons.cleaning_services_outlined, size: 16),
                    label: const Text('Expurgo Global'),
                  ),
                  ElevatedButton.icon(
                    onPressed: _isRunningBatchBackup ? null : _runAllBackups,
                    icon: _isRunningBatchBackup
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.backup, size: 16),
                    label: Text(_isRunningBatchBackup ? 'Executando...' : 'Backup em Lote (Run All)'),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 20),

          // Sub-tabs Navigation
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              _buildSubTabButton(
                index: 0,
                icon: Icons.history_edu,
                label: 'Snapshots, Drift & Auditoria por OLT',
              ),
              _buildSubTabButton(
                index: 1,
                icon: Icons.cloud_upload_outlined,
                label: 'Servidores FTP Remotos (${_ftpServers.length})',
              ),
            ],
          ),
          const SizedBox(height: 20),

          Expanded(
            child: _selectedSubTab == 0
                ? _buildOltsBackupGrid(olts, isLoadingOlts)
                : _buildFtpServersView(),
          ),
        ],
      ),
    );
  }

  Widget _buildSubTabButton({
    required int index,
    required IconData icon,
    required String label,
  }) {
    final isSelected = _selectedSubTab == index;
    return InkWell(
      onTap: () => setState(() => _selectedSubTab = index),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.primary.withValues(alpha: 0.15) : AppColors.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: isSelected ? AppColors.primary : AppColors.surfaceBorder,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? AppColors.primary : AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? AppColors.textPrimary : AppColors.textSecondary,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOltsBackupGrid(List olts, bool isLoading) {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (olts.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.only(top: 60),
          child: Text(
            'Nenhuma OLT cadastrada. Vá em "Gerenciar OLTs" para adicionar equipamentos.',
            style: TextStyle(color: AppColors.textSecondary),
          ),
        ),
      );
    }

    return GridView.builder(
      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
        maxCrossAxisExtent: 440,
        mainAxisExtent: 225,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
      ),
      itemCount: olts.length,
      itemBuilder: (context, index) {
        final olt = olts[index];
        final audit = _auditMap[olt.id];

        return Card(
          color: AppColors.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: const BorderSide(color: AppColors.surfaceBorder),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        olt.name,
                        style: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.bold,
                          color: AppColors.textPrimary,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (audit != null)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: (audit.hasChanged
                                  ? AppColors.statusWarning
                                  : AppColors.statusOnline)
                              .withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Text(
                          audit.hasChanged ? 'DRIFT DETECTADO' : 'ÍNTEGRO',
                          style: TextStyle(
                            color: audit.hasChanged
                                ? AppColors.statusWarning
                                : AppColors.statusOnline,
                            fontSize: 10,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  '${olt.vendor.toUpperCase()} ${olt.model} • ${olt.host}:${olt.port} (${olt.protocol.toUpperCase()})',
                  style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 10),
                if (audit != null) ...[
                  Wrap(
                    spacing: 12,
                    runSpacing: 4,
                    children: [
                      Text(
                        'Snapshots: ${audit.totalBackups}',
                        style: const TextStyle(color: AppColors.textPrimary, fontSize: 12, fontWeight: FontWeight.w600),
                      ),
                      Text(
                        'Volume: ${audit.formattedTotalBytes}',
                        style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                      ),
                      if (audit.lastBackupAt != null)
                        Text(
                          'Último: ${DateFormat('dd/MM HH:mm').format(audit.lastBackupAt!.toLocal())}',
                          style: const TextStyle(color: AppColors.textSecondary, fontSize: 12),
                        ),
                    ],
                  ),
                ] else
                  const Text(
                    'Clique em Backups para inspecionar snapshots e diff.',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
                    overflow: TextOverflow.ellipsis,
                  ),
                const Spacer(),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    ElevatedButton.icon(
                      onPressed: () => _checkAndOpenBackupModal(olt.id),
                      icon: const Icon(Icons.save, size: 16),
                      label: const Text('Backups, Diff & FTP'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildFtpServersView() {
    if (_isLoadingFtp) {
      return const Center(child: CircularProgressIndicator());
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Expanded(
              child: Text(
                'Repositórios FTP Remotos para Disaster Recovery',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            ElevatedButton.icon(
              onPressed: () => _showFtpServerDialog(),
              icon: const Icon(Icons.add, size: 16),
              label: const Text('Novo Servidor FTP'),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (_ftpServers.isEmpty)
          Expanded(
            child: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.cloud_off, size: 48, color: AppColors.textMuted),
                  const SizedBox(height: 12),
                  const Text(
                    'Nenhum servidor FTP remoto cadastrado.',
                    style: TextStyle(color: AppColors.textSecondary, fontSize: 15),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Adicione servidores FTP para envio nativo do running-config com fallback automático.',
                    style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                  ),
                ],
              ),
            ),
          )
        else
          Expanded(
            child: ListView.separated(
              itemCount: _ftpServers.length,
              separatorBuilder: (context, index) => const SizedBox(height: 10),
              itemBuilder: (context, index) {
                final ftp = _ftpServers[index];
                final isTesting = _testingFtpId == ftp.id;

                return Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppColors.surface,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.surfaceBorder),
                  ),
                  child: Wrap(
                    spacing: 16,
                    runSpacing: 12,
                    alignment: WrapAlignment.spaceBetween,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Wrap(
                            spacing: 8,
                            runSpacing: 6,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Text(
                                ftp.name,
                                style: const TextStyle(
                                  color: AppColors.textPrimary,
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              if (ftp.isGlobalDefault)
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: AppColors.primary.withValues(alpha: 0.15),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: const Text(
                                    'GLOBAL DEFAULT',
                                    style: TextStyle(
                                      color: AppColors.primary,
                                      fontSize: 10,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: (ftp.isActive ? AppColors.statusOnline : AppColors.textMuted)
                                      .withValues(alpha: 0.15),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: Text(
                                  ftp.isActive ? 'ATIVO' : 'INATIVO',
                                  style: TextStyle(
                                    color: ftp.isActive ? AppColors.statusOnline : AppColors.textMuted,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 6),
                          Text(
                            'ftp://${ftp.username}@${ftp.host}:${ftp.port}${ftp.basePath}',
                            style: const TextStyle(
                              color: AppColors.textSecondary,
                              fontSize: 13,
                              fontFamily: 'monospace',
                            ),
                          ),
                        ],
                      ),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          OutlinedButton.icon(
                            onPressed: isTesting ? null : () => _testFtpServer(ftp),
                            icon: isTesting
                                ? const SizedBox(
                                    width: 14,
                                    height: 14,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.network_check, size: 16),
                            label: const Text('Testar FTP'),
                          ),
                          OutlinedButton.icon(
                            onPressed: () => _showFtpServerDialog(existing: ftp),
                            icon: const Icon(Icons.edit_outlined, size: 16),
                            label: const Text('Editar'),
                          ),
                          IconButton(
                            onPressed: () => _deleteFtpServer(ftp),
                            icon: const Icon(Icons.delete_outline, color: AppColors.statusDanger),
                            tooltip: 'Remover FTP',
                          ),
                        ],
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
      ],
    );
  }
}
