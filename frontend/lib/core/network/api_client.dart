import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../../models/olt_model.dart';
import '../../models/onu_model.dart';
import '../../models/backup_model.dart';
import 'api_exception.dart';

class ApiClient {
  String baseUrl;
  String apiKey;
  final http.Client _client;

  ApiClient({
    required this.baseUrl,
    required this.apiKey,
    http.Client? client,
  }) : _client = client ?? http.Client();

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-API-Key': apiKey,
      };

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

  // Unconfigured ONUs
  Future<List<UnauthorizedOnu>> getUnauthorizedOnus(String oltId) async {
    final response = await _client
        .get(Uri.parse(_cleanUrl('/api/v1/provision/$oltId/unauthorized')), headers: _headers)
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
          Uri.parse(_cleanUrl('/api/v1/provision/$oltId/onus')),
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
        .get(Uri.parse(_cleanUrl('/api/v1/diagnostics/$oltId/onus/$serialOrId')), headers: _headers)
        .timeout(const Duration(seconds: 15));
    final data = await _handleResponse(response);
    return OnuDiagnostics.fromJson(data as Map<String, dynamic>);
  }

  // Lifecycle Actions
  Future<OnuActionResponse> rebootOnu(String oltId, String serialOrId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/provision/$oltId/onus/$serialOrId/reboot')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<OnuActionResponse> suspendOnu(String oltId, String serialOrId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/provision/$oltId/onus/$serialOrId/suspend')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<OnuActionResponse> resumeOnu(String oltId, String serialOrId) async {
    final response = await _client
        .post(Uri.parse(_cleanUrl('/api/v1/provision/$oltId/onus/$serialOrId/resume')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }

  Future<OnuActionResponse> deprovisionOnu(String oltId, String serialOrId) async {
    final response = await _client
        .delete(Uri.parse(_cleanUrl('/api/v1/provision/$oltId/onus/$serialOrId')), headers: _headers)
        .timeout(const Duration(seconds: 20));
    final data = await _handleResponse(response);
    return OnuActionResponse.fromJson(data as Map<String, dynamic>);
  }
}
