class VlanMetricsModel {
  final int vlanId;
  final String? name;
  final String? description;
  final List<String> taggedPorts;
  final List<String> untaggedPorts;
  final int totalProvisionedOnus;
  final int totalActiveOnus;

  VlanMetricsModel({
    required this.vlanId,
    this.name,
    this.description,
    this.taggedPorts = const [],
    this.untaggedPorts = const [],
    this.totalProvisionedOnus = 0,
    this.totalActiveOnus = 0,
  });

  factory VlanMetricsModel.fromJson(Map<String, dynamic> json) {
    return VlanMetricsModel(
      vlanId: (json['vlan_id'] as num?)?.toInt() ?? 0,
      name: json['name']?.toString(),
      description: json['description']?.toString(),
      taggedPorts: (json['tagged_ports'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      untaggedPorts: (json['untagged_ports'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      totalProvisionedOnus: (json['total_provisioned_onus'] as num?)?.toInt() ?? 0,
      totalActiveOnus: (json['total_active_onus'] as num?)?.toInt() ?? 0,
    );
  }
}

class VlanHistoryModel {
  final String id;
  final String serial;
  final int vlanId;
  final String oltId;
  final String? port;
  final String? contractId;
  final String? subscriberName;
  final String reason;
  final DateTime? startedAt;
  final DateTime? endedAt;
  final bool isCurrent;

  VlanHistoryModel({
    required this.id,
    required this.serial,
    required this.vlanId,
    required this.oltId,
    this.port,
    this.contractId,
    this.subscriberName,
    required this.reason,
    this.startedAt,
    this.endedAt,
    this.isCurrent = true,
  });

  factory VlanHistoryModel.fromJson(Map<String, dynamic> json) {
    return VlanHistoryModel(
      id: json['id']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      vlanId: (json['vlan_id'] as num?)?.toInt() ?? 0,
      oltId: json['olt_id']?.toString() ?? '',
      port: json['port']?.toString(),
      contractId: json['contract_id']?.toString(),
      subscriberName: json['subscriber_name']?.toString(),
      reason: json['reason']?.toString() ?? '',
      startedAt: json['started_at'] != null ? DateTime.tryParse(json['started_at'].toString()) : null,
      endedAt: json['ended_at'] != null ? DateTime.tryParse(json['ended_at'].toString()) : null,
      isCurrent: json['is_current'] != false,
    );
  }
}
