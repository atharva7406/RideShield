// ============================================================
// RideShield — Notifications Screen
// ============================================================

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Switch,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';
import { Spacing, Typography, BorderRadius, Shadows } from '../constants/theme';

export default function NotificationsScreen() {
  const router = useRouter();

  const [pushEnabled, setPushEnabled] = useState(true);
  const [incidentAlerts, setIncidentAlerts] = useState(true);
  const [shiftReminders, setShiftReminders] = useState(true);
  const [weatherAlerts, setWeatherAlerts] = useState(true);
  const [weeklyReport, setWeeklyReport] = useState(false);

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Notifications</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Master Push Toggle */}
        <View style={styles.masterCard}>
          <View style={styles.masterIconWrap}>
            <Ionicons name="notifications-circle" size={32} color={Colors.primary} />
          </View>
          <View style={styles.masterTextGroup}>
            <Text style={styles.masterTitle}>Push Notifications</Text>
            <Text style={styles.masterSub}>Receive real-time alerts for safety & shifts.</Text>
          </View>
          <Switch
            value={pushEnabled}
            onValueChange={setPushEnabled}
            trackColor={{ false: Colors.border, true: Colors.primary }}
            thumbColor="#ffffff"
          />
        </View>

        {/* Alert Preferences */}
        <Text style={styles.sectionTitle}>ALERT PREFERENCES</Text>
        <View style={styles.card}>
          <NotificationSwitchRow
            icon="alert-circle-outline"
            label="Crash & Emergency Alerts"
            description="Immediate notifications when incident detection triggers."
            value={incidentAlerts}
            onValueChange={setIncidentAlerts}
            disabled={!pushEnabled}
          />
          <View style={styles.divider} />
          <NotificationSwitchRow
            icon="time-outline"
            label="Shift Start Reminders"
            description="Remind me to start daily coverage before riding."
            value={shiftReminders}
            onValueChange={setShiftReminders}
            disabled={!pushEnabled}
          />
          <View style={styles.divider} />
          <NotificationSwitchRow
            icon="rainy-outline"
            label="Weather & Hazard Warnings"
            description="Daily safety insights for rain and heavy traffic."
            value={weatherAlerts}
            onValueChange={setWeatherAlerts}
            disabled={!pushEnabled}
          />
          <View style={styles.divider} />
          <NotificationSwitchRow
            icon="stats-chart-outline"
            label="Weekly Coverage Digest"
            description="Summary of protected hours and safety score."
            value={weeklyReport}
            onValueChange={setWeeklyReport}
            disabled={!pushEnabled}
          />
        </View>

        {/* Recent Notifications Log */}
        <Text style={styles.sectionTitle}>RECENT NOTIFICATIONS</Text>
        <View style={styles.card}>
          <NotificationItem
            icon="shield-checkmark"
            iconColor={Colors.success}
            title="Shift Protected Successfully"
            time="2 hours ago"
            body="Your 4h 15m shift was fully covered under Gig Shield Policy."
          />
          <View style={styles.divider} />
          <NotificationItem
            icon="bulb"
            iconColor={Colors.warning}
            title="Weather Advisory Alert"
            time="Today, 8:00 AM"
            body="Wet road conditions reported downtown. Stay safe!"
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function NotificationSwitchRow({
  icon,
  label,
  description,
  value,
  onValueChange,
  disabled,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  description: string;
  value: boolean;
  onValueChange: (val: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <View style={[styles.row, disabled && { opacity: 0.5 }]}>
      <Ionicons name={icon} size={22} color={Colors.textSecondary} style={styles.rowIcon} />
      <View style={styles.rowTextContent}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowDesc}>{description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
        trackColor={{ false: Colors.border, true: Colors.primary }}
        thumbColor="#ffffff"
      />
    </View>
  );
}

function NotificationItem({
  icon,
  iconColor,
  title,
  time,
  body,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  iconColor: string;
  title: string;
  time: string;
  body: string;
}) {
  return (
    <View style={styles.itemRow}>
      <View style={[styles.itemIconCircle, { backgroundColor: `${iconColor}15` }]}>
        <Ionicons name={icon} size={20} color={iconColor} />
      </View>
      <View style={styles.itemContent}>
        <View style={styles.itemHeader}>
          <Text style={styles.itemTitle}>{title}</Text>
          <Text style={styles.itemTime}>{time}</Text>
        </View>
        <Text style={styles.itemBody}>{body}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    gap: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  backButton: { padding: Spacing.xs },
  headerTitle: { ...Typography.h3, color: Colors.textPrimary },
  scroll: {
    padding: Spacing.lg,
    paddingBottom: Spacing.xxl,
    gap: Spacing.md,
  },
  masterCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  masterIconWrap: {},
  masterTextGroup: { flex: 1 },
  masterTitle: { ...Typography.h4, color: Colors.textPrimary },
  masterSub: { ...Typography.bodySM, color: Colors.textSecondary, marginTop: 2 },
  sectionTitle: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    letterSpacing: 1.2,
    marginTop: Spacing.sm,
    marginLeft: Spacing.xs,
  },
  card: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    paddingHorizontal: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadows.soft,
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
  },
  rowIcon: { marginRight: Spacing.md },
  rowTextContent: { flex: 1, paddingRight: Spacing.sm },
  rowLabel: { ...Typography.bodyLG, color: Colors.textPrimary, fontWeight: '600' },
  rowDesc: { ...Typography.caption, color: Colors.textSecondary, marginTop: 2 },
  itemRow: {
    flexDirection: 'row',
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  itemIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  itemContent: { flex: 1 },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
  },
  itemTitle: { ...Typography.bodyMD, fontWeight: '700', color: Colors.textPrimary },
  itemTime: { ...Typography.caption, color: Colors.textMuted },
  itemBody: { ...Typography.bodySM, color: Colors.textSecondary, marginTop: 2 },
});
