import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/onu_model.dart';

class AuthorizeOnuDialog extends StatefulWidget {
  final UnauthorizedOnu onu;
  final int? initialVlan;
  final String? initialProfile;
  final Function(int vlan, String profile, String description) onAuthorize;

  const AuthorizeOnuDialog({
    super.key,
    required this.onu,
    this.initialVlan,
    this.initialProfile,
    required this.onAuthorize,
  });

  @override
  State<AuthorizeOnuDialog> createState() => _AuthorizeOnuDialogState();
}

class _AuthorizeOnuDialogState extends State<AuthorizeOnuDialog> {
  final _formKey = GlobalKey<FormState>();
  final _subscriberController = TextEditingController();
  late final TextEditingController _vlanController;
  late final TextEditingController _profileController;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _vlanController = TextEditingController(text: (widget.initialVlan ?? 100).toString());
    _profileController = TextEditingController(text: widget.initialProfile ?? 'DEFAULT');
  }

  @override
  void dispose() {
    _subscriberController.dispose();
    _vlanController.dispose();
    _profileController.dispose();
    super.dispose();
  }

  void _submit() {
    if (_formKey.currentState?.validate() ?? false) {
      setState(() => _isSubmitting = true);
      final vlan = int.parse(_vlanController.text.trim());
      final profile = _profileController.text.trim();
      final description = _subscriberController.text.trim();

      widget.onAuthorize(vlan, profile, description);
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: AppColors.surfaceBorder, width: 1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 500),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
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
                              Icons.verified_user_outlined,
                              color: AppColors.primaryLight,
                              size: 20,
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Flexible(
                            child: Text(
                              'Autorizar ONU (Provision)',
                              style: TextStyle(
                                fontSize: 18,
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
                      icon: const Icon(Icons.close, color: AppColors.textSecondary, size: 20),
                      onPressed: () => Navigator.of(context).pop(),
                      splashRadius: 20,
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.codeBackground,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: AppColors.surfaceBorder),
                  ),
                  child: Column(
                    children: [
                      Row(
                        children: [
                          const Text(
                            'Serial: ',
                            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                          ),
                          Expanded(
                            child: SelectableText(
                              widget.onu.serial,
                              style: const TextStyle(
                                color: AppColors.accentCyan,
                                fontWeight: FontWeight.w600,
                                fontFamily: 'monospace',
                                fontSize: 13,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          const Text(
                            'Porta PON: ',
                            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                          ),
                          Text(
                            widget.onu.port,
                            style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontWeight: FontWeight.w500,
                              fontSize: 13,
                            ),
                          ),
                          const SizedBox(width: 24),
                          const Text(
                            'Modelo: ',
                            style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
                          ),
                          Flexible(
                            child: Text(
                              widget.onu.model ?? 'Auto-detect',
                              style: const TextStyle(
                                color: AppColors.textPrimary,
                                fontSize: 13,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                TextFormField(
                  controller: _subscriberController,
                  decoration: const InputDecoration(
                    labelText: 'Identificação / Assinante *',
                    hintText: 'Ex: Cliente_Joao_Silva',
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Informe o nome do cliente ou identificação';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: 14),
                Row(
                  children: [
                    Expanded(
                      flex: 2,
                      child: TextFormField(
                        controller: _vlanController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(
                          labelText: 'VLAN de Serviço *',
                          hintText: 'Ex: 100',
                        ),
                        validator: (value) {
                          if (value == null || value.trim().isEmpty) {
                            return 'Obrigatório';
                          }
                          final v = int.tryParse(value.trim());
                          if (v == null || v < 1 || v > 4094) {
                            return '1 - 4094';
                          }
                          return null;
                        },
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      flex: 3,
                      child: TextFormField(
                        controller: _profileController,
                        decoration: const InputDecoration(
                          labelText: 'Perfil de Tráfego',
                          hintText: 'DEFAULT',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    OutlinedButton(
                      onPressed: _isSubmitting ? null : () => Navigator.of(context).pop(),
                      child: const Text('Cancelar'),
                    ),
                    const SizedBox(width: 12),
                    ElevatedButton.icon(
                      onPressed: _isSubmitting ? null : _submit,
                      icon: _isSubmitting
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.check, size: 18),
                      label: const Text('Autorizar ONU'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
