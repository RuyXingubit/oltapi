import re

with open("frontend/lib/screens/unconfigured/authorize_onu_dialog.dart", "r") as f:
    content = f.read()

# Add provider import
content = content.replace("import '../../models/onu_model.dart';", "import '../../models/onu_model.dart';\nimport 'package:provider/provider.dart';\nimport '../../providers/app_state.dart';")

# We want to replace the VLAN and Profile TextFormFields with Dropdowns if they are available in schema
old_vlan_profile_row = """                    Expanded(
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
                    ),"""

new_vlan_profile_row = """                    Expanded(
                      flex: 2,
                      child: _buildVlanField(context),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      flex: 3,
                      child: _buildProfileField(context),
                    ),"""

content = content.replace(old_vlan_profile_row, new_vlan_profile_row)

helper_methods = """  Widget _buildVlanField(BuildContext context) {
    final schema = context.watch<AppState>().provisioningSchema;
    final vlans = schema?.availableVlans ?? [];
    
    if (vlans.isNotEmpty) {
      if (!vlans.any((v) => v['id'].toString() == _vlanController.text) && _vlanController.text.isNotEmpty) {
        _vlanController.text = vlans.first['id'].toString();
      }
      return DropdownButtonFormField<String>(
        value: _vlanController.text.isNotEmpty ? _vlanController.text : null,
        dropdownColor: AppColors.surfaceHover,
        decoration: const InputDecoration(
          labelText: 'VLAN de Serviço *',
        ),
        items: vlans.map((v) {
          final String idStr = v['id'].toString();
          final String nameStr = v['name'] ?? 'VLAN $idStr';
          return DropdownMenuItem(value: idStr, child: Text('$idStr - $nameStr', style: const TextStyle(color: AppColors.textPrimary)));
        }).toList(),
        onChanged: (val) {
          if (val != null) setState(() => _vlanController.text = val);
        },
        validator: (value) => (value == null || value.trim().isEmpty) ? 'Obrigatório' : null,
      );
    }
    
    // Fallback to text field if schema has no VLANs (should not happen with strict api)
    return TextFormField(
      controller: _vlanController,
      keyboardType: TextInputType.number,
      decoration: const InputDecoration(labelText: 'VLAN de Serviço *', hintText: 'Ex: 100'),
      validator: (value) {
        if (value == null || value.trim().isEmpty) return 'Obrigatório';
        final v = int.tryParse(value.trim());
        if (v == null || v < 1 || v > 4094) return '1 - 4094';
        return null;
      },
    );
  }

  Widget _buildProfileField(BuildContext context) {
    final schema = context.watch<AppState>().provisioningSchema;
    final profiles = schema?.availableProfiles ?? [];
    
    if (profiles.isNotEmpty) {
      if (!profiles.any((p) => p['name'].toString() == _profileController.text) && profiles.isNotEmpty) {
        _profileController.text = profiles.first['name'].toString();
      }
      return DropdownButtonFormField<String>(
        value: _profileController.text.isNotEmpty ? _profileController.text : null,
        dropdownColor: AppColors.surfaceHover,
        decoration: const InputDecoration(
          labelText: 'Perfil de Tráfego',
        ),
        items: profiles.map((p) {
          final String nameStr = p['name'].toString();
          return DropdownMenuItem(value: nameStr, child: Text(nameStr, style: const TextStyle(color: AppColors.textPrimary), overflow: TextOverflow.ellipsis));
        }).toList(),
        onChanged: (val) {
          if (val != null) setState(() => _profileController.text = val);
        },
      );
    }
    
    // Fallback if none returned by driver
    return TextFormField(
      controller: _profileController,
      decoration: const InputDecoration(labelText: 'Perfil de Tráfego', hintText: 'DEFAULT'),
    );
  }"""

content = content.replace("  @override\n  Widget build(BuildContext context) {", helper_methods + "\n\n  @override\n  Widget build(BuildContext context) {")

with open("frontend/lib/screens/unconfigured/authorize_onu_dialog.dart", "w") as f:
    f.write(content)
