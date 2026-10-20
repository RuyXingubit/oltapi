class UnauthorizedOnu {
  final String port;
  final String serial;
  final String? model;
  final DateTime? detectedAt;

  UnauthorizedOnu({
    required this.port,
    required this.serial,
    this.model,
    this.detectedAt,
  });

  factory UnauthorizedOnu.fromJson(Map<String, dynamic> json) {
    return UnauthorizedOnu(
      port: json['port']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      model: json['model']?.toString(),
      detectedAt: json['detected_at'] != null
          ? DateTime.tryParse(json['detected_at'].toString())
          : null,
    );
  }
}

class ConfiguredOnu {
  final String id;
  final String serial;
  final String? contractId;
  final String? subscriberName;
  final String contractStatus;
  final int? vlan;
  final String profile;
  final String? description;
  final String? currentOltId;
  final String? currentPort;
  final int? currentOnuId;
  final String? circuitId;
  final double? lastRxPowerDbm;
  final double? lastTxPowerDbm;
  final double? lastOltRxPowerDbm;
  final String? lastDownCause;
  final DateTime? lastDownTime;
  final String? zoneId;
  final String? odbId;
  final int? odbSplitterPort;
  final DateTime? updatedAt;

  ConfiguredOnu({
    required this.id,
    required this.serial,
    this.contractId,
    this.subscriberName,
    required this.contractStatus,
    this.vlan,
    required this.profile,
    this.description,
    this.currentOltId,
    this.currentPort,
    this.currentOnuId,
    this.circuitId,
    this.lastRxPowerDbm,
    this.lastTxPowerDbm,
    this.lastOltRxPowerDbm,
    this.lastDownCause,
    this.lastDownTime,
    this.zoneId,
    this.odbId,
    this.odbSplitterPort,
    this.updatedAt,
  });

  factory ConfiguredOnu.fromJson(Map<String, dynamic> json) {
    return ConfiguredOnu(
      id: json['id']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      contractId: json['contract_id']?.toString(),
      subscriberName: json['subscriber_name']?.toString(),
      contractStatus: json['contract_status']?.toString() ?? 'ACTIVE',
      vlan: (json['vlan'] as num?)?.toInt(),
      profile: json['profile']?.toString() ?? 'DEFAULT',
      description: json['description']?.toString(),
      currentOltId: json['current_olt_id']?.toString(),
      currentPort: json['current_port']?.toString(),
      currentOnuId: (json['current_onu_id'] as num?)?.toInt(),
      circuitId: json['circuit_id']?.toString(),
      lastRxPowerDbm: (json['last_rx_power_dbm'] as num?)?.toDouble(),
      lastTxPowerDbm: (json['last_tx_power_dbm'] as num?)?.toDouble(),
      lastOltRxPowerDbm: (json['last_olt_rx_power_dbm'] as num?)?.toDouble(),
      lastDownCause: json['last_down_cause']?.toString(),
      lastDownTime: json['last_down_time'] != null
          ? DateTime.tryParse(json['last_down_time'].toString())
          : null,
      zoneId: json['zone_id']?.toString(),
      odbId: json['odb_id']?.toString(),
      odbSplitterPort: (json['odb_splitter_port'] as num?)?.toInt(),
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString())
          : null,
    );
  }
}

class OnuMacEntryModel {
  final String macAddress;
  final int? vlan;
  final String? servicePortOrEth;
  final String? type;

  OnuMacEntryModel({
    required this.macAddress,
    this.vlan,
    this.servicePortOrEth,
    this.type,
  });

  factory OnuMacEntryModel.fromJson(Map<String, dynamic> json) {
    return OnuMacEntryModel(
      macAddress: (json['mac_address'] ?? json['mac'])?.toString() ?? '',
      vlan: (json['vlan'] as num?)?.toInt(),
      servicePortOrEth:
          (json['port'] ?? json['service_port_or_eth'])?.toString(),
      type: json['type']?.toString() ??
          (json['is_dynamic'] == false ? 'static' : 'dynamic'),
    );
  }
}

class OnuDiagnostics {
  final String port;
  final int onuId;
  final String serial;
  final String status;
  final double? rxPowerDbm;
  final double? txPowerDbm;
  final double? oltRxPowerDbm;
  final int? vlan;
  final String? lastDownCause;
  final String? lastDownTime;
  final List<OnuMacEntryModel> macTable;

  OnuDiagnostics({
    required this.port,
    required this.onuId,
    required this.serial,
    required this.status,
    this.rxPowerDbm,
    this.txPowerDbm,
    this.oltRxPowerDbm,
    this.vlan,
    this.lastDownCause,
    this.lastDownTime,
    this.macTable = const [],
  });

  factory OnuDiagnostics.fromJson(Map<String, dynamic> json) {
    final rawMacs = json['mac_table'];
    return OnuDiagnostics(
      port: json['port']?.toString() ?? '',
      onuId: (json['onu_id'] as num?)?.toInt() ?? 0,
      serial: json['serial']?.toString() ?? '',
      status: json['status']?.toString() ?? 'unknown',
      rxPowerDbm: (json['rx_power_dbm'] as num?)?.toDouble(),
      txPowerDbm: (json['tx_power_dbm'] as num?)?.toDouble(),
      oltRxPowerDbm: (json['olt_rx_power_dbm'] as num?)?.toDouble(),
      vlan: (json['vlan'] as num?)?.toInt(),
      lastDownCause: json['last_down_cause']?.toString(),
      lastDownTime: json['last_down_time']?.toString(),
      macTable: rawMacs is List
          ? rawMacs
              .whereType<Map<String, dynamic>>()
              .map((e) => OnuMacEntryModel.fromJson(e))
              .toList()
          : const [],
    );
  }
}

class ProvisionRequestModel {
  final String port;
  final String serial;
  final int vlan;
  final String profile;
  final String description;
  final String onuModel;
  final String mode;

  ProvisionRequestModel({
    required this.port,
    required this.serial,
    required this.vlan,
    this.profile = 'DEFAULT',
    this.description = 'Cliente',
    this.onuModel = 'auto',
    this.mode = 'bridge',
  });

  Map<String, dynamic> toJson() {
    return {
      'port': port,
      'serial': serial,
      'vlan': vlan,
      'profile': profile,
      'description': description,
      'onu_model': onuModel,
      'mode': mode,
    };
  }
}

class OnuActionResponse {
  final bool success;
  final String action;
  final String serial;
  final String message;

  OnuActionResponse({
    required this.success,
    required this.action,
    required this.serial,
    required this.message,
  });

  factory OnuActionResponse.fromJson(Map<String, dynamic> json) {
    return OnuActionResponse(
      success: json['success'] == true,
      action: json['action']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      message: json['message']?.toString() ?? '',
    );
  }
}

// =========================================================================
// FASE 2: Telemetria Óptica Histórica & Radar de Degradação
// =========================================================================

class OpticalTelemetrySampleModel {
  final String id;
  final String serial;
  final String oltId;
  final String port;
  final int onuId;
  final double? rxPowerDbm;
  final double? txPowerDbm;
  final double? oltRxPowerDbm;
  final String status;
  final String? lastDownCause;
  final DateTime collectedAt;

  OpticalTelemetrySampleModel({
    required this.id,
    required this.serial,
    required this.oltId,
    required this.port,
    required this.onuId,
    this.rxPowerDbm,
    this.txPowerDbm,
    this.oltRxPowerDbm,
    required this.status,
    this.lastDownCause,
    required this.collectedAt,
  });

  factory OpticalTelemetrySampleModel.fromJson(Map<String, dynamic> json) {
    return OpticalTelemetrySampleModel(
      id: json['id']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      oltId: json['olt_id']?.toString() ?? '',
      port: json['port']?.toString() ?? '',
      onuId: (json['onu_id'] as num?)?.toInt() ?? 0,
      rxPowerDbm: (json['rx_power_dbm'] as num?)?.toDouble(),
      txPowerDbm: (json['tx_power_dbm'] as num?)?.toDouble(),
      oltRxPowerDbm: (json['olt_rx_power_dbm'] as num?)?.toDouble(),
      status: json['status']?.toString() ?? 'unknown',
      lastDownCause: json['last_down_cause']?.toString(),
      collectedAt: DateTime.tryParse(
            (json['recorded_at'] ?? json['collected_at'])?.toString() ?? '',
          ) ??
          DateTime.now(),
    );
  }
}

class OpticalTelemetryHistoryModel {
  final String serial;
  final double? currentRxPowerDbm;
  final double? baselineRxPowerDbm;
  final double? minRxPowerDbm;
  final double? maxRxPowerDbm;
  final double? avgRxPowerDbm;
  final double? driftDb;
  final bool isDegraded;
  final List<String> degradationReasons;
  final List<OpticalTelemetrySampleModel> samples;

  OpticalTelemetryHistoryModel({
    required this.serial,
    this.currentRxPowerDbm,
    this.baselineRxPowerDbm,
    this.minRxPowerDbm,
    this.maxRxPowerDbm,
    this.avgRxPowerDbm,
    this.driftDb,
    required this.isDegraded,
    this.degradationReasons = const [],
    required this.samples,
  });

  factory OpticalTelemetryHistoryModel.fromJson(Map<String, dynamic> json) {
    final rawSamples = json['samples'];
    final parsedSamples = rawSamples is List
        ? rawSamples
            .whereType<Map<String, dynamic>>()
            .map((e) => OpticalTelemetrySampleModel.fromJson(e))
            .toList()
        : const <OpticalTelemetrySampleModel>[];

    final rxValues = parsedSamples
        .map((s) => s.rxPowerDbm)
        .whereType<double>()
        .toList();

    double? computedMin;
    double? computedMax;
    double? computedAvg;
    if (rxValues.isNotEmpty) {
      computedMin = rxValues.reduce((a, b) => a < b ? a : b);
      computedMax = rxValues.reduce((a, b) => a > b ? a : b);
      computedAvg = rxValues.reduce((a, b) => a + b) / rxValues.length;
    }

    final rawReasons = json['degradation_reasons'];
    final reasonsList = rawReasons is List
        ? rawReasons.map((e) => e.toString()).toList()
        : const <String>[];

    final baseline = (json['baseline_rx_power_dbm'] as num?)?.toDouble();

    return OpticalTelemetryHistoryModel(
      serial: json['serial']?.toString() ?? '',
      currentRxPowerDbm:
          ((json['current_rx_power_dbm'] ?? json['latest_rx_dbm']) as num?)
              ?.toDouble(),
      baselineRxPowerDbm: baseline,
      minRxPowerDbm:
          (json['min_rx_power_dbm'] as num?)?.toDouble() ?? computedMin,
      maxRxPowerDbm:
          (json['max_rx_power_dbm'] as num?)?.toDouble() ?? computedMax,
      avgRxPowerDbm: (json['avg_rx_power_dbm'] as num?)?.toDouble() ??
          baseline ??
          computedAvg,
      driftDb: (json['drift_db'] as num?)?.toDouble(),
      isDegraded: json['is_degraded'] == true,
      degradationReasons: reasonsList,
      samples: parsedSamples,
    );
  }
}

class DegradedOnuItemModel {
  final String serial;
  final String? subscriberName;
  final String? oltId;
  final String? port;
  final int? onuId;
  final double? lastRxPowerDbm;
  final double? baselineRxPowerDbm;
  final double? driftDb;
  final String? lastDownCause;
  final String severity;
  final List<String> reasons;
  final String reason;

  DegradedOnuItemModel({
    required this.serial,
    this.subscriberName,
    this.oltId,
    this.port,
    this.onuId,
    this.lastRxPowerDbm,
    this.baselineRxPowerDbm,
    this.driftDb,
    this.lastDownCause,
    this.severity = 'warning',
    this.reasons = const [],
    required this.reason,
  });

  factory DegradedOnuItemModel.fromJson(Map<String, dynamic> json) {
    final rawReasons = json['reasons'];
    final reasonsList = rawReasons is List
        ? rawReasons.map((e) => e.toString()).toList()
        : const <String>[];
    final combinedReason = reasonsList.isNotEmpty
        ? reasonsList.join(' • ')
        : (json['reason']?.toString() ?? '');

    return DegradedOnuItemModel(
      serial: json['serial']?.toString() ?? '',
      subscriberName: json['subscriber_name']?.toString(),
      oltId: json['olt_id']?.toString(),
      port: json['port']?.toString(),
      onuId: (json['onu_id'] as num?)?.toInt(),
      lastRxPowerDbm:
          ((json['rx_power_dbm'] ?? json['last_rx_power_dbm']) as num?)
              ?.toDouble(),
      baselineRxPowerDbm: (json['baseline_rx_power_dbm'] as num?)?.toDouble(),
      driftDb: (json['drift_db'] as num?)?.toDouble(),
      lastDownCause: json['last_down_cause']?.toString(),
      severity: json['severity']?.toString() ?? 'warning',
      reasons: reasonsList,
      reason: combinedReason,
    );
  }
}

// =========================================================================
// FASE 3: Presets Universais, Pré-Provisionamento & Ações em Lote
// =========================================================================

class ProvisioningPresetModel {
  final String id;
  final String name;
  final String? description;
  final int defaultVlan;
  final String defaultProfile;
  final String srvProfile;
  final String defaultMode;
  final String onuTypePattern;
  final String? tenantId;
  final bool isDefault;
  final DateTime? createdAt;

  ProvisioningPresetModel({
    required this.id,
    required this.name,
    this.description,
    required this.defaultVlan,
    required this.defaultProfile,
    this.srvProfile = 'DEFAULT',
    required this.defaultMode,
    required this.onuTypePattern,
    this.tenantId,
    required this.isDefault,
    this.createdAt,
  });

  factory ProvisioningPresetModel.fromJson(Map<String, dynamic> json) {
    final lineProf =
        (json['line_profile'] ?? json['default_profile'])?.toString() ??
            'DEFAULT';
    return ProvisioningPresetModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      description: json['description']?.toString(),
      defaultVlan:
          ((json['vlan'] ?? json['default_vlan']) as num?)?.toInt() ?? 100,
      defaultProfile: lineProf,
      srvProfile: json['srv_profile']?.toString() ?? lineProf,
      defaultMode:
          (json['mode'] ?? json['default_mode'])?.toString() ?? 'transparent',
      onuTypePattern: json['onu_type_pattern']?.toString() ?? '*',
      tenantId: json['tenant_id']?.toString(),
      isDefault: json['is_default'] == true,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }
}

class BatchOnuActionResultItemModel {
  final String serial;
  final bool success;
  final String message;

  BatchOnuActionResultItemModel({
    required this.serial,
    required this.success,
    required this.message,
  });

  factory BatchOnuActionResultItemModel.fromJson(Map<String, dynamic> json) {
    return BatchOnuActionResultItemModel(
      serial: json['serial']?.toString() ?? '',
      success: json['success'] == true,
      message: json['message']?.toString() ?? '',
    );
  }
}

class BatchOnuActionResponseModel {
  final String action;
  final int totalRequested;
  final int succeeded;
  final int failed;
  final List<BatchOnuActionResultItemModel> results;

  BatchOnuActionResponseModel({
    required this.action,
    required this.totalRequested,
    required this.succeeded,
    required this.failed,
    required this.results,
  });

  factory BatchOnuActionResponseModel.fromJson(Map<String, dynamic> json) {
    final rawResults = json['results'];
    return BatchOnuActionResponseModel(
      action: json['action']?.toString() ?? '',
      totalRequested:
          ((json['total'] ?? json['total_requested']) as num?)?.toInt() ?? 0,
      succeeded: (json['succeeded'] as num?)?.toInt() ?? 0,
      failed: (json['failed'] as num?)?.toInt() ?? 0,
      results: rawResults is List
          ? rawResults
              .whereType<Map<String, dynamic>>()
              .map((e) => BatchOnuActionResultItemModel.fromJson(e))
              .toList()
          : const [],
    );
  }
}

// =========================================================================
// FASE 4: Topologia Passiva FTTH (Zonas, CTOs/ODBs & Mapa de Saúde)
// =========================================================================

class NetworkZoneModel {
  final String id;
  final String name;
  final String? sector;
  final String? city;
  final String? description;
  final int odbCount;
  final int onuCount;
  final DateTime? createdAt;

  NetworkZoneModel({
    required this.id,
    required this.name,
    this.sector,
    this.city,
    this.description,
    this.odbCount = 0,
    this.onuCount = 0,
    this.createdAt,
  });

  factory NetworkZoneModel.fromJson(Map<String, dynamic> json) {
    return NetworkZoneModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      sector: json['sector']?.toString(),
      city: json['city']?.toString(),
      description: json['description']?.toString(),
      odbCount: (json['odb_count'] as num?)?.toInt() ?? 0,
      onuCount: (json['onu_count'] as num?)?.toInt() ?? 0,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }
}

class OpticalDistributionBoxModel {
  final String id;
  final String name;
  final String code;
  final String? zoneId;
  final String? oltId;
  final String? ponPort;
  final int splitterCapacity;
  final String splitterRatio;
  final double? latitude;
  final double? longitude;
  final String? address;
  final int usedPortsCount;
  final int availablePorts;
  final List<int> occupiedSplitterPorts;

  OpticalDistributionBoxModel({
    required this.id,
    required this.name,
    required this.code,
    this.zoneId,
    this.oltId,
    this.ponPort,
    this.splitterCapacity = 16,
    required this.splitterRatio,
    this.latitude,
    this.longitude,
    this.address,
    this.usedPortsCount = 0,
    this.availablePorts = 16,
    this.occupiedSplitterPorts = const [],
  });

  factory OpticalDistributionBoxModel.fromJson(Map<String, dynamic> json) {
    final cap = (json['splitter_capacity'] as num?)?.toInt() ?? 16;
    final used =
        ((json['used_ports'] ?? json['used_ports_count']) as num?)?.toInt() ??
            0;
    final rawOccupied = json['occupied_splitter_ports'];
    return OpticalDistributionBoxModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      code: json['code']?.toString() ?? '',
      zoneId: json['zone_id']?.toString(),
      oltId: json['olt_id']?.toString(),
      ponPort: json['pon_port']?.toString(),
      splitterCapacity: cap,
      splitterRatio: json['splitter_ratio']?.toString() ?? '1:$cap',
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      address: json['address']?.toString(),
      usedPortsCount: used,
      availablePorts:
          (json['available_ports'] as num?)?.toInt() ?? (cap - used),
      occupiedSplitterPorts: rawOccupied is List
          ? rawOccupied.whereType<num>().map((e) => e.toInt()).toList()
          : const [],
    );
  }
}

class OdbHealthNodeModel {
  final String odbId;
  final String name;
  final String code;
  final String? zoneId;
  final String? zoneName;
  final String? oltId;
  final String? ponPort;
  final int splitterCapacity;
  final String splitterRatio;
  final double? latitude;
  final double? longitude;
  final int totalOnus;
  final int onlineOnus;
  final int dyingGaspOnus;
  final int losOnus;
  final int degradedOnus;
  final String healthStatus;
  final String diagnosisSummary;

  OdbHealthNodeModel({
    required this.odbId,
    required this.name,
    required this.code,
    this.zoneId,
    this.zoneName,
    this.oltId,
    this.ponPort,
    this.splitterCapacity = 16,
    required this.splitterRatio,
    this.latitude,
    this.longitude,
    required this.totalOnus,
    required this.onlineOnus,
    required this.dyingGaspOnus,
    required this.losOnus,
    required this.degradedOnus,
    required this.healthStatus,
    this.diagnosisSummary = 'Operação normal',
  });

  factory OdbHealthNodeModel.fromJson(Map<String, dynamic> json) {
    final cap = (json['splitter_capacity'] as num?)?.toInt() ?? 16;
    return OdbHealthNodeModel(
      odbId: json['odb_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      code: json['code']?.toString() ?? '',
      zoneId: json['zone_id']?.toString(),
      zoneName: json['zone_name']?.toString(),
      oltId: json['olt_id']?.toString(),
      ponPort: json['pon_port']?.toString(),
      splitterCapacity: cap,
      splitterRatio: json['splitter_ratio']?.toString() ?? '1:$cap',
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      totalOnus: (json['total_onus'] as num?)?.toInt() ?? 0,
      onlineOnus: (json['online_onus'] as num?)?.toInt() ?? 0,
      dyingGaspOnus: (json['dying_gasp_onus'] as num?)?.toInt() ?? 0,
      losOnus: (json['los_onus'] as num?)?.toInt() ?? 0,
      degradedOnus: (json['degraded_onus'] as num?)?.toInt() ?? 0,
      healthStatus: json['health_status']?.toString() ?? 'healthy',
      diagnosisSummary: json['diagnosis_summary']?.toString() ?? 'Operação normal',
    );
  }
}

class TopologyHealthMapModel {
  final int totalZones;
  final int totalOdbs;
  final int healthyOdbs;
  final int degradedOdbs;
  final int powerOutageOdbs;
  final int fiberCutOdbs;
  final List<OdbHealthNodeModel> nodes;

  TopologyHealthMapModel({
    required this.totalZones,
    required this.totalOdbs,
    required this.healthyOdbs,
    required this.degradedOdbs,
    required this.powerOutageOdbs,
    required this.fiberCutOdbs,
    required this.nodes,
  });

  factory TopologyHealthMapModel.fromJson(Map<String, dynamic> json) {
    final rawNodes = json['nodes'] ?? json['odbs'];
    return TopologyHealthMapModel(
      totalZones: (json['total_zones'] as num?)?.toInt() ?? 0,
      totalOdbs: (json['total_odbs'] as num?)?.toInt() ?? 0,
      healthyOdbs: (json['healthy_odbs'] as num?)?.toInt() ?? 0,
      degradedOdbs: (json['degraded_odbs'] as num?)?.toInt() ?? 0,
      powerOutageOdbs: (json['power_outage_odbs'] as num?)?.toInt() ?? 0,
      fiberCutOdbs: (json['fiber_cut_odbs'] as num?)?.toInt() ?? 0,
      nodes: rawNodes is List
          ? rawNodes
              .whereType<Map<String, dynamic>>()
              .map((e) => OdbHealthNodeModel.fromJson(e))
              .toList()
          : const [],
    );
  }
}

// =========================================================================
// FASE 5: Integração ACS TR-069 / CWMP (GenieACS)
// =========================================================================

class AcsServerConfigModel {
  final String id;
  final String name;
  final String baseUrl;
  final String? username;
  final bool hasPassword;
  final String cwmpUrl;
  final int periodicInformInterval;
  final bool isActive;
  final DateTime? createdAt;

  AcsServerConfigModel({
    required this.id,
    required this.name,
    required this.baseUrl,
    this.username,
    required this.hasPassword,
    required this.cwmpUrl,
    required this.periodicInformInterval,
    required this.isActive,
    this.createdAt,
  });

  factory AcsServerConfigModel.fromJson(Map<String, dynamic> json) {
    return AcsServerConfigModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      baseUrl: (json['nbi_url'] ?? json['base_url'])?.toString() ?? '',
      username: json['username']?.toString(),
      hasPassword: json['has_password'] == true,
      cwmpUrl: (json['cwmp_inform_url'] ?? json['cwmp_url'])?.toString() ?? '',
      periodicInformInterval:
          (json['periodic_inform_interval'] as num?)?.toInt() ?? 300,
      isActive: json['is_active'] != false,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }
}

class Tr069DeviceSummaryModel {
  final String serial;
  final String? acsDeviceId;
  final bool onlineInAcs;
  final String? acsServerName;
  final String? lastInform;
  final String? firmwareVersion;
  final String? hardwareVersion;
  final String? wanMode;
  final String? wanIp;
  final String? pppoeUsername;
  final String? ssid24g;
  final String? ssid5g;
  final int connectedHostsCount;
  final String? message;

  Tr069DeviceSummaryModel({
    required this.serial,
    this.acsDeviceId,
    required this.onlineInAcs,
    this.acsServerName,
    this.lastInform,
    this.firmwareVersion,
    this.hardwareVersion,
    this.wanMode,
    this.wanIp,
    this.pppoeUsername,
    this.ssid24g,
    this.ssid5g,
    this.connectedHostsCount = 0,
    this.message,
  });

  factory Tr069DeviceSummaryModel.fromJson(Map<String, dynamic> json) {
    return Tr069DeviceSummaryModel(
      serial: json['serial']?.toString() ?? '',
      acsDeviceId: json['acs_device_id']?.toString(),
      onlineInAcs:
          json['registered_in_acs'] == true || json['online_in_acs'] == true,
      acsServerName: json['acs_server_name']?.toString(),
      lastInform: json['last_inform']?.toString(),
      firmwareVersion:
          (json['software_version'] ?? json['firmware_version'])?.toString(),
      hardwareVersion: json['hardware_version']?.toString(),
      wanMode: json['wan_mode']?.toString(),
      wanIp: json['wan_ip']?.toString(),
      pppoeUsername: json['pppoe_username']?.toString(),
      ssid24g: json['ssid_24g']?.toString(),
      ssid5g: json['ssid_5g']?.toString(),
      connectedHostsCount:
          (json['connected_hosts_count'] as num?)?.toInt() ?? 0,
      message: json['message']?.toString(),
    );
  }
}

