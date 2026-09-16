import 'package:flutter_test/flutter_test.dart';
import 'package:olt_frontend/core/theme/app_colors.dart';
import 'package:olt_frontend/models/backup_model.dart';
import 'package:olt_frontend/models/olt_model.dart';
import 'package:olt_frontend/models/onu_model.dart';
import 'package:olt_frontend/models/pon_policy_model.dart';

void main() {
  group('Models Unit Tests', () {
    test('OltModel deserializes correctly from JSON', () {
      final json = {
        'id': '0191eb58-6932-7000-8000-000000000001',
        'name': 'OLT Central Fiberhome',
        'vendor': 'fiberhome',
        'model': 'AN5516-04',
        'host': '192.168.10.1',
        'port': 23,
        'protocol': 'telnet',
        'snmp_community': 'public',
        'snmp_port': 161,
        'status': 'online',
        'connection_message': 'Conectado com sucesso',
        'created_at': '2026-09-15T12:00:00Z',
      };

      final olt = OltModel.fromJson(json);

      expect(olt.id, '0191eb58-6932-7000-8000-000000000001');
      expect(olt.name, 'OLT Central Fiberhome');
      expect(olt.vendor, 'fiberhome');
      expect(olt.model, 'AN5516-04');
      expect(olt.host, '192.168.10.1');
      expect(olt.port, 23);
      expect(olt.status, 'online');
      expect(olt.createdAt, isNotNull);
    });

    test('UnauthorizedOnu deserializes correctly', () {
      final json = {
        'port': '0/1/1',
        'serial': 'FHTT12345678',
        'model': 'HG6143D',
        'detected_at': '2026-09-15T14:30:00Z',
      };

      final onu = UnauthorizedOnu.fromJson(json);

      expect(onu.port, '0/1/1');
      expect(onu.serial, 'FHTT12345678');
      expect(onu.model, 'HG6143D');
      expect(onu.detectedAt, isNotNull);
    });

    test('ConfiguredOnu deserializes correctly', () {
      final json = {
        'id': '0191eb58-6932-7000-8000-000000000002',
        'serial': 'VSOL87654321',
        'subscriber_name': 'Cliente Joao da Silva',
        'contract_status': 'ACTIVE',
        'vlan': 100,
        'profile': 'PLAN_200M',
        'current_olt_id': '0191eb58-6932-7000-8000-000000000001',
        'current_port': '0/1/2',
        'current_onu_id': 5,
      };

      final onu = ConfiguredOnu.fromJson(json);

      expect(onu.id, '0191eb58-6932-7000-8000-000000000002');
      expect(onu.serial, 'VSOL87654321');
      expect(onu.subscriberName, 'Cliente Joao da Silva');
      expect(onu.contractStatus, 'ACTIVE');
      expect(onu.vlan, 100);
      expect(onu.currentPort, '0/1/2');
      expect(onu.currentOnuId, 5);
    });

    test('OnuDiagnostics handles dBm levels', () {
      final json = {
        'port': '0/1/1',
        'onu_id': 1,
        'serial': 'FHTT11223344',
        'status': 'online',
        'rx_power_dbm': -19.45,
        'tx_power_dbm': 2.30,
        'olt_rx_power_dbm': -20.10,
        'vlan': 200,
      };

      final diag = OnuDiagnostics.fromJson(json);

      expect(diag.rxPowerDbm, -19.45);
      expect(diag.txPowerDbm, 2.30);
      expect(diag.oltRxPowerDbm, -20.10);
      expect(diag.status, 'online');
    });

    test('BackupModel formats file sizes correctly', () {
      final b1 = BackupModel(
        backupId: '1',
        oltId: 'olt1',
        sizeBytes: 500,
        sha256Hash: 'abc',
        filename: 'backup.cfg',
      );
      expect(b1.formattedSize, '500 B');

      final b2 = BackupModel(
        backupId: '2',
        oltId: 'olt1',
        sizeBytes: 20480, // 20 KB
        sha256Hash: 'def',
        filename: 'backup2.cfg',
      );
      expect(b2.formattedSize, '20.0 KB');

      final b3 = BackupModel(
        backupId: '3',
        oltId: 'olt1',
        sizeBytes: 2621440, // 2.5 MB
        sha256Hash: 'ghi',
        filename: 'backup3.cfg',
      );
      expect(b3.formattedSize, '2.50 MB');
    });

    test('AppColors optical signal evaluation is accurate', () {
      // Sinal excelente (-20 dBm)
      expect(AppColors.getOpticalSignalQuality(-20.0), 'Excelente');
      expect(AppColors.getOpticalSignalColor(-20.0), AppColors.statusOnline);

      // Sinal limítrofe / atenção (-26.5 dBm)
      expect(AppColors.getOpticalSignalQuality(-26.5), 'Atenção');
      expect(AppColors.getOpticalSignalColor(-26.5), AppColors.statusWarning);

      // Sinal crítico (-29.0 dBm ou saturado -5 dBm)
      expect(AppColors.getOpticalSignalQuality(-29.0), 'Crítico');
      expect(AppColors.getOpticalSignalColor(-29.0), AppColors.statusDanger);
      expect(AppColors.getOpticalSignalQuality(-5.0), 'Crítico');
      expect(AppColors.getOpticalSignalColor(-5.0), AppColors.statusDanger);

      // N/A
      expect(AppColors.getOpticalSignalQuality(null), 'N/A');
    });

    test('PonPolicyModel deserializes correctly from JSON', () {
      final json = {
        'id': '0191eb58-6932-7000-8000-000000000010',
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'port': '0/1',
        'default_vlan': 300,
        'default_mode': 'transparent',
        'default_line_profile': 'PLAN_100M',
        'auto_authorize_enabled': false,
      };

      final policy = PonPolicyModel.fromJson(json);

      expect(policy.id, '0191eb58-6932-7000-8000-000000000010');
      expect(policy.oltId, '0191eb58-6932-7000-8000-000000000001');
      expect(policy.port, '0/1');
      expect(policy.defaultVlan, 300);
      expect(policy.defaultMode, 'transparent');
      expect(policy.defaultProfile, 'PLAN_100M');
      expect(policy.autoAuthorize, false);
    });

    test('AutoProvisionTaskModel deserializes correctly and handles status', () {
      final json = {
        'id': '0191eb58-6932-7000-8000-000000000020',
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'port': '0/2',
        'duration_minutes': 120,
        'default_vlan': 621,
        'default_profile': 'DEFAULT',
        'expires_at': '2026-09-16T14:00:00Z',
        'remaining_seconds': 7150,
        'status': 'active',
        'onus_provisioned_count': 14,
        'created_at': '2026-09-16T12:00:00Z',
      };

      final task = AutoProvisionTaskModel.fromJson(json);

      expect(task.id, '0191eb58-6932-7000-8000-000000000020');
      expect(task.port, '0/2');
      expect(task.durationMinutes, 120);
      expect(task.defaultVlan, 621);
      expect(task.remainingSeconds, 7150);
      expect(task.status, 'active');
      expect(task.onusProvisionedCount, 14);
    });

    test('ProvisioningSchemaModel handles vlans, profiles, and ports', () {
      final json = {
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'vendor': 'vsol',
        'model': 'V1600G',
        'available_vlans': [
          {'vlan_id': 100, 'name': 'INTERNET'},
          {'vlan_id': 200, 'name': 'VOIP'},
          {'vlan_id': 300, 'name': 'IPTV'},
        ],
        'available_profiles': [
          {'name': 'DEFAULT', 'type': 'line'},
          {'name': 'PLAN_100M', 'type': 'srv'},
        ],
        'ports': ['0/1', '0/2', '0/3', '0/4'],
      };

      final schema = ProvisioningSchemaModel.fromJson(json);

      expect(schema.availableVlans.length, 3);
      expect(schema.availableVlans.first['vlan_id'], 100);
      expect(schema.availableProfiles.length, 2);
      expect(schema.availableProfiles.first['name'], 'DEFAULT');
      expect(schema.ports.length, 4);
    });
  });
}
