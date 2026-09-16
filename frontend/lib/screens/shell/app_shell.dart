import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_colors.dart';
import '../../models/olt_model.dart';
import '../../providers/app_state.dart';
import '../../providers/settings_provider.dart';
import '../configured/configured_screen.dart';
import '../olts/olts_screen.dart';
import '../settings/settings_screen.dart';
import '../unconfigured/unconfigured_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _currentIndex = 0;
  bool _isRefreshing = false;

  final List<Widget> _screens = const [
    UnconfiguredScreen(),
    ConfiguredScreen(),
    OltsScreen(),
    SettingsScreen(),
  ];

  @override
  void initState() {
    super.initState();
    final tabParam = Uri.base.queryParameters['tab'];
    if (tabParam != null) {
      if (tabParam == 'configured' || tabParam == '1') {
        _currentIndex = 1;
      } else if (tabParam == 'olts' || tabParam == '2') {
        _currentIndex = 2;
      } else if (tabParam == 'settings' || tabParam == '3') {
        _currentIndex = 3;
      }
    }
  }

  Future<void> _handleRefresh() async {
    setState(() => _isRefreshing = true);
    final settings = context.read<SettingsProvider>();
    final appState = context.read<AppState>();

    await settings.checkBackendHealth();
    await appState.refreshAll();

    if (mounted) {
      setState(() => _isRefreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final settings = context.watch<SettingsProvider>();
    final appState = context.watch<AppState>();
    final pendingCount = appState.unauthorizedOnus.length;

    return Scaffold(
      body: Column(
        children: [
          // Top Bar NOC
          Container(
            height: 60,
            padding: const EdgeInsets.symmetric(horizontal: 20),
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(
                bottom: BorderSide(color: AppColors.surfaceBorder, width: 1),
              ),
            ),
            child: Row(
              children: [
                // Brand Logo & Badge
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: AppColors.primary,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Icon(
                        Icons.hub_outlined,
                        color: Colors.white,
                        size: 18,
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Text(
                      'OLTAPI',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.0,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceBorder,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'NOC',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: AppColors.accentCyan,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(width: 32),

                // Navigation Tabs
                Expanded(
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        _NavTab(
                          label: 'Aguardando Autorização',
                          badgeCount: pendingCount,
                          isSelected: _currentIndex == 0,
                          icon: Icons.pending_actions_outlined,
                          onTap: () => setState(() => _currentIndex = 0),
                        ),
                        const SizedBox(width: 8),
                        _NavTab(
                          label: 'ONUs Autorizadas',
                          isSelected: _currentIndex == 1,
                          icon: Icons.dns_outlined,
                          onTap: () => setState(() => _currentIndex = 1),
                        ),
                        const SizedBox(width: 8),
                        _NavTab(
                          label: 'OLTs & Backups',
                          isSelected: _currentIndex == 2,
                          icon: Icons.developer_board,
                          onTap: () => setState(() => _currentIndex = 2),
                        ),
                        const SizedBox(width: 8),
                        _NavTab(
                          label: 'Configurações',
                          isSelected: _currentIndex == 3,
                          icon: Icons.tune,
                          onTap: () => setState(() => _currentIndex = 3),
                        ),
                      ],
                    ),
                  ),
                ),

                // Right Actions: OLT Selector + Backend Status + Refresh
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // OLT Selector Dropdown
                    if (appState.olts.isNotEmpty) ...[
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppColors.inputBackground,
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppColors.surfaceBorder),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<OltModel>(
                            value: appState.selectedOlt,
                            dropdownColor: AppColors.surface,
                            icon: const Icon(Icons.arrow_drop_down, color: AppColors.textSecondary),
                            style: const TextStyle(
                              color: AppColors.textPrimary,
                              fontSize: 13,
                              fontWeight: FontWeight.w500,
                            ),
                            items: appState.olts.map((olt) {
                              return DropdownMenuItem<OltModel>(
                                value: olt,
                                child: Text('${olt.name} (${olt.vendor.toUpperCase()})'),
                              );
                            }).toList(),
                            onChanged: (newOlt) => appState.selectOlt(newOlt),
                          ),
                        ),
                      ),
                      const SizedBox(width: 14),
                    ],

                    // Backend Connectivity Status
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        color: settings.isConnected
                            ? AppColors.statusOnline.withValues(alpha: 0.12)
                            : AppColors.statusDanger.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: settings.isConnected
                              ? AppColors.statusOnline.withValues(alpha: 0.3)
                              : AppColors.statusDanger.withValues(alpha: 0.3),
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 7,
                            height: 7,
                            decoration: BoxDecoration(
                              color: settings.isConnected
                                  ? AppColors.statusOnline
                                  : AppColors.statusDanger,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 7),
                          Text(
                            settings.isConnected
                                ? 'Online • ${settings.latencyMs ?? 0}ms'
                                : 'Offline',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: settings.isConnected
                                  ? AppColors.statusOnline
                                  : AppColors.statusDanger,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),

                    // Reload Button
                    IconButton(
                      icon: _isRefreshing
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: AppColors.primaryLight,
                              ),
                            )
                          : const Icon(Icons.refresh, size: 20, color: AppColors.textSecondary),
                      onPressed: _isRefreshing ? null : _handleRefresh,
                      tooltip: 'Sincronizar dados',
                      splashRadius: 20,
                    ),
                  ],
                ),
              ],
            ),
          ),

          // Main Body
          Expanded(
            child: _screens[_currentIndex],
          ),
        ],
      ),
    );
  }
}

class _NavTab extends StatelessWidget {
  final String label;
  final int? badgeCount;
  final bool isSelected;
  final IconData icon;
  final VoidCallback onTap;

  const _NavTab({
    required this.label,
    this.badgeCount,
    required this.isSelected,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? AppColors.surfaceHover : Colors.transparent,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(
            color: isSelected ? AppColors.surfaceBorder : Colors.transparent,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16,
              color: isSelected ? AppColors.primaryLight : AppColors.textSecondary,
            ),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                color: isSelected ? AppColors.textPrimary : AppColors.textSecondary,
              ),
            ),
            if (badgeCount != null && badgeCount! > 0) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '$badgeCount',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
