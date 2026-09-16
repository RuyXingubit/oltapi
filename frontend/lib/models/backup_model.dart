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

  String get formattedSize {
    if (sizeBytes < 1024) return '$sizeBytes B';
    if (sizeBytes < 1024 * 1024) {
      return '${(sizeBytes / 1024).toStringAsFixed(1)} KB';
    }
    return '${(sizeBytes / (1024 * 1024)).toStringAsFixed(2)} MB';
  }
}
