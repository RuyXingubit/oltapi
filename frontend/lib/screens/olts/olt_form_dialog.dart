import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';

class OltFormDialog extends StatefulWidget {
  final OltModel? olt;

  const OltFormDialog({super.key, this.olt});

  @override
  State<OltFormDialog> createState() => _OltFormDialogState();
}

class _OltFormDialogState extends State<OltFormDialog> {
  final _formKey = GlobalKey<FormState>();

  late TextEditingController _nameCtrl;
  late TextEditingController _modelCtrl;
  late TextEditingController _hostCtrl;
  late TextEditingController _portCtrl;
  late TextEditingController _usernameCtrl;
  late TextEditingController _passwordCtrl;
  late TextEditingController _snmpCommunityCtrl;
  late TextEditingController _snmpPortCtrl;

  String _vendor = 'intelbras';
  String _protocol = 'ssh';
  bool _isLoading = false;
  String? _error;

  final List<String> _vendors = ['intelbras', 'huawei', 'fiberhome', 'vsol', 'zte', 'parks', 'cdata'];
  final List<String> _protocols = ['ssh', 'telnet'];

  @override
  void initState() {
    super.initState();
    _nameCtrl = TextEditingController(text: widget.olt?.name ?? '');
    _modelCtrl = TextEditingController(text: widget.olt?.model ?? '');
    _hostCtrl = TextEditingController(text: widget.olt?.host ?? '');
    _portCtrl = TextEditingController(text: widget.olt != null ? widget.olt!.port.toString() : '22');
    _usernameCtrl = TextEditingController();
    _passwordCtrl = TextEditingController();
    _snmpCommunityCtrl = TextEditingController(text: widget.olt?.snmpCommunity ?? 'public');
    _snmpPortCtrl = TextEditingController(text: widget.olt?.snmpPort?.toString() ?? '161');

    if (widget.olt != null) {
      if (_vendors.contains(widget.olt!.vendor.toLowerCase())) {
        _vendor = widget.olt!.vendor.toLowerCase();
      }
      if (_protocols.contains(widget.olt!.protocol.toLowerCase())) {
        _protocol = widget.olt!.protocol.toLowerCase();
      }
    }
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final data = {
      'name': _nameCtrl.text.trim(),
      'vendor': _vendor,
      'model': _modelCtrl.text.trim(),
      'host': _hostCtrl.text.trim(),
      'port': int.tryParse(_portCtrl.text.trim()) ?? 22,
      'protocol': _protocol,
      'username': _usernameCtrl.text.trim(),
      'password': _passwordCtrl.text.trim(),
      'snmp_community': _snmpCommunityCtrl.text.trim(),
      'snmp_port': int.tryParse(_snmpPortCtrl.text.trim()) ?? 161,
      'snmp_version': 'v2c',
    };

    // Removendo campos em branco no UPDATE caso o user não queira trocar senha
    if (widget.olt != null) {
      if (data['username'] == '') data.remove('username');
      if (data['password'] == '') data.remove('password');
    }

    try {
      final appState = context.read<AppState>();
      OltModel? result;
      
      if (widget.olt == null) {
        result = await appState.createOlt(data);
      } else {
        result = await appState.updateOlt(widget.olt!.id, data);
      }

      if (result != null && mounted) {
        Navigator.of(context).pop(true);
      } else {
        setState(() {
          _error = appState.errorMessage ?? 'Erro desconhecido ao salvar OLT';
        });
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      backgroundColor: AppColors.surface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Container(
        width: 600,
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    widget.olt == null ? 'Nova OLT' : 'Editar OLT',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppColors.textPrimary),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close, color: AppColors.textSecondary),
                    onPressed: () => Navigator.of(context).pop(),
                  )
                ],
              ),
              const SizedBox(height: 16),
              if (_error != null) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  color: AppColors.statusDanger.withValues(alpha: 0.1),
                  child: Text(_error!, style: const TextStyle(color: AppColors.statusDanger)),
                ),
                const SizedBox(height: 16),
              ],
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      _buildTextField(_nameCtrl, 'Nome da OLT (Identificação)', Icons.label, required: true),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: DropdownButtonFormField<String>(
                              initialValue: _vendor,
                              dropdownColor: AppColors.surfaceHover,
                              decoration: const InputDecoration(labelText: 'Fabricante', prefixIcon: Icon(Icons.precision_manufacturing, color: AppColors.textSecondary)),
                              items: _vendors.map((v) => DropdownMenuItem(value: v, child: Text(v.toUpperCase(), style: const TextStyle(color: AppColors.textPrimary)))).toList(),
                              onChanged: (v) => setState(() => _vendor = v!),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(child: _buildTextField(_modelCtrl, 'Modelo (Ex: MA5800)', Icons.memory, required: true)),
                        ],
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(flex: 2, child: _buildTextField(_hostCtrl, 'Endereço IP (Gerência)', Icons.computer, required: true)),
                          const SizedBox(width: 16),
                          Expanded(flex: 1, child: _buildTextField(_portCtrl, 'Porta', Icons.numbers, isNumber: true, required: true)),
                          const SizedBox(width: 16),
                          Expanded(
                            flex: 1,
                            child: DropdownButtonFormField<String>(
                              initialValue: _protocol,
                              dropdownColor: AppColors.surfaceHover,
                              decoration: const InputDecoration(labelText: 'Protocolo'),
                              items: _protocols.map((p) => DropdownMenuItem(value: p, child: Text(p.toUpperCase(), style: const TextStyle(color: AppColors.textPrimary)))).toList(),
                              onChanged: (v) => setState(() => _protocol = v!),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      const Divider(color: AppColors.surfaceBorder),
                      const SizedBox(height: 16),
                      const Text('Credenciais de Acesso (Terminal)', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(child: _buildTextField(_usernameCtrl, widget.olt == null ? 'Usuário (Admin)' : 'Novo Usuário (em branco para manter)', Icons.person, required: widget.olt == null)),
                          const SizedBox(width: 16),
                          Expanded(child: _buildTextField(_passwordCtrl, widget.olt == null ? 'Senha' : 'Nova Senha (em branco para manter)', Icons.lock, obscure: true, required: widget.olt == null)),
                        ],
                      ),
                      const SizedBox(height: 16),
                      const Divider(color: AppColors.surfaceBorder),
                      const SizedBox(height: 16),
                      const Text('Telemetria (SNMP)', style: TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(child: _buildTextField(_snmpCommunityCtrl, 'Comunidade SNMP (v2c)', Icons.sensors)),
                          const SizedBox(width: 16),
                          Expanded(child: _buildTextField(_snmpPortCtrl, 'Porta SNMP', Icons.numbers, isNumber: true)),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancelar', style: TextStyle(color: AppColors.textSecondary)),
                  ),
                  const SizedBox(width: 16),
                  ElevatedButton(
                    onPressed: _isLoading ? null : _save,
                    child: _isLoading ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Salvar OLT'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, IconData icon, {bool isNumber = false, bool obscure = false, bool required = false}) {
    return TextFormField(
      controller: controller,
      obscureText: obscure,
      keyboardType: isNumber ? TextInputType.number : TextInputType.text,
      style: const TextStyle(color: AppColors.textPrimary),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, color: AppColors.textSecondary, size: 20),
      ),
      validator: (value) {
        if (required && (value == null || value.trim().isEmpty)) {
          return 'Campo obrigatório';
        }
        return null;
      },
    );
  }
}
