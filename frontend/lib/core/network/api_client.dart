import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../models/olt_model.dart';
import '../../models/onu_model.dart';
import '../../models/backup_model.dart';
import '../../models/pon_policy_model.dart';
import '../../models/vlan_model.dart';
import '../../models/governance_models.dart';
import 'api_exception.dart';

class ApiClient {
  String baseUrl;
  String? apiKey;
  String? token;
  final http.Client _client;

  ApiClient({
    required this.baseUrl,
    this.apiKey,
    this.token,
    http.Client? client,
  }) : _client = client ?? http.Client();

  Map<String, String> get _headers {
    final headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    };
    if (token != null && token!.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    } else if (apiKey != null && apiKey!.isNotEmpty) {
      headers['X-API-Key'] = apiKey!;
    }
    return headers;
  }

  String _cleanUrl(String path) {
    final base = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl;
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return '$base$cleanPath';
  }

  Future<dynamic> _handleResponse(http.Response response) {
    final body = response.body;
    dynamic decoded;
    try {
      if (body.isNotEmpty) {
        decoded = jsonDecode(body);
      }
    } catch (_) {
      decoded = body;
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return Future.value(decoded);
    }

    String message = 'Erro ${response.statusCode}';
    if (decoded is Map && decoded.containsKey('detail')) {
      message = decoded['detail'].toString();
    } else if (decoded is String && decoded.isNotEmpty) {
      message = decoded;
    }

    throw ApiException(
      statusCode: response.statusCode,
      message: message,
      details: decoded,
    );
  }

  // Healthcheck & Connectivity
  Future<int> checkHealth() async {
    final stopwatch = Stopwatch()..start();
    try {
      final response = await _client
          .get(Uri.parse(_cleanUrl('/api/v1/olts')), headers: _headers)
          .timeout(const Duration(seconds: 5));
      stopwatch.stop();
      if (response.statusCode == 200 || response.statusCode == 401 || response.statusCode == 403) {
        return stopwatch.elapsedMilliseconds;
      }
      throw ApiException(
        statusCode: response.statusCode,
        message: 'Status inesperado: ${response.statusCode}',
      );
    } catch (e) {
      stopwatch.stop();
      if (e is ApiException) rethrow;
      throw ApiException(statusCode: 0, message: 'Falha de conexão: $e');
    }
  }

  // OLTs
  Future<List<OltModel>> getOlts() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((item) => OltModel.fromJson(item as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<List<String>> getSupportedVendors() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/supported-vendors')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((e) => e.toString()).toList();
    }
    return [];
  }

  Future<List<String>> getSupportedModels(String vendor) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/supported-vendors/$vendor/models')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((e) => e.toString()).toList();
    }
    return [];
  }

  Future<OltModel> createOlt(Map<String, dynamic> oltData) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts')),
          headers: _headers,
          body: jsonEncode(oltData),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OltModel.fromJson(data as Map<String, dynamic>);
  }

  Future<OltModel> updateOlt(String oltId, Map<String, dynamic> oltData) async {
    final response = await _client
        .put(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId')),
          headers: _headers,
          body: jsonEncode(oltData),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OltModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteOlt(String oltId) async {
    final response = await _client
        .delete(Uri.parse(_cleanUrl('/api/v1/olts/$oltId')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<ConnectionTestResult> testOltConnection(String oltId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/test-connection')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return ConnectionTestResult.fromJson(data as Map<String, dynamic>);
  }

  Future<String> getOltConfig(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/config')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    if (data is Map && data.containsKey('config_text')) {
      return data['config_text'].toString();
    }
    return '';
  }

  // Onda A: Onboarding Wizard (2 Fases), Raio-X, Sync Brownfield & Flash VLANs
  Future<OltInspectResultModel> inspectOlt(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/inspect')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 30));
    final data = await _handleResponse(response);
    return OltInspectResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<OltOnboardResultModel> onboardOltWizard(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/onboard-wizard')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 45));
    final data = await _handleResponse(response);
    return OltOnboardResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<OltOnboardResultModel> onboardOltZeroTouch(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/onboard')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 45));
    final data = await _handleResponse(response);
    return OltOnboardResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<OltXRayModel> getOltTelemetry(String oltId) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/telemetry')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 35));
    final data = await _handleResponse(response);
    return OltXRayModel.fromJson(data as Map<String, dynamic>);
  }

  Future<SyncOltResultModel> syncOlt(String oltId) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/sync')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 45));
    final data = await _handleResponse(response);
    return SyncOltResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> enrichOltVlans(String oltId, {bool force = false}) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/enrich-vlans?force=$force')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<List<VlanMetricsModel>> getOltVlanMetrics(String oltId) async {
    final response = await _client
        .get(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/vlans/metrics')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => VlanMetricsModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> createOltVlan(String oltId, Map<String, dynamic> vlanData) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/vlans')),
          headers: _headers,
          body: jsonEncode(vlanData),
        )
        .timeout(const Duration(seconds: 25));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<List<VlanHistoryModel>> getOltVlanHistory(String oltId, int vlanId) async {
    final response = await _client
        .get(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/vlans/$vlanId/history')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => VlanHistoryModel.fromJson(e))
          .toList();
    }
    return [];
  }

  // Backups
  Future<List<BackupModel>> getOltBackups(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/backups')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((item) => BackupModel.fromJson(item as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<BackupModel> triggerOltBackup(String oltId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/backups')), headers: _headers)
        .timeout(const Duration(seconds: 30));
    final data = await _handleResponse(response);
    return BackupModel.fromJson(data as Map<String, dynamic>);
  }

  Future<String> downloadBackupText(String oltId, String backupId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/backups/$backupId/download')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.body;
    }
    throw ApiException(
      statusCode: response.statusCode,
      message: 'Falha ao baixar backup: ${response.statusCode}',
    );
  }

  // Onda B: Disaster Recovery Avançado (Multi-FTP, Unified Diff, Auditoria & Expurgo)
  Future<BackupAuditReportModel> auditOltBackups(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/backups/audit')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return BackupAuditReportModel.fromJson(data as Map<String, dynamic>);
  }

  Future<BackupDiffResultModel> compareOltBackups(
    String oltId, {
    String? baseId,
    String? targetId,
  }) async {
    final queryParams = <String, String>{};
    if (baseId != null && baseId.isNotEmpty) queryParams['base_id'] = baseId;
    if (targetId != null && targetId.isNotEmpty) queryParams['target_id'] = targetId;
    final uri = Uri.parse(_cleanUrl('/api/v1/olts/$oltId/backups/compare'))
        .replace(queryParameters: queryParams.isEmpty ? null : queryParams);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return BackupDiffResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<PurgeResultModel> purgeOltBackups(
    String oltId, {
    int maxBackupsPerOlt = 30,
    int? maxAgeDays,
  }) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/backups/purge')),
          headers: _headers,
          body: jsonEncode({
            'max_backups_per_olt': maxBackupsPerOlt,
            if (maxAgeDays != null) 'max_age_days': maxAgeDays,
          }),
        )
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return PurgeResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<BatchBackupResultModel> runAllBackups({
    bool purgeAfter = true,
    int maxBackupsPerOlt = 30,
    int? maxAgeDays,
  }) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/backups/run-all?purge_after=$purgeAfter')),
          headers: _headers,
          body: jsonEncode({
            'max_backups_per_olt': maxBackupsPerOlt,
            if (maxAgeDays != null) 'max_age_days': maxAgeDays,
          }),
        )
        .timeout(const Duration(seconds: 60));
    final data = await _handleResponse(response);
    return BatchBackupResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<List<BackupAuditReportModel>> auditAllBackups() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/backups/audit-all')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map(BackupAuditReportModel.fromJson)
          .toList();
    }
    return [];
  }

  Future<PurgeResultModel> purgeAllBackups({
    int maxBackupsPerOlt = 30,
    int? maxAgeDays,
  }) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/backups/purge-all')),
          headers: _headers,
          body: jsonEncode({
            'max_backups_per_olt': maxBackupsPerOlt,
            if (maxAgeDays != null) 'max_age_days': maxAgeDays,
          }),
        )
        .timeout(const Duration(seconds: 25));
    final data = await _handleResponse(response);
    return PurgeResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<List<FtpServerModel>> getFtpServers({bool activeOnly = false}) async {
    final response = await _client
        .get(
          Uri.parse(_cleanUrl('/api/v1/ftp-servers?active_only=$activeOnly')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map(FtpServerModel.fromJson)
          .toList();
    }
    return [];
  }

  Future<FtpServerModel> createFtpServer(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/ftp-servers')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return FtpServerModel.fromJson(data as Map<String, dynamic>);
  }

  Future<FtpServerModel> updateFtpServer(
    String ftpId,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .put(
          Uri.parse(_cleanUrl('/api/v1/ftp-servers/$ftpId')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return FtpServerModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteFtpServer(String ftpId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/ftp-servers/$ftpId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<FtpTestResultModel> testFtpServer(String ftpId) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/ftp-servers/$ftpId/test')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return FtpTestResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<OltFtpDestinationsModel> getOltFtpDestinations(String oltId) async {
    final response = await _client
        .get(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/ftp-servers')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OltFtpDestinationsModel.fromJson(data as Map<String, dynamic>);
  }

  Future<OltFtpDestinationsModel> bindOltFtpServers(
    String oltId,
    List<String> ftpServerIds,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/ftp-servers')),
          headers: _headers,
          body: jsonEncode({'ftp_server_ids': ftpServerIds}),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OltFtpDestinationsModel.fromJson(data as Map<String, dynamic>);
  }

  // Unconfigured ONUs
  Future<List<UnauthorizedOnu>> getUnauthorizedOnus(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/unauthorized')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((item) => UnauthorizedOnu.fromJson(item as Map<String, dynamic>)).toList();
    }
    return [];
  }

  // Provisioning
  Future<Map<String, dynamic>> provisionOnu(String oltId, ProvisionRequestModel request) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus')),
          headers: _headers,
          body: jsonEncode(request.toJson()),
        )
        .timeout(const Duration(seconds: 25));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  // Configured ONUs (Inventory)
  Future<List<ConfiguredOnu>> getConfiguredOnus() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/onus')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((item) => ConfiguredOnu.fromJson(item as Map<String, dynamic>)).toList();
    }
    return [];
  }

  // Diagnostics (Optical Signal)
  Future<OnuDiagnostics> getOnuDiagnostics(String oltId, String serialOrId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/$serialOrId')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OnuDiagnostics.fromJson(data as Map<String, dynamic>);
  }

  // Lifecycle Actions
  Future<OnuActionResponse> rebootOnu(String oltId, String serialOrId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/$serialOrId/reboot')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<OnuActionResponse> suspendOnu(String oltId, String serialOrId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/$serialOrId/suspend')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<OnuActionResponse> resumeOnu(String oltId, String serialOrId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/$serialOrId/resume')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<OnuActionResponse> deprovisionOnu(String oltId, String serialOrId) async {
    final response = await _client
        .delete(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/$serialOrId')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  // PON Policies & Dynamic Schemas
  Future<ProvisioningSchemaModel> getProvisioningSchema(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/provisioning-schema')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return ProvisioningSchemaModel.fromJson(data as Map<String, dynamic>);
  }

  Future<List<PonPolicyModel>> getPonPolicies(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/pon-policies')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((e) => PonPolicyModel.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<PonPolicyModel> getPonPolicy(String oltId, String port) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/pon-policies/$port')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return PonPolicyModel.fromJson(data as Map<String, dynamic>);
  }

  Future<PonPolicyModel> savePonPolicy(String oltId, String port, Map<String, dynamic> policyData) async {
    final response = await _client
        .put(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/pon-policies/$port')),
          headers: _headers,
          body: jsonEncode(policyData),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return PonPolicyModel.fromJson(data as Map<String, dynamic>);
  }

  // Auto-Provision Tasks (Cutover Mode)
  Future<AutoProvisionTaskModel> createAutoProvisionTask(String oltId, Map<String, dynamic> taskData) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/tasks/auto-provision')),
          headers: _headers,
          body: jsonEncode(taskData),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return AutoProvisionTaskModel.fromJson(data as Map<String, dynamic>);
  }

  Future<List<AutoProvisionTaskModel>> listAutoProvisionTasks(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/tasks/auto-provision')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data.map((e) => AutoProvisionTaskModel.fromJson(e as Map<String, dynamic>)).toList();
    }
    return [];
  }

  Future<AutoProvisionTaskModel> cancelAutoProvisionTask(String oltId, String taskId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/olts/$oltId/tasks/auto-provision/$taskId/cancel')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return AutoProvisionTaskModel.fromJson(data as Map<String, dynamic>);
  }

  // Setup & Auth
  Future<Map<String, dynamic>> checkSetupStatus() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/setup/status')))
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> initSetup(Map<String, dynamic> req, String masterKey) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/setup/init')),
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': masterKey,
          },
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/auth/login')),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'email': email, 'password': password}),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getMe() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/auth/me')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  // Onda C: Scanner Autônomo (PON Supervision)
  Future<ScannerStatusModel> getScannerStatus() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/scanner/status')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    return ScannerStatusModel.fromJson(data as Map<String, dynamic>);
  }

  Future<ScannerStatusModel> startScanner() async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/scanner/start')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    return ScannerStatusModel.fromJson(data as Map<String, dynamic>);
  }

  Future<ScannerStatusModel> stopScanner() async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/scanner/stop')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    return ScannerStatusModel.fromJson(data as Map<String, dynamic>);
  }

  Future<ScannerRunResultModel> runScannerNow() async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/scanner/run-now')), headers: _headers)
        .timeout(const Duration(seconds: 60));
    final data = await _handleResponse(response);
    return ScannerRunResultModel.fromJson(data as Map<String, dynamic>);
  }

  Future<ScannerStatusModel> updateScannerInterval(int intervalSeconds) async {
    final response = await _client
        .patch(
          Uri.parse(_cleanUrl('/api/v1/scanner/interval')),
          headers: _headers,
          body: jsonEncode({'interval_seconds': intervalSeconds}),
        )
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    return ScannerStatusModel.fromJson(data as Map<String, dynamic>);
  }

  // Onda C: Timeline TR-101 & Reconciliação de Eventos em Campo
  Future<List<OnuMigrationEventModel>> getOnuHistory({
    String? serial,
    int limit = 100,
  }) async {
    final queryParams = <String, String>{'limit': limit.toString()};
    if (serial != null && serial.trim().isNotEmpty) {
      queryParams['serial'] = serial.trim();
    }
    final uri = Uri.parse(_cleanUrl('/api/v1/onus/history'))
        .replace(queryParameters: queryParams);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => OnuMigrationEventModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<ReconcileFieldEventResultModel> reconcileFieldEvent(
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/onus/reconcile-field-event')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 30));
    final data = await _handleResponse(response);
    return ReconcileFieldEventResultModel.fromJson(data as Map<String, dynamic>);
  }

  // Onda C: Webhooks HMAC
  Future<List<WebhookSubscriptionModel>> getWebhooks() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/webhooks')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => WebhookSubscriptionModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<WebhookSubscriptionModel> createWebhook(
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/webhooks')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return WebhookSubscriptionModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteWebhook(String subscriptionId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/webhooks/$subscriptionId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<WebhookDeliveryLogModel> pingWebhook(String subscriptionId) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/webhooks/$subscriptionId/ping')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return WebhookDeliveryLogModel.fromJson(data as Map<String, dynamic>);
  }

  Future<List<WebhookDeliveryLogModel>> getWebhookDeliveries({
    String? subscriptionId,
    int limit = 50,
  }) async {
    final queryParams = <String, String>{'limit': limit.toString()};
    if (subscriptionId != null && subscriptionId.isNotEmpty) {
      queryParams['subscription_id'] = subscriptionId;
    }
    final uri = Uri.parse(_cleanUrl('/api/v1/webhooks/deliveries'))
        .replace(queryParameters: queryParams);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => WebhookDeliveryLogModel.fromJson(e))
          .toList();
    }
    return [];
  }

  // Onda C: Inquilinos & Rede Neutra (Tenants & VLAN Allocations)
  Future<List<TenantModel>> getTenants() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/tenants')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => TenantModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<TenantModel> createTenant(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/tenants')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return TenantModel.fromJson(data as Map<String, dynamic>);
  }

  Future<TenantVlanAllocationModel> allocateTenantVlan(
    String tenantId,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/tenants/$tenantId/vlans')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return TenantVlanAllocationModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> revokeTenantVlan(String tenantId, String allocationId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/tenants/$tenantId/vlans/$allocationId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  // Onda C: Usuários RBAC
  Future<List<UserAccountModel>> getUsers() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/users')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => UserAccountModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<UserAccountModel> createUser(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/users')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return UserAccountModel.fromJson(data as Map<String, dynamic>);
  }

  Future<UserAccountModel> updateUser(
    String userId,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .patch(
          Uri.parse(_cleanUrl('/api/v1/users/$userId')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return UserAccountModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteUser(String userId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/users/$userId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  // Onda C: API Keys
  Future<List<ApiKeyModel>> getApiKeys() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/api-keys')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => ApiKeyModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<ApiKeyCreatedModel> createApiKey(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/api-keys')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return ApiKeyCreatedModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> revokeApiKey(String apiKeyId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/api-keys/$apiKeyId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  // =========================================================================
  // FASE 1: Tabela MAC FDB por ONU
  // =========================================================================
  Future<List<OnuMacEntryModel>> getOnuMacTable(
    String oltId,
    String serialOrId, {
    String? port,
    int? onuId,
  }) async {
    final queryParams = <String, String>{};
    if (port != null && port.isNotEmpty) queryParams['port'] = port;
    if (onuId != null) queryParams['onu_id'] = onuId.toString();
    final uri = Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/$serialOrId/macs'))
        .replace(queryParameters: queryParams.isEmpty ? null : queryParams);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => OnuMacEntryModel.fromJson(e))
          .toList();
    }
    return [];
  }

  // =========================================================================
  // FASE 2: Telemetria Óptica Histórica & Radar de Degradação
  // =========================================================================
  Future<OpticalTelemetryHistoryModel> getOnuOpticalHistory(
    String serial, {
    int limit = 100,
  }) async {
    final uri = Uri.parse(_cleanUrl('/api/v1/onus/$serial/optical-history'))
        .replace(queryParameters: {'limit': limit.toString()});
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OpticalTelemetryHistoryModel.fromJson(data as Map<String, dynamic>);
  }

  Future<List<DegradedOnuItemModel>> getDegradedOnus({
    String? oltId,
    double thresholdDbm = -25.5,
    double driftThresholdDb = -2.5,
  }) async {
    final queryParams = <String, String>{
      'threshold_dbm': thresholdDbm.toString(),
      'drift_threshold_db': driftThresholdDb.toString(),
    };
    if (oltId != null && oltId.isNotEmpty) queryParams['olt_id'] = oltId;
    final uri = Uri.parse(_cleanUrl('/api/v1/onus/degraded'))
        .replace(queryParameters: queryParams);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => DegradedOnuItemModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> collectOpticalTelemetry(
    String oltId, {
    String? port,
    int maxOnus = 64,
  }) async {
    final queryParams = <String, String>{'max_onus': maxOnus.toString()};
    if (port != null && port.isNotEmpty) queryParams['port'] = port;
    final uri =
        Uri.parse(_cleanUrl('/api/v1/olts/$oltId/telemetry/collect-optical'))
            .replace(queryParameters: queryParams);
    final response = await _client
        .post(uri, headers: _headers)
        .timeout(const Duration(seconds: 60));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  // =========================================================================
  // FASE 3: Presets Universais, Pré-Provisionamento & Ações em Lote
  // =========================================================================
  Future<List<ProvisioningPresetModel>> getPresets() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/presets')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => ProvisioningPresetModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<ProvisioningPresetModel> createPreset(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/presets')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return ProvisioningPresetModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deletePreset(String presetId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/presets/$presetId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<ConfiguredOnu> preProvisionOnu(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/onus/pre-provision')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return ConfiguredOnu.fromJson(data as Map<String, dynamic>);
  }

  Future<BatchOnuActionResponseModel> batchOnuAction(
    String oltId,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/olts/$oltId/onus/batch-action')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 60));
    final data = await _handleResponse(response);
    return BatchOnuActionResponseModel.fromJson(data as Map<String, dynamic>);
  }

  // =========================================================================
  // FASE 4: Topologia Passiva FTTH (Zonas, CTOs/ODBs & Mapa de Saúde)
  // =========================================================================
  Future<List<NetworkZoneModel>> getNetworkZones() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/topology/zones')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => NetworkZoneModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<NetworkZoneModel> createNetworkZone(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/topology/zones')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return NetworkZoneModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteNetworkZone(String zoneId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/topology/zones/$zoneId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<List<OpticalDistributionBoxModel>> getOdbs({
    String? zoneId,
    String? oltId,
  }) async {
    final queryParams = <String, String>{};
    if (zoneId != null && zoneId.isNotEmpty) queryParams['zone_id'] = zoneId;
    if (oltId != null && oltId.isNotEmpty) queryParams['olt_id'] = oltId;
    final uri = Uri.parse(_cleanUrl('/api/v1/topology/odbs'))
        .replace(queryParameters: queryParams.isEmpty ? null : queryParams);
    final response = await _client
        .get(uri, headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => OpticalDistributionBoxModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<OpticalDistributionBoxModel> createOdb(
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/topology/odbs')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OpticalDistributionBoxModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteOdb(String odbId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/topology/odbs/$odbId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<Map<String, dynamic>> assignOnuTopology(
    String serial,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .patch(
          Uri.parse(_cleanUrl('/api/v1/onus/$serial/topology')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<TopologyHealthMapModel> getTopologyHealthMap() async {
    final response = await _client
        .get(
          Uri.parse(_cleanUrl('/api/v1/topology/health-map')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return TopologyHealthMapModel.fromJson(data as Map<String, dynamic>);
  }

  // =========================================================================
  // FASE 5: Integração ACS TR-069 / CWMP (GenieACS)
  // =========================================================================
  Future<List<AcsServerConfigModel>> getAcsServers() async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/acs/servers')), headers: _headers)
        .timeout(const Duration(seconds: 10));
    final data = await _handleResponse(response);
    if (data is List) {
      return data
          .whereType<Map<String, dynamic>>()
          .map((e) => AcsServerConfigModel.fromJson(e))
          .toList();
    }
    return [];
  }

  Future<AcsServerConfigModel> createAcsServer(Map<String, dynamic> req) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/acs/servers')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return AcsServerConfigModel.fromJson(data as Map<String, dynamic>);
  }

  Future<void> deleteAcsServer(String acsId) async {
    final response = await _client
        .delete(
          Uri.parse(_cleanUrl('/api/v1/acs/servers/$acsId')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    await _handleResponse(response);
  }

  Future<Map<String, dynamic>> testAcsServer(String acsId) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/acs/servers/$acsId/test')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<Tr069DeviceSummaryModel> getOnuTr069Summary(String serial) async {
    final response = await _client
        .get(
          Uri.parse(_cleanUrl('/api/v1/onus/$serial/tr069')),
          headers: _headers,
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return Tr069DeviceSummaryModel.fromJson(data as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> configureOnuTr069Wifi(
    String serial,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/onus/$serial/tr069/wifi')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> configureOnuTr069Wan(
    String serial,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/onus/$serial/tr069/wan')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> pushOnuTr069Firmware(
    String serial,
    Map<String, dynamic> req,
  ) async {
    final response = await _client
        .post(
          Uri.parse(_cleanUrl('/api/v1/onus/$serial/tr069/firmware')),
          headers: _headers,
          body: jsonEncode(req),
        )
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return data as Map<String, dynamic>;
  }
}
