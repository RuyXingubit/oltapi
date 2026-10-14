class BackupModel {
  final String backupId;
  final String oltId;
  final DateTime? createdAt;
  final int sizeBytes;
  final String sha256Hash;
  final String filename;

  BackupModel({
    required this.backupId,
    required this.oltId,
    this.createdAt,
    required this.sizeBytes,
    required this.sha256Hash,
    required this.filename,
  });

  factory BackupModel.fromJson(Map<String, dynamic> json) {
    return BackupModel(
      backupId: json['backup_id']?.toString() ?? '',
      oltId: json['olt_id']?.toString() ?? '',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
      sizeBytes: (json['size_bytes'] as num?)?.toInt() ?? 0,
      sha256Hash: json['sha256_hash']?.toString() ?? '',
      filename: json['filename']?.toString() ?? '',
    );
  }

  String get formattedSize => formatBytes(sizeBytes);

  static String formatBytes(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) {
      return '${(bytes / 1024).toStringAsFixed(1)} KB';
    }
    return '${(bytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }
}

class FtpServerModel {
  final String id;
  final String name;
  final String host;
  final int port;
  final String username;
  final String basePath;
  final bool isGlobalDefault;
  final bool isActive;
  final DateTime? createdAt;

  FtpServerModel({
    required this.id,
    required this.name,
    required this.host,
    this.port = 21,
    required this.username,
    this.basePath = '/',
    this.isGlobalDefault = false,
    this.isActive = true,
    this.createdAt,
  });

  factory FtpServerModel.fromJson(Map<String, dynamic> json) {
    return FtpServerModel(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      host: json['host']?.toString() ?? '',
      port: (json['port'] as num?)?.toInt() ?? 21,
      username: json['username']?.toString() ?? '',
      basePath: json['base_path']?.toString() ?? '/',
      isGlobalDefault: json['is_global_default'] == true,
      isActive: json['is_active'] != false,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'].toString())
          : null,
    );
  }
}

class FtpTestResultModel {
  final bool success;
  final String message;
  final String? banner;
  final String? workingDirectory;
  final double? latencyMs;

  FtpTestResultModel({
    required this.success,
    required this.message,
    this.banner,
    this.workingDirectory,
    this.latencyMs,
  });

  factory FtpTestResultModel.fromJson(Map<String, dynamic> json) {
    return FtpTestResultModel(
      success: json['success'] == true,
      message: json['message']?.toString() ?? '',
      banner: json['banner']?.toString(),
      workingDirectory: json['working_directory']?.toString(),
      latencyMs: (json['latency_ms'] as num?)?.toDouble(),
    );
  }
}

class OltFtpDestinationsModel {
  final String oltId;
  final List<FtpServerModel> specificDestinations;
  final List<FtpServerModel> globalDestinations;
  final List<FtpServerModel> effectiveDestinations;

  OltFtpDestinationsModel({
    required this.oltId,
    this.specificDestinations = const [],
    this.globalDestinations = const [],
    this.effectiveDestinations = const [],
  });

  factory OltFtpDestinationsModel.fromJson(Map<String, dynamic> json) {
    List<FtpServerModel> parseList(dynamic raw) {
      if (raw is List) {
        return raw
            .whereType<Map<String, dynamic>>()
            .map(FtpServerModel.fromJson)
            .toList();
      }
      return const [];
    }

    return OltFtpDestinationsModel(
      oltId: json['olt_id']?.toString() ?? '',
      specificDestinations: parseList(json['specific_destinations']),
      globalDestinations: parseList(json['global_destinations']),
      effectiveDestinations: parseList(json['effective_destinations']),
    );
  }
}

class BackupDiffResultModel {
  final String oltId;
  final String baseBackupId;
  final String targetBackupId;
  final bool identical;
  final String baseSha256;
  final String targetSha256;
  final List<String> diffLines;
  final int additionsCount;
  final int deletionsCount;

  BackupDiffResultModel({
    required this.oltId,
    required this.baseBackupId,
    required this.targetBackupId,
    required this.identical,
    required this.baseSha256,
    required this.targetSha256,
    this.diffLines = const [],
    this.additionsCount = 0,
    this.deletionsCount = 0,
  });

  factory BackupDiffResultModel.fromJson(Map<String, dynamic> json) {
    return BackupDiffResultModel(
      oltId: json['olt_id']?.toString() ?? '',
      baseBackupId: json['base_backup_id']?.toString() ?? '',
      targetBackupId: json['target_backup_id']?.toString() ?? '',
      identical: json['identical'] == true,
      baseSha256: json['base_sha256']?.toString() ?? '',
      targetSha256: json['target_sha256']?.toString() ?? '',
      diffLines: (json['diff_lines'] as List?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      additionsCount: (json['additions_count'] as num?)?.toInt() ?? 0,
      deletionsCount: (json['deletions_count'] as num?)?.toInt() ?? 0,
    );
  }
}

class BackupAuditReportModel {
  final String oltId;
  final String oltName;
  final int totalBackups;
  final int totalBytes;
  final BackupModel? latestBackup;
  final BackupModel? previousBackup;
  final bool hasChanged;
  final DateTime? lastBackupAt;

  BackupAuditReportModel({
    required this.oltId,
    required this.oltName,
    this.totalBackups = 0,
    this.totalBytes = 0,
    this.latestBackup,
    this.previousBackup,
    this.hasChanged = false,
    this.lastBackupAt,
  });

  factory BackupAuditReportModel.fromJson(Map<String, dynamic> json) {
    return BackupAuditReportModel(
      oltId: json['olt_id']?.toString() ?? '',
      oltName: json['olt_name']?.toString() ?? '',
      totalBackups: (json['total_backups'] as num?)?.toInt() ?? 0,
      totalBytes: (json['total_bytes'] as num?)?.toInt() ?? 0,
      latestBackup: json['latest_backup'] is Map<String, dynamic>
          ? BackupModel.fromJson(json['latest_backup'] as Map<String, dynamic>)
          : null,
      previousBackup: json['previous_backup'] is Map<String, dynamic>
          ? BackupModel.fromJson(
              json['previous_backup'] as Map<String, dynamic>,
            )
          : null,
      hasChanged: json['has_changed'] == true,
      lastBackupAt: json['last_backup_at'] != null
          ? DateTime.tryParse(json['last_backup_at'].toString())
          : null,
    );
  }

  String get formattedTotalBytes => BackupModel.formatBytes(totalBytes);
}

class PurgeResultModel {
  final String? oltId;
  final int deletedCount;
  final int freedBytes;
  final int remainingCount;

  PurgeResultModel({
    this.oltId,
    this.deletedCount = 0,
    this.freedBytes = 0,
    this.remainingCount = 0,
  });

  factory PurgeResultModel.fromJson(Map<String, dynamic> json) {
    return PurgeResultModel(
      oltId: json['olt_id']?.toString(),
      deletedCount: (json['deleted_count'] as num?)?.toInt() ?? 0,
      freedBytes: (json['freed_bytes'] as num?)?.toInt() ?? 0,
      remainingCount: (json['remaining_count'] as num?)?.toInt() ?? 0,
    );
  }

  String get formattedFreedBytes => BackupModel.formatBytes(freedBytes);
}

class BatchBackupResultModel {
  final int totalOlts;
  final int successful;
  final int failed;
  final List<BackupModel> backups;
  final List<Map<String, dynamic>> errors;

  BatchBackupResultModel({
    this.totalOlts = 0,
    this.successful = 0,
    this.failed = 0,
    this.backups = const [],
    this.errors = const [],
  });

  factory BatchBackupResultModel.fromJson(Map<String, dynamic> json) {
    return BatchBackupResultModel(
      totalOlts: (json['total_olts'] as num?)?.toInt() ?? 0,
      successful: (json['successful'] as num?)?.toInt() ?? 0,
      failed: (json['failed'] as num?)?.toInt() ?? 0,
      backups: (json['backups'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .map(BackupModel.fromJson)
              .toList() ??
          const [],
      errors: (json['errors'] as List?)
              ?.whereType<Map<String, dynamic>>()
              .toList() ??
          const [],
    );
  }
}
