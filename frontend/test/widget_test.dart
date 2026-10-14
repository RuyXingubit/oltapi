import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:olt_frontend/core/network/api_client.dart';
import 'package:olt_frontend/core/theme/app_theme.dart';
import 'package:olt_frontend/providers/app_state.dart';
import 'package:olt_frontend/providers/settings_provider.dart';
import 'package:olt_frontend/screens/shell/app_shell.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  late http.Client mockHttpClient;

  setUp(() {
    SharedPreferences.setMockInitialValues({});

    mockHttpClient = MockClient((request) async {
      final path = request.url.path;

      if (path.endsWith('/api/v1/olts')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000001',
              'name': 'OLT VSOL Teste',
              'vendor': 'vsol',
              'model': 'V1600G1',
              'host': '192.168.1.100',
              'port': 23,
              'protocol': 'telnet',
              'status': 'online',
              'created_at': '2026-09-15T10:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/telemetry')) {
        return http.Response(
          jsonEncode({
            'olt_id': '0191eb58-6932-7000-8000-000000000001',
            'olt_name': 'OLT VSOL Teste',
            'vendor': 'vsol',
            'model': 'V1600G1',
            'host': '192.168.1.100',
            'uptime_seconds': 86400,
            'uptime_human': '1d 0h',
            'ports': [
              {'port_id': '0/1', 'port_type': 'gpon', 'oper_status': 'up', 'onu_count': 10, 'onu_capacity': 64},
              {'port_id': '0/5', 'port_type': 'uplink_ge', 'oper_status': 'up', 'speed_duplex': '1G Full'},
            ],
            'total_onus_detected': 10,
            'total_vlans_detected': 1,
            'vlans': [100],
            'snmp_active': true,
            'snmp_status': 'active',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/vlans/metrics')) {
        return http.Response(
          jsonEncode([
            {
              'vlan_id': 100,
              'name': 'CLIENTES',
              'description': 'PPPoE Residencial',
              'tagged_ports': ['0/5'],
              'untagged_ports': [],
              'total_provisioned_onus': 10,
              'total_active_onus': 9,
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.contains('/unauthorized')) {
        return http.Response('[]', 200, headers: {'content-type': 'application/json'});
      } else if (path.endsWith('/api/v1/onus/history')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000201',
              'serial': 'ZTEGC9988776',
              'from_olt_id': '0191eb58-6932-7000-8000-000000000001',
              'from_port': '0/1/1',
              'to_olt_id': '0191eb58-6932-7000-8000-000000000001',
              'to_olt_name': 'OLT VSOL Teste',
              'to_port': '0/1/2',
              'to_onu_id': 5,
              'to_circuit_id': 'OLT VSOL Teste eth 0/1/2:5',
              'reason': 'port_swap',
              'timestamp': '2026-10-14T15:31:01Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/scanner/status')) {
        return http.Response(
          jsonEncode({
            'is_running': true,
            'interval_seconds': 60,
            'last_run_at': '2026-10-14T15:30:00Z',
            'last_run_duration_ms': 250.0,
            'last_cycle_id': 'cycle-01',
            'total_cycles': 5,
            'total_onus_detected': 12,
            'total_onus_reconciled': 1,
            'total_virgin_onus': 11,
            'total_errors': 0,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/webhooks/deliveries')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000302',
              'subscription_id': '0191eb58-6932-7000-8000-000000000301',
              'event': 'webhook.ping',
              'url': 'https://erp.provedor.com.br/webhook',
              'status_code': 200,
              'success': true,
              'duration_ms': 38.0,
              'timestamp': '2026-10-14T15:05:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/webhooks')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000301',
              'url': 'https://erp.provedor.com.br/webhook',
              'secret': 'hmac-secret-123',
              'events': ['*'],
              'is_active': true,
              'description': 'ERP IXC',
              'created_at': '2026-10-14T15:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/tenants')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000401',
              'name': 'FibraSul Neutra',
              'type': 'NEUTRAL_OPERATOR',
              'is_active': true,
              'created_at': '2026-10-14T15:00:00Z',
              'vlans': [
                {
                  'id': '0191eb58-6932-7000-8000-000000000402',
                  'tenant_id': '0191eb58-6932-7000-8000-000000000401',
                  'olt_id': '0191eb58-6932-7000-8000-000000000001',
                  'vlan_id': 621,
                  'description': 'Atacado',
                  'created_at': '2026-10-14T15:10:00Z',
                }
              ],
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/users')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000501',
              'name': 'Admin Master',
              'email': 'admin@oltapi.local',
              'role': 'SUPER_ADMIN',
              'is_active': true,
              'allowed_olt_ids': [],
              'created_at': '2026-10-14T15:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/api-keys')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000601',
              'name': 'Chave ERP',
              'key_prefix': 'olt_99aa',
              'scopes': ['*'],
              'created_at': '2026-10-14T15:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/backups/audit-all')) {
        return http.Response(
          jsonEncode([
            {
              'olt_id': '0191eb58-6932-7000-8000-000000000001',
              'olt_name': 'OLT VSOL Teste',
              'total_backups': 2,
              'total_bytes': 40960,
              'has_changed': true,
              'last_backup_at': '2026-10-14T16:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/ftp-servers')) {
        return http.Response(
          jsonEncode([
            {
              'id': '0191eb58-6932-7000-8000-000000000701',
              'name': 'FTP Primário Datacenter',
              'host': '10.50.50.10',
              'port': 21,
              'username': 'oltbackup',
              'base_path': '/olt-backups',
              'is_global_default': true,
              'is_active': true,
              'created_at': '2026-10-14T16:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/ftp-servers')) {
        return http.Response(
          jsonEncode({
            'olt_id': '0191eb58-6932-7000-8000-000000000001',
            'specific_destinations': [],
            'global_destinations': [
              {
                'id': '0191eb58-6932-7000-8000-000000000701',
                'name': 'FTP Primário Datacenter',
                'host': '10.50.50.10',
                'port': 21,
                'username': 'oltbackup',
                'base_path': '/olt-backups',
                'is_global_default': true,
                'is_active': true,
              }
            ],
            'effective_destinations': [
              {
                'id': '0191eb58-6932-7000-8000-000000000701',
                'name': 'FTP Primário Datacenter',
                'host': '10.50.50.10',
                'port': 21,
                'username': 'oltbackup',
                'base_path': '/olt-backups',
                'is_global_default': true,
                'is_active': true,
              }
            ],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/backups/audit')) {
        return http.Response(
          jsonEncode({
            'olt_id': '0191eb58-6932-7000-8000-000000000001',
            'olt_name': 'OLT VSOL Teste',
            'total_backups': 2,
            'total_bytes': 40960,
            'has_changed': true,
            'last_backup_at': '2026-10-14T16:00:00Z',
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/backups/compare')) {
        return http.Response(
          jsonEncode({
            'olt_id': '0191eb58-6932-7000-8000-000000000001',
            'base_backup_id': 'b-01',
            'target_backup_id': 'b-02',
            'base_sha256': 'hash111111111111',
            'target_sha256': 'hash222222222222',
            'identical': false,
            'additions_count': 2,
            'deletions_count': 1,
            'diff_lines': ['--- b-01.cfg', '+++ b-02.cfg', '@@ -1,2 +1,3 @@', '+vlan 621', '-vlan 100'],
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/backups')) {
        return http.Response(
          jsonEncode([
            {
              'backup_id': 'b-02',
              'olt_id': '0191eb58-6932-7000-8000-000000000001',
              'size_bytes': 20480,
              'sha256_hash': 'hash222222222222',
              'filename': 'olt_vsol_20261014_1600.cfg',
              'created_at': '2026-10-14T16:00:00Z',
            },
            {
              'backup_id': 'b-01',
              'olt_id': '0191eb58-6932-7000-8000-000000000001',
              'size_bytes': 20480,
              'sha256_hash': 'hash111111111111',
              'filename': 'olt_vsol_20261014_1500.cfg',
              'created_at': '2026-10-14T15:00:00Z',
            }
          ]),
          200,
          headers: {'content-type': 'application/json'},
        );
      } else if (path.endsWith('/api/v1/onus')) {
        return http.Response('[]', 200, headers: {'content-type': 'application/json'});
      }

      return http.Response('{"status": "ok"}', 200, headers: {'content-type': 'application/json'});
    });
  });

  testWidgets('AppShell renders NOC Topbar, logo and brand', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final settings = SettingsProvider();
    settings.apiClient = ApiClient(
      baseUrl: SettingsProvider.defaultBaseUrl,
      apiKey: SettingsProvider.defaultApiKey,
      client: mockHttpClient,
    );
    final appState = AppState(apiClient: settings.apiClient);

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: settings),
          ChangeNotifierProvider.value(value: appState),
        ],
        child: MaterialApp(
          theme: AppTheme.darkTheme,
          home: const AppShell(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Valida Marca e Badge NOC
    expect(find.text('OLTAPI'), findsOneWidget);
    expect(find.text('NOC'), findsOneWidget);

    // Valida Tabs na barra superior
    expect(find.byIcon(Icons.pending_actions_outlined), findsOneWidget);
    expect(find.byIcon(Icons.dns_outlined), findsOneWidget);
    expect(find.byIcon(Icons.developer_board), findsOneWidget);
    expect(find.byIcon(Icons.admin_panel_settings_outlined), findsOneWidget);
    expect(find.byIcon(Icons.tune), findsOneWidget);
  });

  testWidgets('AppShell tab navigation switches between all screens smoothly', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final settings = SettingsProvider();
    settings.apiClient = ApiClient(
      baseUrl: SettingsProvider.defaultBaseUrl,
      apiKey: SettingsProvider.defaultApiKey,
      client: mockHttpClient,
    );
    final appState = AppState(apiClient: settings.apiClient);

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: settings),
          ChangeNotifierProvider.value(value: appState),
        ],
        child: MaterialApp(
          theme: AppTheme.darkTheme,
          home: const AppShell(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Tab 2: ONUs Autorizadas (Configured)
    await tester.tap(find.byIcon(Icons.dns_outlined));
    await tester.pumpAndSettle();
    expect(find.text('ONUs Autorizadas (Configured)'), findsOneWidget);

    // Tab 3: OLTs & Backups
    await tester.tap(find.byIcon(Icons.developer_board));
    await tester.pumpAndSettle();
    expect(find.text('Inventário de OLTs'), findsOneWidget);

    // Tab 5: Configurações
    await tester.ensureVisible(find.byIcon(Icons.tune));
    await tester.tap(find.byIcon(Icons.tune));
    await tester.pumpAndSettle();
    expect(find.text('Configurações de Conexão'), findsOneWidget);

    // Tab 1: Voltar para Aguardando Autorização
    await tester.ensureVisible(find.byIcon(Icons.pending_actions_outlined));
    await tester.tap(find.byIcon(Icons.pending_actions_outlined));
    await tester.pumpAndSettle();
    expect(find.text('Aguardando Autorização'), findsNWidgets(2)); // Header tab + Tela título
  });

  testWidgets('OltsScreen opens Onda A dialogs (Wizard Zero-Touch, Raio-X, VLANs) without overflow',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final settings = SettingsProvider();
    settings.apiClient = ApiClient(
      baseUrl: SettingsProvider.defaultBaseUrl,
      apiKey: SettingsProvider.defaultApiKey,
      client: mockHttpClient,
    );
    final appState = AppState(apiClient: settings.apiClient);
    await appState.loadOlts();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: settings),
          ChangeNotifierProvider.value(value: appState),
        ],
        child: MaterialApp(
          theme: AppTheme.darkTheme,
          home: const AppShell(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Navigate to OLTs tab
    await tester.ensureVisible(find.text('Gerenciar OLTs'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Gerenciar OLTs'));
    await tester.pumpAndSettle();

    expect(find.text('Wizard Zero-Touch'), findsOneWidget);
    expect(find.text('OLT VSOL Teste'), findsWidgets);

    // 1. Open Wizard Zero-Touch dialog
    await tester.tap(find.text('Wizard Zero-Touch'));
    await tester.pumpAndSettle();
    expect(find.text('Onboarding Wizard & Descoberta Zero-Touch'), findsOneWidget);
    expect(find.text('Inspecionar Arquitetura (Fase 1)'), findsOneWidget);
    await tester.tap(find.text('Cancelar'));
    await tester.pumpAndSettle();

    // 2. Open Raio-X & Sync dialog
    await tester.tap(find.text('Raio-X & Sync'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Raio-X de Chassi & Telemetria'), findsOneWidget);
    expect(find.text('Portas PON do Chassi'), findsOneWidget);
    await tester.tap(find.text('Fechar'));
    await tester.pumpAndSettle();

    // 3. Open VLANs dialog
    await tester.tap(find.text('VLANs'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Catálogo Flash de VLANs & Ocupação'), findsOneWidget);
    expect(find.text('VLAN 100'), findsOneWidget);
    await tester.tap(find.text('Fechar'));
    await tester.pumpAndSettle();
  });

  testWidgets('GovernanceScreen renders Onda C sub-tabs (Scanner, Webhooks, Tenants, RBAC) without overflow',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final settings = SettingsProvider();
    settings.apiClient = ApiClient(
      baseUrl: SettingsProvider.defaultBaseUrl,
      apiKey: SettingsProvider.defaultApiKey,
      client: mockHttpClient,
    );
    final appState = AppState(apiClient: settings.apiClient);
    await appState.loadOlts();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: settings),
          ChangeNotifierProvider.value(value: appState),
        ],
        child: MaterialApp(
          theme: AppTheme.darkTheme,
          home: const AppShell(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Navigate to Governança & Automação tab
    await tester.ensureVisible(find.text('Governança & Automação'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Governança & Automação'));
    await tester.pumpAndSettle();

    // 1. Sub-tab 0: Scanner & Timeline TR-101
    expect(find.text('Governança, Automação & RBAC'), findsOneWidget);
    expect(find.text('RODANDO'), findsOneWidget);
    expect(find.text('ZTEGC9988776'), findsOneWidget);

    // 2. Sub-tab 1: Webhooks ERP (HMAC)
    await tester.tap(find.text('Webhooks ERP (HMAC)'));
    await tester.pumpAndSettle();
    expect(find.text('https://erp.provedor.com.br/webhook'), findsWidgets);
    expect(find.text('HMAC-SHA256'), findsOneWidget);

    // 3. Sub-tab 2: Inquilinos & Rede Neutra
    await tester.tap(find.text('Inquilinos & Rede Neutra'));
    await tester.pumpAndSettle();
    expect(find.text('FibraSul Neutra'), findsOneWidget);
    expect(find.textContaining('VLAN 621'), findsOneWidget);

    // 4. Sub-tab 3: Usuários & API Keys
    await tester.tap(find.text('Usuários & API Keys'));
    await tester.pumpAndSettle();
    expect(find.text('Admin Master'), findsOneWidget);
    expect(find.text('admin@oltapi.local'), findsOneWidget);
    expect(find.text('Chave ERP'), findsOneWidget);
  });

  testWidgets('BackupsScreen renders Onda B (Audit Drift, Multi-FTP, Unified Diff Dialog) without overflow',
      (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1400, 900);
    tester.view.devicePixelRatio = 1.0;

    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
    });

    final settings = SettingsProvider();
    settings.apiClient = ApiClient(
      baseUrl: SettingsProvider.defaultBaseUrl,
      apiKey: SettingsProvider.defaultApiKey,
      client: mockHttpClient,
    );
    final appState = AppState(apiClient: settings.apiClient);
    await appState.loadOlts();

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider.value(value: settings),
          ChangeNotifierProvider.value(value: appState),
        ],
        child: MaterialApp(
          theme: AppTheme.darkTheme,
          home: const AppShell(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Navigate to Gestão de Backups tab
    await tester.ensureVisible(find.text('Gestão de Backups'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Gestão de Backups'));
    await tester.pumpAndSettle();

    // Verify Onda B header and audit drift badge on OLT card
    expect(find.text('Disaster Recovery, Backups & Servidores FTP'), findsOneWidget);
    expect(find.text('DRIFT DETECTADO'), findsOneWidget);

    // Open OltBackupsDialog
    await tester.tap(find.text('Backups, Diff & FTP'));
    await tester.pumpAndSettle();

    expect(find.textContaining('Histórico de Backups'), findsOneWidget);
    expect(find.text('olt_vsol_20261014_1600.cfg'), findsOneWidget);
    expect(find.text('CONFIG DRIFT DETECTADO'), findsOneWidget);

    // Open Unified Diff modal inside OltBackupsDialog
    await tester.tap(find.text('Unified Diff'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Comparador Unified Diff'), findsOneWidget);
    expect(find.text('DRIFT (+2 / -1)'), findsOneWidget);

    // Close Unified Diff modal
    await tester.tap(find.text('Fechar'));
    await tester.pumpAndSettle();

    // Close OltBackupsDialog
    await tester.tap(find.byIcon(Icons.close));
    await tester.pumpAndSettle();

    // Switch to Servidores FTP Remotos sub-tab
    await tester.tap(find.textContaining('Servidores FTP Remotos'));
    await tester.pumpAndSettle();
    expect(find.text('FTP Primário Datacenter'), findsOneWidget);
    expect(find.text('GLOBAL DEFAULT'), findsOneWidget);
    expect(find.text('ftp://oltbackup@10.50.50.10:21/olt-backups'), findsOneWidget);
  });
}

