import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/app_state.dart';
import '../../providers/settings_provider.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _urlController;
  late TextEditingController _apiKeyController;
  bool _isSaving = false;

  @override
  void initState() {
    super.initState();
    final settings = context.read<SettingsProvider>();
    _urlController = TextEditingController(text: settings.baseUrl);
    _apiKeyController = TextEditingController(text: settings.apiKey);
  }

  @override
  void dispose() {
    _urlController.dispose();
    _apiKeyController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => _isSaving = true);
    final settings = context.read<SettingsProvider>();
    final appState = context.read<AppState>();

    await settings.updateSettings(
      baseUrl: _urlController.text.trim(),
      apiKey: _apiKeyController.text.trim(),
    );

    if (!mounted) return;
    setState(() => _isSaving = false);

    if (settings.isConnected) {
      await appState.refreshAll();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusOnline,
          content: Text(
            'Conexão estabelecida com sucesso! (${settings.latencyMs} ms)',
          ),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          backgroundColor: AppColors.statusDanger,
          content: Text(
            'Não foi possível conectar ao backend: ${settings.lastError ?? "Erro desconhecido"}',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsProvider>();

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          const Text(
            'Configurações de Conexão',
            style: TextStyle(
              fontSize: 22,
              fontWeight: FontWeight.bold,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'Defina o endpoint REST do OLTAPI e as credenciais de autenticação',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
          ),
          const SizedBox(height: 24),

          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 650),
            child: Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: AppColors.surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: AppColors.surfaceBorder),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Status Atual do Backend
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: settings.isConnected
                          ? AppColors.statusOnline.withValues(alpha: 0.1)
                          : AppColors.statusDanger.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: settings.isConnected
                            ? AppColors.statusOnline.withValues(alpha: 0.3)
                            : AppColors.statusDanger.withValues(alpha: 0.3),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          settings.isConnected ? Icons.check_circle : Icons.error_outline,
                          color: settings.isConnected ? AppColors.statusOnline : AppColors.statusDanger,
                          size: 20,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                settings.isConnected
                                    ? 'Conectado ao Backend (${settings.latencyMs} ms)'
                                    : 'Desconectado / Inacessível',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: settings.isConnected
                                      ? AppColors.statusOnline
                                      : AppColors.statusDanger,
                                  fontSize: 14,
                                ),
                              ),
                              if (settings.lastError != null)
                                Text(
                                  settings.lastError!,
                                  style: const TextStyle(
                                    color: AppColors.textSecondary,
                                    fontSize: 12,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Campos
                  const Text(
                    'URL Base do OLTAPI',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _urlController,
                    decoration: const InputDecoration(
                      hintText: 'http://localhost:8000',
                      prefixIcon: Icon(Icons.link, size: 20, color: AppColors.textSecondary),
                    ),
                  ),
                  const SizedBox(height: 16),

                  const Text(
                    'Chave de Autenticação (X-API-Key)',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: _apiKeyController,
                    obscureText: true,
                    decoration: const InputDecoration(
                      hintText: 'oltapi_secret_default_key_change_me',
                      prefixIcon: Icon(Icons.vpn_key_outlined, size: 20, color: AppColors.textSecondary),
                    ),
                  ),
                  const SizedBox(height: 24),

                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      ElevatedButton.icon(
                        onPressed: _isSaving ? null : _save,
                        icon: _isSaving
                            ? const SizedBox(
                                width: 14,
                                height: 14,
                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                              )
                            : const Icon(Icons.save, size: 16),
                        label: const Text('Testar e Salvar Configurações'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
