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
}

