import sys

with open("frontend/lib/core/network/api_client.dart", "r") as f:
    content = f.read()

import_line = "import '../../models/onu_model.dart';\n"
new_import = import_line + "import '../../models/provisioning_schema_model.dart';\n"
content = content.replace(import_line, new_import)

provision_block = "  // Provisioning\n"
schema_method = """  Future<ProvisioningSchemaModel> getProvisioningSchema(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/provisioning-schema')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return ProvisioningSchemaModel.fromJson(data as Map<String, dynamic>);
  }

"""
content = content.replace(provision_block, provision_block + schema_method)

with open("frontend/lib/core/network/api_client.dart", "w") as f:
    f.write(content)
