import 'package:flutter/material.dart';

class AppColors {
  // Backgrounds
  static const Color background = Color(0xFF0B0F17);
  static const Color surface = Color(0xFF131A24);
  static const Color surfaceHover = Color(0xFF1B2433);
  static const Color surfaceBorder = Color(0xFF222F42);
  static const Color inputBackground = Color(0xFF0F1520);

  // Brand / Primaries
  static const Color primary = Color(0xFF2563EB);
  static const Color primaryLight = Color(0xFF3B82F6);
  static const Color primaryDark = Color(0xFF1D4ED8);
  static const Color accentCyan = Color(0xFF06B6D4);

  // Semantics NOC
  static const Color statusOnline = Color(0xFF10B981);
  static const Color statusWarning = Color(0xFFF59E0B);
  static const Color statusDanger = Color(0xFFEF4444);
  static const Color statusOffline = Color(0xFF6B7280);

  // Typography
  static const Color textPrimary = Color(0xFFF3F4F6);
  static const Color textSecondary = Color(0xFF9CA3AF);
  static const Color textMuted = Color(0xFF6B7280);
  static const Color codeBackground = Color(0xFF080C12);

  // Signal Optical Helpers
  static Color getOpticalSignalColor(double? dbm) {
    if (dbm == null) return textMuted;
    if (dbm >= -25.0 && dbm <= -8.0) {
      return statusOnline; // Excelente / Bom
    } else if (dbm < -25.0 && dbm >= -28.0) {
      return statusWarning; // Atenção / Limítrofe
    } else {
      return statusDanger; // Crítico / LOS / Saturado
    }
  }

  static String getOpticalSignalQuality(double? dbm) {
    if (dbm == null) return 'N/A';
    if (dbm >= -25.0 && dbm <= -8.0) {
      return 'Excelente';
    } else if (dbm < -25.0 && dbm >= -28.0) {
      return 'Atenção';
    } else {
      return 'Crítico';
    }
  }
}
