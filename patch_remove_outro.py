with open("frontend/lib/screens/olts/olt_form_dialog.dart", "r") as f:
    content = f.read()

import sys

old_block = """                          Expanded(
                            child: _isCustomModel || _currentModels.isEmpty
                                ? Row(
                                    children: [
                                      Expanded(
                                        child: TextFormField(
                                          controller: _modelCtrl,
                                          style: const TextStyle(color: AppColors.textPrimary),
                                          decoration: const InputDecoration(
                                            labelText: 'Modelo',
                                            prefixIcon: Icon(Icons.memory, color: AppColors.textSecondary, size: 20),
                                          ),
                                          validator: (value) => (value == null || value.trim().isEmpty) ? 'Obrigatório' : null,
                                        ),
                                      ),
                                      if (_currentModels.isNotEmpty)
                                        IconButton(
                                          icon: const Icon(Icons.arrow_drop_down, color: AppColors.textSecondary),
                                          onPressed: () {
                                            setState(() {
                                              _isCustomModel = false;
                                              _modelCtrl.text = _currentModels.first;
                                            });
                                          },
                                        ),
                                    ],
                                  )
                                : DropdownButtonFormField<String>(
                                    value: _currentModels.contains(_modelCtrl.text) ? _modelCtrl.text : (_currentModels.isNotEmpty ? _currentModels.first : null),
                                    dropdownColor: AppColors.surfaceHover,
                                    decoration: const InputDecoration(
                                      labelText: 'Modelo',
                                      prefixIcon: Icon(Icons.memory, color: AppColors.textSecondary, size: 20),
                                    ),
                                    items: [
                                      ..._currentModels.map((m) => DropdownMenuItem(value: m, child: Text(m.toUpperCase(), style: const TextStyle(color: AppColors.textPrimary)))),
                                      const DropdownMenuItem(value: 'outro', child: Text('OUTRO (DIGITAR)', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold))),
                                    ],
                                    onChanged: (v) {
                                      if (v == 'outro') {
                                        setState(() {
                                          _isCustomModel = true;
                                          _modelCtrl.text = '';
                                        });
                                      } else if (v != null) {
                                        setState(() {
                                          _modelCtrl.text = v;
                                        });
                                      }
                                    },
                                  ),
                          ),"""

new_block = """                          Expanded(
                            child: DropdownButtonFormField<String>(
                              value: _currentModels.contains(_modelCtrl.text) ? _modelCtrl.text : (_currentModels.isNotEmpty ? _currentModels.first : null),
                              dropdownColor: AppColors.surfaceHover,
                              decoration: const InputDecoration(
                                labelText: 'Modelo',
                                prefixIcon: Icon(Icons.memory, color: AppColors.textSecondary, size: 20),
                              ),
                              items: _currentModels.map((m) => DropdownMenuItem(value: m, child: Text(m.toUpperCase(), style: const TextStyle(color: AppColors.textPrimary)))).toList(),
                              onChanged: (v) {
                                if (v != null) {
                                  setState(() {
                                    _modelCtrl.text = v;
                                  });
                                }
                              },
                              validator: (value) => (value == null || value.trim().isEmpty) ? 'Obrigatório' : null,
                            ),
                          ),"""

if old_block in content:
    new_content = content.replace(old_block, new_block)
    # Also remove _isCustomModel state
    new_content = new_content.replace("  bool _isCustomModel = false;\n", "")
    new_content = new_content.replace("                                    _isCustomModel = false;\n", "")
    
    with open("frontend/lib/screens/olts/olt_form_dialog.dart", "w") as f:
        f.write(new_content)
    print("Success")
else:
    print("Failed to find old block")
    sys.exit(1)
