with open("frontend/lib/screens/olts/olt_form_dialog.dart", "r") as f:
    content = f.read()

import re

old_block = """                          const SizedBox(width: 16),
                          Expanded(
                            child: Autocomplete<String>("""

new_block = """                          const SizedBox(width: 16),
                          Expanded(
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
                                  ),"""

import sys
start_idx = content.find(old_block)
if start_idx == -1:
    print("Failed to find start_idx")
    sys.exit(1)

# Find the end of the Expanded block
# It ends with:
#                                 );
#                               },
#                             ),
#                           ),
end_block = """                                );
                              },
                            ),
                          ),"""
end_idx = content.find(end_block, start_idx)
if end_idx == -1:
    print("Failed to find end_idx")
    sys.exit(1)

end_idx += len(end_block)

new_content = content[:start_idx] + new_block + "\n                          )," + content[end_idx:]

with open("frontend/lib/screens/olts/olt_form_dialog.dart", "w") as f:
    f.write(new_content)
print("Success")
