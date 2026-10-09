with open("frontend/lib/providers/app_state.dart", "r") as f:
    content = f.read()

import_line = "import '../models/onu_model.dart';\n"
new_import = import_line + "import '../models/provisioning_schema_model.dart';\n"
content = content.replace(import_line, new_import)

var_line = "  List<ConfiguredOnu> _configuredOnus = [];\n"
new_var = var_line + "  ProvisioningSchemaModel? _provisioningSchema;\n"
content = content.replace(var_line, new_var)

get_line = "  List<ConfiguredOnu> get configuredOnus => _configuredOnus;\n"
new_get = get_line + "  ProvisioningSchemaModel? get provisioningSchema => _provisioningSchema;\n"
content = content.replace(get_line, new_get)

prov_method = """  Future<void> loadProvisioningSchema() async {
    if (_selectedOlt == null) return;
    try {
      _provisioningSchema = await apiClient.getProvisioningSchema(_selectedOlt!.id);
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Falha ao buscar esquema de provisionamento: $e';
      notifyListeners();
    }
  }

"""
content = content.replace("  // Provisioning\n", "  // Provisioning\n" + prov_method)

# call it in selectOlt
select_old = """    if (olt != null) {
      loadUnauthorizedOnus();
    } else {"""
select_new = """    if (olt != null) {
      loadUnauthorizedOnus();
      loadProvisioningSchema();
    } else {"""
content = content.replace(select_old, select_new)

refresh_old = """      if (_selectedOlt != null) loadUnauthorizedOnus(),"""
refresh_new = """      if (_selectedOlt != null) loadUnauthorizedOnus(),
      if (_selectedOlt != null) loadProvisioningSchema(),"""
content = content.replace(refresh_old, refresh_new)

with open("frontend/lib/providers/app_state.dart", "w") as f:
    f.write(content)
