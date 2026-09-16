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
