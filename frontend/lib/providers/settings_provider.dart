import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/network/api_client.dart';

class SettingsProvider extends ChangeNotifier {
  static const String _keyBaseUrl = 'oltapi_base_url';
  static const String _keyApiKey = 'oltapi_api_key';

  static const String defaultBaseUrl = 'http://localhost:8000';
  static const String defaultApiKey = 'oltapi_secret_default_key_change_me';

  String _baseUrl = defaultBaseUrl;
  String _apiKey = defaultApiKey;
  bool _isLoading = true;
  bool _isConnected = false;
  int? _latencyMs;
  String? _lastError;

  String get baseUrl => _baseUrl;
  String get apiKey => _apiKey;
  bool get isLoading => _isLoading;
  bool get isConnected => _isConnected;
  int? get latencyMs => _latencyMs;
  String? get lastError => _lastError;

  late ApiClient apiClient;

  SettingsProvider() {
    apiClient = ApiClient(baseUrl: _baseUrl, apiKey: _apiKey);
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    _isLoading = true;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      _baseUrl = prefs.getString(_keyBaseUrl) ?? defaultBaseUrl;
      _apiKey = prefs.getString(_keyApiKey) ?? defaultApiKey;
      apiClient = ApiClient(baseUrl: _baseUrl, apiKey: _apiKey);
    } catch (_) {
      // Fallback para defaults
    } finally {
      _isLoading = false;
      notifyListeners();
      checkBackendHealth();
    }
  }

  Future<void> updateSettings({required String baseUrl, required String apiKey}) async {
    _baseUrl = baseUrl.trim();
    _apiKey = apiKey.trim();
    apiClient = ApiClient(baseUrl: _baseUrl, apiKey: _apiKey);

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_keyBaseUrl, _baseUrl);
      await prefs.setString(_keyApiKey, _apiKey);
    } catch (_) {}

    notifyListeners();
    await checkBackendHealth();
  }

  Future<bool> checkBackendHealth() async {
    try {
      _lastError = null;
      final latency = await apiClient.checkHealth();
      _latencyMs = latency;
      _isConnected = true;
      notifyListeners();
      return true;
    } catch (e) {
      _isConnected = false;
      _latencyMs = null;
      _lastError = e.toString();
      notifyListeners();
      return false;
    }
  }
}
