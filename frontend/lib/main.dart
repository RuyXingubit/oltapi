import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme/app_theme.dart';
import 'providers/app_state.dart';
import 'providers/settings_provider.dart';
import 'screens/shell/app_shell.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OltApp());
}

class OltApp extends StatelessWidget {
  const OltApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => SettingsProvider()),
        ChangeNotifierProxyProvider<SettingsProvider, AppState>(
          create: (ctx) => AppState(apiClient: ctx.read<SettingsProvider>().apiClient),
          update: (ctx, settings, previous) {
            final appState = previous ?? AppState(apiClient: settings.apiClient);
            // Se as credenciais mudaram, atualiza e recarrega
            return appState;
          },
        ),
      ],
      child: MaterialApp(
        title: 'OLTAPI - Central de Operações de Rede',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        home: const _AppInitializer(),
      ),
    );
  }
}

class _AppInitializer extends StatefulWidget {
  const _AppInitializer();

  @override
  State<_AppInitializer> createState() => _AppInitializerState();
}

class _AppInitializerState extends State<_AppInitializer> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _initApp();
    });
  }

  Future<void> _initApp() async {
    final settings = context.read<SettingsProvider>();
    final appState = context.read<AppState>();

    await settings.checkBackendHealth();
    if (settings.isConnected) {
      await appState.refreshAll();
    }
  }

  @override
  Widget build(BuildContext context) {
    return const AppShell();
  }
}
