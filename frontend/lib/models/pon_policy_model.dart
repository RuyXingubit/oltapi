class PonPolicyModel {
  final String id;
  final String oltId;
  final String port;
  final int defaultVlan;
  final String defaultMode;
  final String? defaultLineProfile;
  final String? defaultSrvProfile;
  final Map<String, dynamic> vendorParameters;
  final bool autoAuthorizeEnabled;

  const PonPolicyModel({
    required this.id,
    required this.oltId,
    required this.port,
    required this.defaultVlan,
    this.defaultMode = 'transparent',
    this.defaultLineProfile,
    this.defaultSrvProfile,
    this.vendorParameters = const {},
    this.autoAuthorizeEnabled = false,
  });

  factory PonPolicyModel.fromJson(Map<String, dynamic> json) {
    return PonPolicyModel(
      id: json['id'] as String? ?? '',
      oltId: json['olt_id'] as String? ?? '',
      port: json['port'] as String? ?? '',
      defaultVlan: json['default_vlan'] as int? ?? 100,
      defaultMode: json['default_mode'] as String? ?? 'transparent',
      defaultLineProfile: json['default_line_profile'] as String?,
      defaultSrvProfile: json['default_srv_profile'] as String?,
      vendorParameters: json['vendor_parameters'] != null
          ? Map<String, dynamic>.from(json['vendor_parameters'] as Map)
          : const {},
      autoAuthorizeEnabled: json['auto_authorize_enabled'] as bool? ?? false,
    );
  }

  String? get defaultProfile => defaultLineProfile ?? defaultSrvProfile;
  bool get autoAuthorize => autoAuthorizeEnabled;

  Map<String, dynamic> toJson() {
    return {
      'port': port,
      'default_vlan': defaultVlan,
      'default_mode': defaultMode,
      'default_line_profile': defaultLineProfile,
      'default_srv_profile': defaultSrvProfile,
      'vendor_parameters': vendorParameters,
      'auto_authorize_enabled': autoAuthorizeEnabled,
    };
  }
}

class AutoProvisionTaskModel {
  final String id;
  final String oltId;
  final String ponPort;
  final int targetVlan;
  final String defaultMode;
  final String? defaultLineProfile;
  final String? defaultSrvProfile;
  final String status;
  final DateTime startsAt;
  final DateTime expiresAt;
  final int remainingSeconds;
  final int provisionedCount;
  final String? createdBy;

  const AutoProvisionTaskModel({
    required this.id,
    required this.oltId,
    required this.ponPort,
    required this.targetVlan,
    this.defaultMode = 'transparent',
    this.defaultLineProfile,
    this.defaultSrvProfile,
    required this.status,
    required this.startsAt,
    required this.expiresAt,
    required this.remainingSeconds,
    this.provisionedCount = 0,
    this.createdBy,
  });

  factory AutoProvisionTaskModel.fromJson(Map<String, dynamic> json) {
    return AutoProvisionTaskModel(
      id: json['id'] as String? ?? '',
      oltId: json['olt_id'] as String? ?? '',
      ponPort: (json['pon_port'] ?? json['port']) as String? ?? 'ALL',
      targetVlan: (json['target_vlan'] ?? json['default_vlan']) as int? ?? 100,
      defaultMode: json['default_mode'] as String? ?? 'transparent',
      defaultLineProfile: (json['default_line_profile'] ?? json['default_profile']) as String?,
      defaultSrvProfile: json['default_srv_profile'] as String?,
      status: json['status'] as String? ?? 'RUNNING',
      startsAt: json['starts_at'] != null
          ? DateTime.parse(json['starts_at'] as String)
          : DateTime.now(),
      expiresAt: json['expires_at'] != null
          ? DateTime.parse(json['expires_at'] as String)
          : DateTime.now(),
      remainingSeconds: json['remaining_seconds'] as int? ?? 0,
      provisionedCount: (json['provisioned_count'] ?? json['onus_provisioned_count']) as int? ?? 0,
      createdBy: json['created_by'] as String?,
    );
  }

  bool get isRunning => status == 'RUNNING' && remainingSeconds > 0;

  String get port => ponPort;
  int get defaultVlan => targetVlan;
  String? get defaultProfile => defaultLineProfile ?? defaultSrvProfile;
  int get onusProvisionedCount => provisionedCount;
  int get durationMinutes {
    final diff = expiresAt.difference(startsAt).inMinutes;
    return diff > 0 ? diff : 120;
  }

  String get formattedRemainingTime {
    if (remainingSeconds <= 0) return 'Expirado';
    final hours = remainingSeconds ~/ 3600;
    final minutes = (remainingSeconds % 3600) ~/ 60;
    final seconds = remainingSeconds % 60;
    if (hours > 0) {
      return '${hours.toString().padLeft(2, '0')}:${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
    }
    return '${minutes.toString().padLeft(2, '0')}:${seconds.toString().padLeft(2, '0')}';
  }
}

class ProvisioningSchemaModel {
  final String oltId;
  final String vendor;
  final String model;
  final List<String> ports;
  final List<Map<String, dynamic>> availableVlans;
  final List<Map<String, dynamic>> availableProfiles;
  final List<Map<String, dynamic>> fields;

  const ProvisioningSchemaModel({
    required this.oltId,
    required this.vendor,
    required this.model,
    required this.ports,
    this.availableVlans = const [],
    this.availableProfiles = const [],
    this.fields = const [],
  });

  factory ProvisioningSchemaModel.fromJson(Map<String, dynamic> json) {
    return ProvisioningSchemaModel(
      oltId: json['olt_id'] as String? ?? '',
      vendor: json['vendor'] as String? ?? '',
      model: json['model'] as String? ?? '',
      ports: (json['ports'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      availableVlans: (json['available_vlans'] as List<dynamic>?)
              ?.map((e) {
                if (e is Map) return Map<String, dynamic>.from(e);
                return {'vlan_id': e, 'name': 'VLAN $e'};
              })
              .toList() ??
          [],
      availableProfiles: (json['available_profiles'] as List<dynamic>?)
              ?.map((e) {
                if (e is Map) return Map<String, dynamic>.from(e);
                return {'name': e.toString(), 'type': 'profile'};
              })
              .toList() ??
          [],
      fields: (json['fields'] as List<dynamic>?)
              ?.map((e) => Map<String, dynamic>.from(e as Map))
              .toList() ??
          [],
    );
  }
}
