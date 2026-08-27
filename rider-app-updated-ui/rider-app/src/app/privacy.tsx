// ============================================================
// RideShield — Privacy & Security Screen
// ============================================================

import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Switch,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../constants/colors';
import { Spacing, Typography, BorderRadius, Shadows } from '../constants/theme';
import { useAuth } from '../store/authStore';

export default function PrivacyScreen() {
  const router = useRouter();
  const { state: authState } = useAuth();
  const user = authState.user;

  const [telemetrySharing, setTelemetrySharing] = useState(true);
  const [backgroundLocation, setBackgroundLocation] = useState(true);

  const handleChangePassword = () => {
    Alert.alert(
      'Change Password',
      `A password reset link will be sent to ${user?.email ?? 'your email'}.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Send Link', onPress: () => Alert.alert('Link Sent', 'Check your email for reset instructions.') },
      ]
    );
  };

  return (
    <SafeAreaView style={styles.safe}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Privacy & Security</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Security Shield Banner */}
        <View style={styles.banner}>
          <Ionicons name="shield-checkmark" size={32} color="#00C2A8" />
          <View style={styles.bannerTextGroup}>
            <Text style={styles.bannerTitle}>Bank-Grade Encryption</Text>
            <Text style={styles.bannerSub}>
              All location data, sensor telemetry, and claims are 256-bit AES encrypted.
            </Text>
          </View>
        </View>

        {/* Data & Telemetry Privacy */}
        <Text style={styles.sectionTitle}>DATA & SENSOR PRIVACY</Text>
        <View style={styles.card}>
          <PrivacySwitchRow
            icon="location-outline"
            label="Background Location Tracking"
            description="Active only during active shifts to monitor ride coverage."
            value={backgroundLocation}
            onValueChange={setBackgroundLocation}
          />
          <View style={styles.divider} />
          <PrivacySwitchRow
            icon="analytics-outline"
            label="Anonymized Crash Telemetry"
            description="Help improve crash detection models anonymously."
            value={telemetrySharing}
            onValueChange={setTelemetrySharing}
          />
        </View>

        {/* Account Security */}
        <Text style={styles.sectionTitle}>ACCOUNT SECURITY</Text>
        <View style={styles.card}>
          <Pressable
            onPress={handleChangePassword}
            style={({ pressed }) => [styles.passwordRow, pressed && { opacity: 0.7 }]}
          >
            <View style={styles.passwordIconWrap}>
              <Ionicons name="key-outline" size={20} color={Colors.primary} />
            </View>
            <View style={styles.passwordTextGroup}>
              <Text style={styles.passwordTitle}>Change Password</Text>
              <Text style={styles.passwordSub}>Send password reset link to your email</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
          </Pressable>
        </View>

        {/* Data Rights */}
        <Text style={styles.sectionTitle}>DATA RIGHTS & LEGAL</Text>
        <View style={styles.card}>
          <PrivacyLinkRow
            icon="document-text-outline"
            label="Privacy Policy"
            onPress={() => Alert.alert('Privacy Policy', 'RideShield encrypts and never sells your location data.')}
          />
          <View style={styles.divider} />
          <PrivacyLinkRow
            icon="trash-outline"
            label="Request Data Deletion"
            danger
            onPress={() => Alert.alert('Data Deletion', 'Contact support to request full data erasure.')}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function PrivacySwitchRow({
  icon,
  label,
  description,
  value,
  onValueChange,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  description: string;
  value: boolean;
  onValueChange: (val: boolean) => void;
}) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={22} color={Colors.textSecondary} style={styles.rowIcon} />
      <View style={styles.rowTextContent}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={styles.rowDesc}>{description}</Text>
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ false: Colors.border, true: Colors.primary }}
        thumbColor="#ffffff"
      />
    </View>
  );
}

function PrivacyLinkRow({
  icon,
  label,
  value,
  onPress,
  danger,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value?: string;
  onPress: () => void;
  danger?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && { opacity: 0.6 }]}
    >
      <Ionicons
        name={icon}
        size={22}
        color={danger ? Colors.danger : Colors.textSecondary}
        style={styles.rowIcon}
      />
      <Text style={[styles.rowLabel, { flex: 1 }, danger && { color: Colors.danger }]}>{label}</Text>
      {value && <Text style={styles.rowValue}>{value}</Text>}
      <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
    </Pressable>
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
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#002820',
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
    ...Shadows.soft,
  },
  bannerTextGroup: { flex: 1 },
  bannerTitle: { ...Typography.h4, color: '#00C2A8', fontWeight: '700' },
  bannerSub: { ...Typography.caption, color: 'rgba(255,255,255,0.85)', marginTop: 2 },
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
  rowValue: { ...Typography.bodySM, color: Colors.primary, marginRight: 4, fontWeight: '600' },
  passwordRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  passwordIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  passwordTextGroup: { flex: 1 },
  passwordTitle: { ...Typography.bodyLG, fontWeight: '700', color: Colors.textPrimary },
  passwordSub: { ...Typography.caption, color: Colors.textSecondary, marginTop: 2 },
  contactRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
    gap: Spacing.md,
  },
  contactIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  contactTextGroup: { flex: 1 },
  contactTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  contactName: { ...Typography.bodyMD, fontWeight: '700', color: Colors.textPrimary },
  primaryBadge: {
    backgroundColor: Colors.successMuted,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
  },
  primaryBadgeText: { fontSize: 9, fontWeight: '800', color: Colors.success },
  contactPhone: { ...Typography.caption, color: Colors.textSecondary, marginTop: 2 },
  addContactButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.md,
    gap: Spacing.xs,
  },
  addContactText: { ...Typography.labelMD, color: Colors.primary, fontWeight: '700' },
});
