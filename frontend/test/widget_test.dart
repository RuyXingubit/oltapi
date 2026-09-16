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
      } else if (path.contains('/unauthorized')) {
        return http.Response('[]', 200, headers: {'content-type': 'application/json'});
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
    expect(find.byIcon(Icons.tune), findsOneWidget);
  });

  testWidgets('AppShell tab navigation switches between all 4 screens smoothly', (WidgetTester tester) async {
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
    expect(find.text('OLTs & Gestão de Backups'), findsOneWidget);

    // Tab 4: Configurações
    await tester.tap(find.byIcon(Icons.tune));
    await tester.pumpAndSettle();
    expect(find.text('Configurações de Conexão'), findsOneWidget);

    // Tab 1: Voltar para Aguardando Autorização
    await tester.tap(find.byIcon(Icons.pending_actions_outlined));
    await tester.pumpAndSettle();
    expect(find.text('Aguardando Autorização'), findsNWidgets(2)); // Header tab + Tela título
  });
}
