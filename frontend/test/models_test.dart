import 'package:flutter_test/flutter_test.dart';
import 'package:olt_frontend/core/theme/app_colors.dart';
import 'package:olt_frontend/models/backup_model.dart';
import 'package:olt_frontend/models/olt_model.dart';
import 'package:olt_frontend/models/onu_model.dart';
import 'package:olt_frontend/models/pon_policy_model.dart';
import 'package:olt_frontend/models/vlan_model.dart';

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

    test('OltXRayModel and SyncOltResultModel deserialize correctly', () {
      final xrayJson = {
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'olt_name': 'OLT Fiberhome AN5516',
        'vendor': 'fiberhome',
        'model': 'AN5516-04',
        'host': '10.50.50.252',
        'uptime_seconds': 86400,
        'uptime_human': '1d 0h',
        'firmware_version': 'RP0700',
        'cpu_usage_pct': 18.5,
        'memory_usage_pct': 42.0,
        'temperature_celsius': 39.0,
        'ports': [
          {
            'port_id': '0/1/1',
            'port_type': 'gpon',
            'admin_state': 'enabled',
            'oper_status': 'up',
            'onu_count': 12,
            'onu_capacity': 128,
          },
          {
            'port_id': '0/19/1',
            'port_type': 'uplink_ge',
            'admin_state': 'enabled',
            'oper_status': 'up',
            'speed_duplex': '10G Full',
          },
        ],
        'total_onus_detected': 42,
        'total_vlans_detected': 3,
        'vlans': [99, 100, 621],
        'running_config_preview': 'vlan 100',
        'is_onboarded': true,
        'snmp_active': true,
        'snmp_status': 'active',
        'snmp_community': 'public',
      };

      final xray = OltXRayModel.fromJson(xrayJson);
      expect(xray.oltName, 'OLT Fiberhome AN5516');
      expect(xray.snmpActive, true);
      expect(xray.totalOnusDetected, 42);
      expect(xray.totalVlansDetected, 3);
      expect(xray.ports.first.portId, '0/1/1');
      expect(xray.ports.last.portId, '0/19/1');
      expect(xray.vlans, [99, 100, 621]);

      final syncJson = {
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'olt_name': 'OLT Fiberhome AN5516',
        'baseline_backup_id': '0191eb58-6932-7000-8000-000000000090',
        'total_onus_discovered': 42,
        'new_onus_registered': 5,
        'existing_onus_updated': 37,
        'vlans_discovered': [99, 100, 621],
        'duration_ms': 1250.5,
        'message': 'Sincronização concluída',
      };

      final sync = SyncOltResultModel.fromJson(syncJson);
      expect(sync.totalOnusDiscovered, 42);
      expect(sync.newOnusRegistered, 5);
      expect(sync.existingOnusUpdated, 37);
      expect(sync.vlansDiscovered, [99, 100, 621]);
    });

    test('OltInspectResultModel and OltOnboardResultModel deserialize correctly', () {
      final inspectJson = {
        'host': '10.50.50.252',
        'vendor': 'fiberhome',
        'model': 'AN5516-06',
        'access_scenario': 'aux_with_inband',
        'aux_ip': '10.50.50.252',
        'existing_svis': [
          {
            'vlan_id': 99,
            'name': 'MGMT',
            'ip_cidr': '172.16.0.2/24',
            'tagged_ports': ['19/1'],
            'untagged_ports': [],
          },
        ],
        'existing_vlans': [99, 100, 621],
        'gateway': '172.16.0.1',
        'total_onus_detected': 12,
        'prompt_message': 'Acesso via porta AUX com SVI Inband detectada.',
      };

      final inspect = OltInspectResultModel.fromJson(inspectJson);
      expect(inspect.vendor, 'fiberhome');
      expect(inspect.model, 'AN5516-06');
      expect(inspect.accessScenario, 'aux_with_inband');
      expect(inspect.existingSvis.first.vlanId, 99);
      expect(inspect.existingSvis.first.ipCidr, '172.16.0.2/24');
      expect(inspect.existingVlans, [99, 100, 621]);
      expect(inspect.totalOnusDetected, 12);

      final onboardJson = {
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'name': 'OLT Bancada',
        'vendor': 'fiberhome',
        'model': 'AN5516-06',
        'host': '10.50.50.252',
        'port': 23,
        'protocol': 'telnet',
        'baseline_backup_id': '0191eb58-6932-7000-8000-000000000090',
        'snmp_community': 'public',
        'snmp_active': true,
        'total_ports': 8,
        'active_ports': 4,
        'total_onus_detected': 12,
        'new_onus_registered': 12,
        'steps': [
          {'step_key': 'probe', 'title': 'Autodescoberta CLI', 'status': 'ok', 'details': 'Detectado via Telnet'},
        ],
        'message': 'Onboarding concluído',
      };

      final onboard = OltOnboardResultModel.fromJson(onboardJson);
      expect(onboard.name, 'OLT Bancada');
      expect(onboard.snmpActive, true);
      expect(onboard.totalOnusDetected, 12);
      expect(onboard.steps.first.stepKey, 'probe');
      expect(onboard.steps.first.title, 'Autodescoberta CLI');
    });

    test('VlanMetricsModel and VlanHistoryModel deserialize correctly', () {
      final vlanJson = {
        'vlan_id': 621,
        'name': 'REDE_NEUTRA',
        'description': 'VLAN Atacado',
        'tagged_ports': ['19/1'],
        'untagged_ports': [],
        'total_provisioned_onus': 18,
        'total_active_onus': 16,
      };

      final vlan = VlanMetricsModel.fromJson(vlanJson);
      expect(vlan.vlanId, 621);
      expect(vlan.name, 'REDE_NEUTRA');
      expect(vlan.totalProvisionedOnus, 18);
      expect(vlan.totalActiveOnus, 16);
      expect(vlan.taggedPorts, ['19/1']);

      final historyJson = {
        'id': '0191eb58-6932-7000-8000-000000000100',
        'serial': 'FHTT11223344',
        'vlan_id': 621,
        'olt_id': '0191eb58-6932-7000-8000-000000000001',
        'port': '0/1/1',
        'subscriber_name': 'Cliente Atacado 01',
        'reason': 'initial_provision',
        'started_at': '2026-10-14T15:00:00Z',
        'is_current': true,
      };

      final history = VlanHistoryModel.fromJson(historyJson);
      expect(history.vlanId, 621);
      expect(history.serial, 'FHTT11223344');
      expect(history.reason, 'initial_provision');
      expect(history.isCurrent, true);
    });
  });
}

