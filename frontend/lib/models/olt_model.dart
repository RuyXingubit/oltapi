class OltModel {
  final String id;
  final String name;
  final String vendor;
  final String model;
  final String host;
  final int port;
  final String protocol;
  final String? snmpCommunity;
  final int? snmpPort;
  final String? status;
  final String? connectionMessage;
  final DateTime? createdAt;

  OltModel({
    required this.id,
    required this.name,
    required this.vendor,
    required this.model,
    required this.host,
    required this.port,
    required this.protocol,
    this.snmpCommunity,
    this.snmpPort,
    this.status,
    this.connectionMessage,
    this.createdAt,
  });

  factory OltModel.fromJson(Map<String, dynamic> json) {
    return OltModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      vendor: json['vendor']?.toString() ?? '',
      model: json['model']?.toString() ?? '',
      host: json['host']?.toString() ?? '',
      port: (json['port'] as num?)?.toInt() ?? 23,
      protocol: json['protocol']?.toString() ?? 'telnet',
      snmpCommunity: json['snmp_community']?.toString(),
      snmpPort: (json['snmp_port'] as num?)?.toInt(),
      status: json['status']?.toString() ?? 'online',
      connectionMessage: json['connection_message']?.toString(),
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'vendor': vendor,
      'model': model,
      'host': host,
      'port': port,
      'protocol': protocol,
      'snmp_community': snmpCommunity,
      'snmp_port': snmpPort,
      'status': status,
      'connection_message': connectionMessage,
      'created_at': createdAt?.toIso8601String(),
    };
  }
}

class ConnectionTestResult {
  final String oltId;
  final String host;
  final int port;
  final bool reachable;
  final double? latencyMs;
  final String message;

  ConnectionTestResult({
    required this.oltId,
    required this.host,
    required this.port,
    required this.reachable,
    this.latencyMs,
    required this.message,
  });

  factory ConnectionTestResult.fromJson(Map<String, dynamic> json) {
    return ConnectionTestResult(
      oltId: json['olt_id']?.toString() ?? '',
      host: json['host']?.toString() ?? '',
      port: (json['port'] as num?)?.toInt() ?? 0,
      reachable: json['reachable'] == true,
      latencyMs: (json['latency_ms'] as num?)?.toDouble(),
      message: json['message']?.toString() ?? '',
    );
  }
}

class OltPortStatusItem {
  final String portId;
  final String portType;
  final String adminState;
  final String operStatus;
  final int onuCount;
  final int onuCapacity;
  final String? speedDuplex;
  final String? details;

  OltPortStatusItem({
    required this.portId,
    required this.portType,
    this.adminState = 'enabled',
    required this.operStatus,
    this.onuCount = 0,
    this.onuCapacity = 128,
    this.speedDuplex,
    this.details,
  });

  factory OltPortStatusItem.fromJson(Map<String, dynamic> json) {
    return OltPortStatusItem(
      portId: json['port_id']?.toString() ?? '',
      portType: json['port_type']?.toString() ?? 'gpon',
      adminState: json['admin_state']?.toString() ?? 'enabled',
      operStatus: json['oper_status']?.toString() ?? 'down',
      onuCount: (json['onu_count'] as num?)?.toInt() ?? 0,
      onuCapacity: (json['onu_capacity'] as num?)?.toInt() ?? 128,
      speedDuplex: json['speed_duplex']?.toString(),
      details: json['details']?.toString(),
    );
  }
}

class OltXRayModel {
  final String oltId;
  final String oltName;
  final String vendor;
  final String model;
  final String host;
  final int uptimeSeconds;
  final String uptimeHuman;
  final String? firmwareVersion;
  final double? cpuUsagePct;
  final double? memoryUsagePct;
  final double? temperatureCelsius;
  final List<OltPortStatusItem> ports;
  final int totalOnusDetected;
  final int totalVlansDetected;
  final List<int> vlans;
  final String runningConfigPreview;
  final bool isOnboarded;
  final String? baselineBackupId;
  final bool snmpActive;
  final String snmpStatus;
  final String? snmpCommunity;
  final String? snmpMessage;

  OltXRayModel({
    required this.oltId,
    required this.oltName,
    required this.vendor,
    required this.model,
    required this.host,
    required this.uptimeSeconds,
    required this.uptimeHuman,
    this.firmwareVersion,
    this.cpuUsagePct,
    this.memoryUsagePct,
    this.temperatureCelsius,
    this.ports = const [],
    this.totalOnusDetected = 0,
    this.totalVlansDetected = 0,
    this.vlans = const [],
    this.runningConfigPreview = '',
    this.isOnboarded = false,
    this.baselineBackupId,
    this.snmpActive = false,
    this.snmpStatus = 'inactive',
    this.snmpCommunity,
    this.snmpMessage,
  });

  factory OltXRayModel.fromJson(Map<String, dynamic> json) {
    return OltXRayModel(
      oltId: json['olt_id']?.toString() ?? '',
      oltName: json['olt_name']?.toString() ?? '',
      vendor: json['vendor']?.toString() ?? '',
      model: json['model']?.toString() ?? '',
      host: json['host']?.toString() ?? '',
      uptimeSeconds: (json['uptime_seconds'] as num?)?.toInt() ?? 0,
      uptimeHuman: json['uptime_human']?.toString() ?? 'N/D',
      firmwareVersion: json['firmware_version']?.toString(),
      cpuUsagePct: (json['cpu_usage_pct'] as num?)?.toDouble(),
      memoryUsagePct: (json['memory_usage_pct'] as num?)?.toDouble(),
      temperatureCelsius: (json['temperature_celsius'] as num?)?.toDouble(),
      ports: (json['ports'] as List?)
              ?.map((p) => OltPortStatusItem.fromJson(p as Map<String, dynamic>))
              .toList() ??
          const [],
      totalOnusDetected: (json['total_onus_detected'] as num?)?.toInt() ?? 0,
      totalVlansDetected: (json['total_vlans_detected'] as num?)?.toInt() ?? 0,
      vlans: (json['vlans'] as List?)?.map((v) => (v as num).toInt()).toList() ?? const [],
      runningConfigPreview: json['running_config_preview']?.toString() ?? '',
      isOnboarded: json['is_onboarded'] == true,
      baselineBackupId: json['baseline_backup_id']?.toString(),
      snmpActive: json['snmp_active'] == true,
      snmpStatus: json['snmp_status']?.toString() ?? 'inactive',
      snmpCommunity: json['snmp_community']?.toString(),
      snmpMessage: json['snmp_message']?.toString(),
    );
  }
}

class SyncOltResultModel {
  final String oltId;
  final String oltName;
  final String baselineBackupId;
  final int totalOnusDiscovered;
  final int newOnusRegistered;
  final int existingOnusUpdated;
  final List<int> vlansDiscovered;
  final double durationMs;
  final String message;

  SyncOltResultModel({
    required this.oltId,
    required this.oltName,
    required this.baselineBackupId,
    this.totalOnusDiscovered = 0,
    this.newOnusRegistered = 0,
    this.existingOnusUpdated = 0,
    this.vlansDiscovered = const [],
    this.durationMs = 0.0,
    this.message = '',
  });

  factory SyncOltResultModel.fromJson(Map<String, dynamic> json) {
    return SyncOltResultModel(
      oltId: json['olt_id']?.toString() ?? '',
      oltName: json['olt_name']?.toString() ?? '',
      baselineBackupId: json['baseline_backup_id']?.toString() ?? '',
      totalOnusDiscovered: (json['total_onus_discovered'] as num?)?.toInt() ?? 0,
      newOnusRegistered: (json['new_onus_registered'] as num?)?.toInt() ?? 0,
      existingOnusUpdated: (json['existing_onus_updated'] as num?)?.toInt() ?? 0,
      vlansDiscovered: (json['vlans_discovered'] as List?)?.map((v) => (v as num).toInt()).toList() ?? const [],
      durationMs: (json['duration_ms'] as num?)?.toDouble() ?? 0.0,
      message: json['message']?.toString() ?? '',
    );
  }
}

class ExistingSviItem {
  final int vlanId;
  final String? name;
  final String? ipCidr;
  final List<String> taggedPorts;
  final List<String> untaggedPorts;

  ExistingSviItem({
    required this.vlanId,
    this.name,
    this.ipCidr,
    this.taggedPorts = const [],
    this.untaggedPorts = const [],
  });

  factory ExistingSviItem.fromJson(Map<String, dynamic> json) {
    return ExistingSviItem(
      vlanId: (json['vlan_id'] as num?)?.toInt() ?? 0,
      name: json['name']?.toString(),
      ipCidr: json['ip_cidr']?.toString(),
      taggedPorts: (json['tagged_ports'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      untaggedPorts: (json['untagged_ports'] as List?)?.map((e) => e.toString()).toList() ?? const [],
    );
  }
}

class OltInspectResultModel {
  final String host;
  final String vendor;
  final String model;
  final String accessScenario;
  final String? auxIp;
  final List<ExistingSviItem> existingSvis;
  final List<int> existingVlans;
  final String? gateway;
  final int totalOnusDetected;
  final String promptMessage;

  OltInspectResultModel({
    required this.host,
    required this.vendor,
    required this.model,
    required this.accessScenario,
    this.auxIp,
    this.existingSvis = const [],
    this.existingVlans = const [],
    this.gateway,
    this.totalOnusDetected = 0,
    required this.promptMessage,
  });

  factory OltInspectResultModel.fromJson(Map<String, dynamic> json) {
    return OltInspectResultModel(
      host: json['host']?.toString() ?? '',
      vendor: json['vendor']?.toString() ?? '',
      model: json['model']?.toString() ?? '',
      accessScenario: json['access_scenario']?.toString() ?? 'inband_active',
      auxIp: json['aux_ip']?.toString(),
      existingSvis: (json['existing_svis'] as List?)
              ?.map((s) => ExistingSviItem.fromJson(s as Map<String, dynamic>))
              .toList() ??
          const [],
      existingVlans: (json['existing_vlans'] as List?)?.map((v) => (v as num).toInt()).toList() ?? const [],
      gateway: json['gateway']?.toString(),
      totalOnusDetected: (json['total_onus_detected'] as num?)?.toInt() ?? 0,
      promptMessage: json['prompt_message']?.toString() ?? '',
    );
  }
}

class OnboardingStepModel {
  final String stepKey;
  final String title;
  final String status;
  final String? details;

  OnboardingStepModel({
    required this.stepKey,
    required this.title,
    required this.status,
    this.details,
  });

  factory OnboardingStepModel.fromJson(Map<String, dynamic> json) {
    return OnboardingStepModel(
      stepKey: json['step_key']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      status: json['status']?.toString() ?? 'pending',
      details: json['details']?.toString(),
    );
  }
}

class OltOnboardResultModel {
  final String oltId;
  final String name;
  final String vendor;
  final String model;
  final String host;
  final int port;
  final String protocol;
  final String baselineBackupId;
  final String snmpCommunity;
  final bool snmpActive;
  final int totalPorts;
  final int activePorts;
  final int totalOnusDetected;
  final int newOnusRegistered;
  final String? firmwareVersion;
  final String? uptimeHuman;
  final List<OnboardingStepModel> steps;
  final String message;

  OltOnboardResultModel({
    required this.oltId,
    required this.name,
    required this.vendor,
    required this.model,
    required this.host,
    required this.port,
    required this.protocol,
    required this.baselineBackupId,
    required this.snmpCommunity,
    required this.snmpActive,
    this.totalPorts = 0,
    this.activePorts = 0,
    this.totalOnusDetected = 0,
    this.newOnusRegistered = 0,
    this.firmwareVersion,
    this.uptimeHuman,
    this.steps = const [],
    required this.message,
  });

  factory OltOnboardResultModel.fromJson(Map<String, dynamic> json) {
    return OltOnboardResultModel(
      oltId: json['olt_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      vendor: json['vendor']?.toString() ?? '',
      model: json['model']?.toString() ?? '',
      host: json['host']?.toString() ?? '',
      port: (json['port'] as num?)?.toInt() ?? 23,
      protocol: json['protocol']?.toString() ?? 'telnet',
      baselineBackupId: json['baseline_backup_id']?.toString() ?? '',
      snmpCommunity: json['snmp_community']?.toString() ?? 'public',
      snmpActive: json['snmp_active'] == true,
      totalPorts: (json['total_ports'] as num?)?.toInt() ?? 0,
      activePorts: (json['active_ports'] as num?)?.toInt() ?? 0,
      totalOnusDetected: (json['total_onus_detected'] as num?)?.toInt() ?? 0,
      newOnusRegistered: (json['new_onus_registered'] as num?)?.toInt() ?? 0,
      firmwareVersion: json['firmware_version']?.toString(),
      uptimeHuman: json['uptime_human']?.toString(),
      steps: (json['steps'] as List?)
              ?.map((s) => OnboardingStepModel.fromJson(s as Map<String, dynamic>))
              .toList() ??
          const [],
      message: json['message']?.toString() ?? '',
    );
  }
}
