import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/network/api_client.dart';
import 'settings_provider.dart';

class AuthProvider extends ChangeNotifier {
  static const String _keyToken = 'oltapi_jwt_token';

  final SettingsProvider settingsProvider;
  
  bool _isLoading = true;
  bool _isAuthenticated = false;
  bool _isSetupRequired = false;
  Map<String, dynamic>? _userProfile;
  
  bool get isLoading => _isLoading;
  bool get isAuthenticated => _isAuthenticated;
  bool get isSetupRequired => _isSetupRequired;
  Map<String, dynamic>? get userProfile => _userProfile;

  AuthProvider({required this.settingsProvider}) {
    _initAuth();
  }

  ApiClient get apiClient => settingsProvider.apiClient;

  Future<void> _initAuth() async {
    _isLoading = true;
    notifyListeners();

    try {
      // 1. Check if backend needs setup
      final status = await apiClient.checkSetupStatus();
      if (status['is_configured'] == false) {
        _isSetupRequired = true;
        _isLoading = false;
        notifyListeners();
        return;
      }
      _isSetupRequired = false;

      // 2. Load token and try to get profile
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString(_keyToken);
      
      if (token != null && token.isNotEmpty) {
        apiClient.token = token;
        final profile = await apiClient.getMe();
        _userProfile = profile;
        _isAuthenticated = true;
      }
    } catch (e) {
      // Token invalid or network error
      apiClient.token = null;
      _isAuthenticated = false;
      _userProfile = null;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> login(String email, String password) async {
    _isLoading = true;
    notifyListeners();
    try {
      final data = await apiClient.login(email, password);
      final token = data['access_token'];
      if (token != null) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_keyToken, token);
        apiClient.token = token;
        
        final profile = await apiClient.getMe();
        _userProfile = profile;
        _isAuthenticated = true;
      }
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_keyToken);
    apiClient.token = null;
    _isAuthenticated = false;
    _userProfile = null;
    notifyListeners();
  }
}
