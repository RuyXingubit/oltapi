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
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'].toString())
          : null,
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

  OnuDiagnostics({
    required this.port,
    required this.onuId,
    required this.serial,
    required this.status,
    this.rxPowerDbm,
    this.txPowerDbm,
    this.oltRxPowerDbm,
    this.vlan,
  });

  factory OnuDiagnostics.fromJson(Map<String, dynamic> json) {
    return OnuDiagnostics(
      port: json['port']?.toString() ?? '',
      onuId: (json['onu_id'] as num?)?.toInt() ?? 0,
      serial: json['serial']?.toString() ?? '',
      status: json['status']?.toString() ?? 'unknown',
      rxPowerDbm: (json['rx_power_dbm'] as num?)?.toDouble(),
      txPowerDbm: (json['tx_power_dbm'] as num?)?.toDouble(),
      oltRxPowerDbm: (json['olt_rx_power_dbm'] as num?)?.toDouble(),
      vlan: (json['vlan'] as num?)?.toInt(),
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
