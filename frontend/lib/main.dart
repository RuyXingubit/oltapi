import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme/app_theme.dart';
import 'providers/app_state.dart';
import 'providers/auth_provider.dart';
import 'providers/settings_provider.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/setup_screen.dart';
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
        ChangeNotifierProxyProvider<SettingsProvider, AuthProvider>(
          create: (ctx) => AuthProvider(settingsProvider: ctx.read<SettingsProvider>()),
          update: (ctx, settings, previous) => previous ?? AuthProvider(settingsProvider: settings),
        ),
        ChangeNotifierProxyProvider<AuthProvider, AppState>(
          create: (ctx) => AppState(apiClient: ctx.read<AuthProvider>().apiClient),
          update: (ctx, auth, previous) {
            final appState = previous ?? AppState(apiClient: auth.apiClient);
            return appState;
          },
        ),
      ],
      child: MaterialApp(
        title: 'OLTAPI - Central de Operações de Rede',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.darkTheme,
        home: const _AppRouter(),
      ),
    );
  }
}

class _AppRouter extends StatefulWidget {
  const _AppRouter();

  @override
  State<_AppRouter> createState() => _AppRouterState();
}

class _AppRouterState extends State<_AppRouter> {
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      final auth = context.watch<AuthProvider>();
      if (!auth.isLoading && auth.isAuthenticated) {
        _initialized = true;
        WidgetsBinding.instance.addPostFrameCallback((_) {
          context.read<AppState>().refreshAll();
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    if (auth.isLoading) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    if (auth.isSetupRequired) {
      return const SetupScreen();
    }

    if (!auth.isAuthenticated) {
      return const LoginScreen();
    }

    return const AppShell();
  }
}
