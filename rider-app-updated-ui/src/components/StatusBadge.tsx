// ============================================================
// RideShield — StatusBadge Component
// ============================================================

import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Colors, BorderRadius, Typography, Spacing } from '../constants/theme';

type BadgeVariant = 'active' | 'inactive' | 'danger' | 'success' | 'warning' | 'info';

interface StatusBadgeProps {
  label: string;
  variant?: BadgeVariant;
  style?: ViewStyle;
}

const variantConfig: Record<BadgeVariant, { bg: string; text: string; dot: string }> = {
  active:   { bg: Colors.successMuted, text: Colors.success, dot: Colors.success },
  inactive: { bg: Colors.card,         text: Colors.textSecondary, dot: Colors.textMuted },
  danger:   { bg: Colors.dangerMuted,  text: Colors.danger,  dot: Colors.danger },
  success:  { bg: Colors.successMuted, text: Colors.success, dot: Colors.success },
  warning:  { bg: Colors.warningMuted, text: Colors.warning, dot: Colors.warning },
  info:     { bg: Colors.primaryMuted, text: Colors.primary, dot: Colors.primary },
};

export function StatusBadge({ label, variant = 'info', style }: StatusBadgeProps) {
  const cfg = variantConfig[variant];
  return (
    <View style={[styles.badge, { backgroundColor: cfg.bg }, style]}>
      <View style={[styles.dot, { backgroundColor: cfg.dot }]} />
      <Text style={[styles.label, { color: cfg.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.sm,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 5,
    alignSelf: 'flex-start',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  label: {
    ...Typography.labelSM,
    fontSize: 11,
  },
});
