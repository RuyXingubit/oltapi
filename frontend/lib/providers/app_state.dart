import 'package:flutter/material.dart';
import '../core/network/api_client.dart';
import '../models/olt_model.dart';
import '../models/onu_model.dart';
import '../models/pon_policy_model.dart';
import '../models/backup_model.dart';

class AppState extends ChangeNotifier {
  final ApiClient apiClient;

  List<OltModel> _olts = [];
  List<String> _supportedVendors = [];
  OltModel? _selectedOlt;
  List<UnauthorizedOnu> _unauthorizedOnus = [];
  List<ConfiguredOnu> _configuredOnus = [];
  ProvisioningSchemaModel? _provisioningSchema;

  bool _isLoadingOlts = false;
  bool _isLoadingUnauthorized = false;
  bool _isLoadingConfigured = false;
  String? _errorMessage;

  List<OltModel> get olts => _olts;
  List<String> get supportedVendors => _supportedVendors;
  OltModel? get selectedOlt => _selectedOlt;
  List<UnauthorizedOnu> get unauthorizedOnus => _unauthorizedOnus;
  List<ConfiguredOnu> get configuredOnus => _configuredOnus;
  ProvisioningSchemaModel? get provisioningSchema => _provisioningSchema;

  bool get isLoadingOlts => _isLoadingOlts;
  bool get isLoadingUnauthorized => _isLoadingUnauthorized;
  bool get isLoadingConfigured => _isLoadingConfigured;
  String? get errorMessage => _errorMessage;

  AppState({required this.apiClient});

  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  void selectOlt(OltModel? olt) {
    _selectedOlt = olt;
    notifyListeners();
    if (olt != null) {
      loadUnauthorizedOnus();
      loadProvisioningSchema();
    } else {
      _unauthorizedOnus = [];
      notifyListeners();
    }
  }

  Future<void> loadOlts() async {
    _isLoadingOlts = true;
    _errorMessage = null;
    notifyListeners();

    try {
      if (_supportedVendors.isEmpty) {
        _supportedVendors = await apiClient.getSupportedVendors();
      }
      _olts = await apiClient.getOlts();
      if (_olts.isNotEmpty) {
        if (_selectedOlt == null || !_olts.any((o) => o.id == _selectedOlt!.id)) {
          _selectedOlt = _olts.first;
        } else {
          // Atualiza a referência da OLT selecionada
          _selectedOlt = _olts.firstWhere((o) => o.id == _selectedOlt!.id);
        }
      } else {
        _selectedOlt = null;
      }
    } catch (e) {
      _errorMessage = 'Falha ao carregar OLTs: $e';
    } finally {
      _isLoadingOlts = false;
      notifyListeners();
      if (_selectedOlt != null) {
        loadUnauthorizedOnus();
      }
    }
  }

  Future<OltModel?> createOlt(Map<String, dynamic> data) async {
    try {
      final newOlt = await apiClient.createOlt(data);
      await loadOlts();
      return newOlt;
    } catch (e) {
      _errorMessage = 'Falha ao criar OLT: $e';
      notifyListeners();
      return null;
    }
  }

  Future<OltModel?> updateOlt(String oltId, Map<String, dynamic> data) async {
    try {
      final updatedOlt = await apiClient.updateOlt(oltId, data);
      await loadOlts();
      return updatedOlt;
    } catch (e) {
      _errorMessage = 'Falha ao atualizar OLT: $e';
      notifyListeners();
      return null;
    }
  }

  Future<bool> deleteOlt(String oltId) async {
    try {
      await apiClient.deleteOlt(oltId);
      if (_selectedOlt?.id == oltId) _selectedOlt = null;
      await loadOlts();
      return true;
    } catch (e) {
      _errorMessage = 'Falha ao remover OLT: $e';
      notifyListeners();
      return false;
    }
  }

  Future<void> loadUnauthorizedOnus() async {
    if (_selectedOlt == null) {
      _unauthorizedOnus = [];
      notifyListeners();
      return;
    }

    _isLoadingUnauthorized = true;
    notifyListeners();

    try {
      _unauthorizedOnus = await apiClient.getUnauthorizedOnus(_selectedOlt!.id);
    } catch (e) {
      _errorMessage = 'Falha ao buscar ONUs pendentes: $e';
      _unauthorizedOnus = [];
    } finally {
      _isLoadingUnauthorized = false;
      notifyListeners();
    }
  }

  Future<void> loadConfiguredOnus() async {
    _isLoadingConfigured = true;
    notifyListeners();

    try {
      _configuredOnus = await apiClient.getConfiguredOnus();
    } catch (e) {
      _errorMessage = 'Falha ao listar inventário de ONUs: $e';
      _configuredOnus = [];
    } finally {
      _isLoadingConfigured = false;
      notifyListeners();
    }
  }

  Future<void> refreshAll() async {
    await loadOlts();
    await Future.wait([
      if (_selectedOlt != null) loadUnauthorizedOnus(),
      if (_selectedOlt != null) loadProvisioningSchema(),
      loadConfiguredOnus(),
    ]);
  }

  // Provisioning
  Future<void> loadProvisioningSchema() async {
    if (_selectedOlt == null) return;
    try {
      _provisioningSchema = await apiClient.getProvisioningSchema(_selectedOlt!.id);
      notifyListeners();
    } catch (e) {
      _errorMessage = 'Falha ao buscar esquema de provisionamento: $e';
      notifyListeners();
    }
  }

  Future<bool> provisionOnu({
    required String port,
    required String serial,
    required int vlan,
    required String profile,
    required String description,
  }) async {
    if (_selectedOlt == null) return false;
    try {
      final req = ProvisionRequestModel(
        port: port,
        serial: serial,
        vlan: vlan,
        profile: profile,
        description: description,
      );
      await apiClient.provisionOnu(_selectedOlt!.id, req);
      await Future.wait([
        loadUnauthorizedOnus(),
        loadConfiguredOnus(),
      ]);
      return true;
    } catch (e) {
      _errorMessage = 'Erro ao autorizar ONU: $e';
      notifyListeners();
      return false;
    }
  }

  // Actions
  Future<bool> rebootOnu(String oltId, String serial) async {
    try {
      await apiClient.rebootOnu(oltId, serial);
      return true;
    } catch (e) {
      _errorMessage = 'Erro ao reiniciar ONU: $e';
      notifyListeners();
      return false;
    }
  }

  Future<bool> suspendOnu(String oltId, String serial) async {
    try {
      await apiClient.suspendOnu(oltId, serial);
      await loadConfiguredOnus();
      return true;
    } catch (e) {
      _errorMessage = 'Erro ao suspender ONU: $e';
      notifyListeners();
      return false;
    }
  }

  Future<bool> resumeOnu(String oltId, String serial) async {
    try {
      await apiClient.resumeOnu(oltId, serial);
      await loadConfiguredOnus();
      return true;
    } catch (e) {
      _errorMessage = 'Erro ao reativar ONU: $e';
      notifyListeners();
      return false;
    }
  }

  Future<bool> deprovisionOnu(String oltId, String serial) async {
    try {
      await apiClient.deprovisionOnu(oltId, serial);
      await loadConfiguredOnus();
      return true;
    } catch (e) {
      _errorMessage = 'Erro ao excluir ONU: $e';
      notifyListeners();
      return false;
    }
  }

  Future<BackupModel?> triggerBackup(String oltId) async {
    try {
      final backup = await apiClient.triggerOltBackup(oltId);
      return backup;
    } catch (e) {
      _errorMessage = 'Erro ao gerar backup: $e';
      notifyListeners();
      return null;
    }
  }
}
