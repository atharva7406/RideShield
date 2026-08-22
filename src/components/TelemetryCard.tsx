// ============================================================
// RideShield — TelemetryCard Component
// ============================================================

import React from 'react';
import { View, Text, StyleSheet, ViewStyle } from 'react-native';
import { Colors, BorderRadius, Spacing, Typography } from '../constants/theme';

interface TelemetryCardProps {
  label: string;
  value: string;
  unit?: string;
  icon?: React.ReactNode;
  accentColor?: string;
  style?: ViewStyle;
}

export function TelemetryCard({
  label,
  value,
  unit,
  icon,
  accentColor = Colors.primary,
  style,
}: TelemetryCardProps) {
  return (
    <View style={[styles.card, style]}>
      {/* Top accent bar */}
      <View style={[styles.accentBar, { backgroundColor: accentColor }]} />

      <View style={styles.content}>
        <View style={styles.header}>
          {icon && <View style={styles.iconWrapper}>{icon}</View>}
          <Text style={[styles.label, { color: accentColor }]}>{label}</Text>
        </View>

        <View style={styles.valueRow}>
          <Text style={styles.value}>{value}</Text>
          {unit && <Text style={styles.unit}>{unit}</Text>}
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  accentBar: {
    height: 3,
    width: '100%',
  },
  content: {
    padding: Spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: Spacing.xs,
    gap: 6,
  },
  iconWrapper: {
    marginRight: 2,
  },
  label: {
    ...Typography.labelSM,
    letterSpacing: 1.2,
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 4,
  },
  value: {
    ...Typography.h2,
    color: Colors.textPrimary,
    lineHeight: 30,
  },
  unit: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    marginBottom: 2,
  },
});
