// ============================================================
// RideShield — ConnectionStatus Component
// ============================================================

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors, Spacing, Typography } from '../constants/theme';
import type { TelemetryConnectionStatus } from '../types/telemetry';

interface ConnectionStatusProps {
  status: TelemetryConnectionStatus;
  isSimulated?: boolean;
}

type StatusLevel = 'connected' | 'connecting' | 'disconnected';

const statusColor: Record<StatusLevel, string> = {
  connected: Colors.success,
  connecting: Colors.warning,
  disconnected: Colors.danger,
};

const statusLabel: Record<StatusLevel, string> = {
  connected: 'Connected',
  connecting: 'Connecting…',
  disconnected: 'Disconnected',
};

function StatusRow({ label, status }: { label: string; status: StatusLevel }) {
  const color = statusColor[status];
  return (
    <View style={styles.row}>
      <View style={[styles.dot, { backgroundColor: color }]} />
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, { color }]}>{statusLabel[status]}</Text>
    </View>
  );
}

export function ConnectionStatus({ status, isSimulated }: ConnectionStatusProps) {
  return (
    <View style={styles.container}>
      <StatusRow label="GPS" status={status.gps} />
      <StatusRow label="Motion Sensors" status={status.motion} />
      <StatusRow label="Backend" status={status.backend} />
      {isSimulated && (
        <View style={styles.simBadge}>
          <Text style={styles.simText}>⚠ Demo Telemetry</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.xs,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  label: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    flex: 1,
  },
  value: {
    ...Typography.labelMD,
  },
  simBadge: {
    marginTop: Spacing.xs,
    backgroundColor: Colors.warningMuted,
    borderRadius: 6,
    paddingHorizontal: Spacing.sm,
    paddingVertical: 3,
    alignSelf: 'flex-start',
  },
  simText: {
    ...Typography.labelSM,
    color: Colors.warning,
  },
});
