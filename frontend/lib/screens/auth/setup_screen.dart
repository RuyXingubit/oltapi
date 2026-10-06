import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../providers/auth_provider.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  final _apiKeyController = TextEditingController(text: 'oltapi_secret_default_key_change_me');
  final _providerNameController = TextEditingController(text: 'Provedor Matriz');
  final _adminNameController = TextEditingController(text: 'Administrador');
  final _adminEmailController = TextEditingController();
  final _adminPasswordController = TextEditingController();
  
  bool _isLoading = false;
  String? _error;
  String? _success;

  Future<void> _handleSetup() async {
    final apiKey = _apiKeyController.text.trim();
    final providerName = _providerNameController.text.trim();
    final adminName = _adminNameController.text.trim();
    final adminEmail = _adminEmailController.text.trim();
    final adminPassword = _adminPasswordController.text.trim();

    if (apiKey.isEmpty || providerName.isEmpty || adminName.isEmpty || adminEmail.isEmpty || adminPassword.isEmpty) {
      setState(() => _error = 'Preencha todos os campos');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
      _success = null;
    });

    try {
      final auth = context.read<AuthProvider>();
      final req = {
        'provider_name': providerName,
        'admin_name': adminName,
        'admin_email': adminEmail,
        'admin_password': adminPassword,
      };
      
      await auth.apiClient.initSetup(req, apiKey);
      
      setState(() {
        _success = 'Setup concluído! Fazendo login...';
      });
      
      // Auto login after setup
      await Future.delayed(const Duration(seconds: 1));
      await auth.login(adminEmail, adminPassword);
      
    } catch (e) {
      setState(() {
        _error = 'Erro no setup. Verifique a Master API Key. ($e)';
      });
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: SingleChildScrollView(
          child: Container(
            width: 450,
            padding: const EdgeInsets.all(32),
            decoration: BoxDecoration(
              color: AppColors.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.surfaceBorder),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.2),
                  blurRadius: 10,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(Icons.rocket_launch, size: 48, color: AppColors.primary),
                const SizedBox(height: 16),
                const Text(
                  'Setup Inicial',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Bem-vindo ao OLTAPI. Crie a empresa matriz e a conta de administrador para iniciar.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 32),
                if (_error != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.statusDanger.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.statusDanger.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      _error!,
                      style: const TextStyle(color: AppColors.statusDanger, fontSize: 13),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                if (_success != null) ...[
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.statusOnline.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.statusOnline.withValues(alpha: 0.3)),
                    ),
                    child: Text(
                      _success!,
                      style: const TextStyle(color: AppColors.statusOnline, fontSize: 13),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 16),
                ],
                TextField(
                  controller: _apiKeyController,
                  decoration: const InputDecoration(
                    labelText: 'Master API Key (do arquivo .env)',
                    prefixIcon: Icon(Icons.key, color: AppColors.textSecondary),
                  ),
                  style: const TextStyle(color: AppColors.textPrimary),
                  obscureText: true,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _providerNameController,
                  decoration: const InputDecoration(
                    labelText: 'Nome da Empresa Matriz',
                    prefixIcon: Icon(Icons.business, color: AppColors.textSecondary),
                  ),
                  style: const TextStyle(color: AppColors.textPrimary),
                ),
                const SizedBox(height: 16),
                const Divider(color: AppColors.surfaceBorder),
                const SizedBox(height: 16),
                TextField(
                  controller: _adminNameController,
                  decoration: const InputDecoration(
                    labelText: 'Nome do Administrador',
                    prefixIcon: Icon(Icons.person, color: AppColors.textSecondary),
                  ),
                  style: const TextStyle(color: AppColors.textPrimary),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _adminEmailController,
                  decoration: const InputDecoration(
                    labelText: 'E-mail do Administrador (Login)',
                    prefixIcon: Icon(Icons.email, color: AppColors.textSecondary),
                  ),
                  style: const TextStyle(color: AppColors.textPrimary),
                  keyboardType: TextInputType.emailAddress,
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _adminPasswordController,
                  decoration: const InputDecoration(
                    labelText: 'Senha do Administrador',
                    prefixIcon: Icon(Icons.lock, color: AppColors.textSecondary),
                  ),
                  style: const TextStyle(color: AppColors.textPrimary),
                  obscureText: true,
                  onSubmitted: (_) => _handleSetup(),
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _isLoading ? null : _handleSetup,
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(vertical: 16),
                  ),
                  child: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('FINALIZAR SETUP'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
