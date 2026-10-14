class ScannerOltSummaryModel {
  final String oltId;
  final String oltName;
  final String status;
  final int detectedOnusCount;
  final List<String> reconciledSerials;
  final List<String> virginSerials;
  final String? errorMessage;

  ScannerOltSummaryModel({
    required this.oltId,
    required this.oltName,
    required this.status,
    this.detectedOnusCount = 0,
    this.reconciledSerials = const [],
    this.virginSerials = const [],
    this.errorMessage,
  });

  factory ScannerOltSummaryModel.fromJson(Map<String, dynamic> json) {
    return ScannerOltSummaryModel(
      oltId: json['olt_id']?.toString() ?? '',
      oltName: json['olt_name']?.toString() ?? '',
      status: json['status']?.toString() ?? 'success',
      detectedOnusCount: (json['detected_onus_count'] as num?)?.toInt() ?? 0,
      reconciledSerials:
          (json['reconciled_serials'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      virginSerials:
          (json['virgin_serials'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      errorMessage: json['error_message']?.toString(),
    );
  }
}

class ScannerRunResultModel {
  final String cycleId;
  final DateTime? startedAt;
  final DateTime? completedAt;
  final double durationMs;
  final int oltsScanned;
  final int detectedOnusCount;
  final int reconciledOnusCount;
  final int virginOnusCount;
  final int errorsCount;
  final List<ScannerOltSummaryModel> oltResults;

  ScannerRunResultModel({
    required this.cycleId,
    this.startedAt,
    this.completedAt,
    this.durationMs = 0.0,
    this.oltsScanned = 0,
    this.detectedOnusCount = 0,
    this.reconciledOnusCount = 0,
    this.virginOnusCount = 0,
    this.errorsCount = 0,
    this.oltResults = const [],
  });

  factory ScannerRunResultModel.fromJson(Map<String, dynamic> json) {
    return ScannerRunResultModel(
      cycleId: json['cycle_id']?.toString() ?? '',
      startedAt: json['started_at'] != null ? DateTime.tryParse(json['started_at'].toString()) : null,
      completedAt:
          json['completed_at'] != null ? DateTime.tryParse(json['completed_at'].toString()) : null,
      durationMs: (json['duration_ms'] as num?)?.toDouble() ?? 0.0,
      oltsScanned: (json['olts_scanned'] as num?)?.toInt() ?? 0,
      detectedOnusCount: (json['detected_onus_count'] as num?)?.toInt() ?? 0,
      reconciledOnusCount: (json['reconciled_onus_count'] as num?)?.toInt() ?? 0,
      virginOnusCount: (json['virgin_onus_count'] as num?)?.toInt() ?? 0,
      errorsCount: (json['errors_count'] as num?)?.toInt() ?? 0,
      oltResults: (json['olt_results'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .map(ScannerOltSummaryModel.fromJson)
              .toList() ??
          const [],
    );
  }
}

class ScannerStatusModel {
  final bool isRunning;
  final int intervalSeconds;
  final DateTime? lastRunAt;
  final double? lastRunDurationMs;
  final String? lastCycleId;
  final int totalCycles;
  final int totalOnusDetected;
  final int totalOnusReconciled;
  final int totalVirginOnus;
  final int totalErrors;

  ScannerStatusModel({
    required this.isRunning,
    required this.intervalSeconds,
    this.lastRunAt,
    this.lastRunDurationMs,
    this.lastCycleId,
    this.totalCycles = 0,
    this.totalOnusDetected = 0,
    this.totalOnusReconciled = 0,
    this.totalVirginOnus = 0,
    this.totalErrors = 0,
  });

  factory ScannerStatusModel.fromJson(Map<String, dynamic> json) {
    return ScannerStatusModel(
      isRunning: json['is_running'] == true,
      intervalSeconds: (json['interval_seconds'] as num?)?.toInt() ?? 60,
      lastRunAt: json['last_run_at'] != null ? DateTime.tryParse(json['last_run_at'].toString()) : null,
      lastRunDurationMs: (json['last_run_duration_ms'] as num?)?.toDouble(),
      lastCycleId: json['last_cycle_id']?.toString(),
      totalCycles: (json['total_cycles'] as num?)?.toInt() ?? 0,
      totalOnusDetected: (json['total_onus_detected'] as num?)?.toInt() ?? 0,
      totalOnusReconciled: (json['total_onus_reconciled'] as num?)?.toInt() ?? 0,
      totalVirginOnus: (json['total_virgin_onus'] as num?)?.toInt() ?? 0,
      totalErrors: (json['total_errors'] as num?)?.toInt() ?? 0,
    );
  }
}

class OnuMigrationEventModel {
  final String id;
  final String serial;
  final String? contractId;
  final String? subscriberName;
  final DateTime? timestamp;
  final String reason;
  final String? fromOltId;
  final String? fromOltName;
  final String? fromPort;
  final int? fromOnuId;
  final String? fromCircuitId;
  final String toOltId;
  final String toOltName;
  final String toPort;
  final int toOnuId;
  final String toCircuitId;
  final String status;
  final String? details;

  OnuMigrationEventModel({
    required this.id,
    required this.serial,
    this.contractId,
    this.subscriberName,
    this.timestamp,
    required this.reason,
    this.fromOltId,
    this.fromOltName,
    this.fromPort,
    this.fromOnuId,
    this.fromCircuitId,
    required this.toOltId,
    required this.toOltName,
    required this.toPort,
    required this.toOnuId,
    required this.toCircuitId,
    this.status = 'success',
    this.details,
  });

  factory OnuMigrationEventModel.fromJson(Map<String, dynamic> json) {
    return OnuMigrationEventModel(
      id: json['id']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      contractId: json['contract_id']?.toString(),
      subscriberName: json['subscriber_name']?.toString(),
      timestamp: json['timestamp'] != null ? DateTime.tryParse(json['timestamp'].toString()) : null,
      reason: json['reason']?.toString() ?? '',
      fromOltId: json['from_olt_id']?.toString(),
      fromOltName: json['from_olt_name']?.toString(),
      fromPort: json['from_port']?.toString(),
      fromOnuId: (json['from_onu_id'] as num?)?.toInt(),
      fromCircuitId: json['from_circuit_id']?.toString(),
      toOltId: json['to_olt_id']?.toString() ?? '',
      toOltName: json['to_olt_name']?.toString() ?? '',
      toPort: json['to_port']?.toString() ?? '',
      toOnuId: (json['to_onu_id'] as num?)?.toInt() ?? 0,
      toCircuitId: json['to_circuit_id']?.toString() ?? '',
      status: json['status']?.toString() ?? 'success',
      details: json['details']?.toString(),
    );
  }
}

class ReconcileFieldEventResultModel {
  final bool success;
  final String actionTaken;
  final String serial;
  final String? contractId;
  final String? subscriberName;
  final String? oldCircuitId;
  final String? newCircuitId;
  final String message;

  ReconcileFieldEventResultModel({
    required this.success,
    required this.actionTaken,
    required this.serial,
    this.contractId,
    this.subscriberName,
    this.oldCircuitId,
    this.newCircuitId,
    required this.message,
  });

  factory ReconcileFieldEventResultModel.fromJson(Map<String, dynamic> json) {
    return ReconcileFieldEventResultModel(
      success: json['success'] == true,
      actionTaken: json['action_taken']?.toString() ?? '',
      serial: json['serial']?.toString() ?? '',
      contractId: json['contract_id']?.toString(),
      subscriberName: json['subscriber_name']?.toString(),
      oldCircuitId: json['old_circuit_id']?.toString(),
      newCircuitId: json['new_circuit_id']?.toString(),
      message: json['message']?.toString() ?? '',
    );
  }
}

class WebhookSubscriptionModel {
  final String id;
  final String url;
  final String secret;
  final List<String> events;
  final bool isActive;
  final String? description;
  final DateTime? createdAt;

  WebhookSubscriptionModel({
    required this.id,
    required this.url,
    required this.secret,
    this.events = const ['*'],
    this.isActive = true,
    this.description,
    this.createdAt,
  });

  factory WebhookSubscriptionModel.fromJson(Map<String, dynamic> json) {
    return WebhookSubscriptionModel(
      id: json['id']?.toString() ?? '',
      url: json['url']?.toString() ?? '',
      secret: json['secret']?.toString() ?? '',
      events: (json['events'] as List?)?.map((e) => e.toString()).toList() ?? const ['*'],
      isActive: json['is_active'] != false,
      description: json['description']?.toString(),
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
    );
  }
}

class WebhookDeliveryLogModel {
  final String id;
  final String subscriptionId;
  final String event;
  final String url;
  final int? statusCode;
  final bool success;
  final double durationMs;
  final String? errorMessage;
  final DateTime? timestamp;

  WebhookDeliveryLogModel({
    required this.id,
    required this.subscriptionId,
    required this.event,
    required this.url,
    this.statusCode,
    required this.success,
    this.durationMs = 0.0,
    this.errorMessage,
    this.timestamp,
  });

  factory WebhookDeliveryLogModel.fromJson(Map<String, dynamic> json) {
    return WebhookDeliveryLogModel(
      id: json['id']?.toString() ?? '',
      subscriptionId: json['subscription_id']?.toString() ?? '',
      event: json['event']?.toString() ?? '',
      url: json['url']?.toString() ?? '',
      statusCode: (json['status_code'] as num?)?.toInt(),
      success: json['success'] == true,
      durationMs: (json['duration_ms'] as num?)?.toDouble() ?? 0.0,
      errorMessage: json['error_message']?.toString(),
      timestamp: json['timestamp'] != null ? DateTime.tryParse(json['timestamp'].toString()) : null,
    );
  }
}

class TenantVlanAllocationModel {
  final String id;
  final String tenantId;
  final String oltId;
  final int vlanId;
  final String? description;
  final DateTime? createdAt;

  TenantVlanAllocationModel({
    required this.id,
    required this.tenantId,
    required this.oltId,
    required this.vlanId,
    this.description,
    this.createdAt,
  });

  factory TenantVlanAllocationModel.fromJson(Map<String, dynamic> json) {
    return TenantVlanAllocationModel(
      id: json['id']?.toString() ?? '',
      tenantId: json['tenant_id']?.toString() ?? '',
      oltId: json['olt_id']?.toString() ?? '',
      vlanId: (json['vlan_id'] as num?)?.toInt() ?? 0,
      description: json['description']?.toString(),
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
    );
  }
}

class TenantModel {
  final String id;
  final String name;
  final String type;
  final bool isActive;
  final DateTime? createdAt;
  final List<TenantVlanAllocationModel> vlans;

  TenantModel({
    required this.id,
    required this.name,
    required this.type,
    this.isActive = true,
    this.createdAt,
    this.vlans = const [],
  });

  factory TenantModel.fromJson(Map<String, dynamic> json) {
    return TenantModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      type: json['type']?.toString() ?? 'NEUTRAL_OPERATOR',
      isActive: json['is_active'] != false,
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      vlans: (json['vlans'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .map(TenantVlanAllocationModel.fromJson)
              .toList() ??
          const [],
    );
  }
}

class UserAccountModel {
  final String id;
  final String tenantId;
  final String name;
  final String email;
  final String role;
  final bool isActive;
  final List<String> allowedOltIds;
  final DateTime? createdAt;

  UserAccountModel({
    required this.id,
    required this.tenantId,
    required this.name,
    required this.email,
    required this.role,
    this.isActive = true,
    this.allowedOltIds = const [],
    this.createdAt,
  });

  factory UserAccountModel.fromJson(Map<String, dynamic> json) {
    return UserAccountModel(
      id: json['id']?.toString() ?? '',
      tenantId: json['tenant_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      email: json['email']?.toString() ?? '',
      role: json['role']?.toString() ?? 'NOC',
      isActive: json['is_active'] != false,
      allowedOltIds:
          (json['allowed_olt_ids'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
    );
  }
}

class ApiKeyModel {
  final String id;
  final String tenantId;
  final String userId;
  final String name;
  final String keyPrefix;
  final List<String> scopes;
  final bool isActive;
  final DateTime? createdAt;
  final DateTime? lastUsedAt;
  final DateTime? expiresAt;

  ApiKeyModel({
    required this.id,
    required this.tenantId,
    required this.userId,
    required this.name,
    required this.keyPrefix,
    this.scopes = const [],
    this.isActive = true,
    this.createdAt,
    this.lastUsedAt,
    this.expiresAt,
  });

  factory ApiKeyModel.fromJson(Map<String, dynamic> json) {
    return ApiKeyModel(
      id: json['id']?.toString() ?? '',
      tenantId: json['tenant_id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      keyPrefix: json['key_prefix']?.toString() ?? '',
      scopes: (json['scopes'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      isActive: json['is_active'] != false,
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      lastUsedAt:
          json['last_used_at'] != null ? DateTime.tryParse(json['last_used_at'].toString()) : null,
      expiresAt:
          json['expires_at'] != null ? DateTime.tryParse(json['expires_at'].toString()) : null,
    );
  }
}

class ApiKeyCreatedModel {
  final String id;
  final String name;
  final String key;
  final String keyPrefix;
  final List<String> scopes;
  final DateTime? createdAt;
  final DateTime? expiresAt;

  ApiKeyCreatedModel({
    required this.id,
    required this.name,
    required this.key,
    required this.keyPrefix,
    this.scopes = const [],
    this.createdAt,
    this.expiresAt,
  });

  factory ApiKeyCreatedModel.fromJson(Map<String, dynamic> json) {
    return ApiKeyCreatedModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      key: json['key']?.toString() ?? '',
      keyPrefix: json['key_prefix']?.toString() ?? '',
      scopes: (json['scopes'] as List?)?.map((e) => e.toString()).toList() ?? const [],
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null,
      expiresAt:
          json['expires_at'] != null ? DateTime.tryParse(json['expires_at'].toString()) : null,
    );
  }
}
