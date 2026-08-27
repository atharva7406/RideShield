// ============================================================
// RideShield — Settings Screen
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
import { Spacing, Typography, BorderRadius } from '../constants/theme';
import { useAuth } from '../store/authStore';
import { useLanguage } from '../store/languageContext';

export default function SettingsScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const { language, setLanguage, t } = useLanguage();

  const [notifications, setNotifications] = useState(true);
  const [autoStart, setAutoStart] = useState(false);
  const [offlineMode, setOfflineMode] = useState(false);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>{t('settings')}</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* App Preferences */}
        <Text style={styles.sectionTitle}>{t('appPreferences')}</Text>
        <View style={styles.card}>
          <SettingSwitch
            icon="notifications-outline"
            label={t('pushNotifications')}
            value={notifications}
            onValueChange={setNotifications}
          />
          <View style={styles.divider} />
          <SettingSwitch
            icon="play-circle-outline"
            label={t('autoStartShift')}
            value={autoStart}
            onValueChange={setAutoStart}
            description={t('autoStartDesc')}
          />
          <View style={styles.divider} />
          <SettingSwitch
            icon="cloud-offline-outline"
            label={t('offlineMode')}
            value={offlineMode}
            onValueChange={setOfflineMode}
            description={t('offlineModeDesc')}
          />
          <View style={styles.divider} />
          <View style={styles.settingRow}>
            <Ionicons name="language-outline" size={22} color={Colors.textSecondary} style={styles.settingIcon} />
            <View style={styles.settingTextContent}>
              <Text style={styles.settingLabel}>{t('appLanguage')}</Text>
            </View>
            <View style={styles.langSelector}>
              <Pressable
                style={[styles.langChip, language === 'en' && styles.langChipActive]}
                onPress={() => setLanguage('en')}
              >
                <Text style={[styles.langChipText, language === 'en' && styles.langChipTextActive]}>EN</Text>
              </Pressable>
              <Pressable
                style={[styles.langChip, language === 'hi' && styles.langChipActive]}
                onPress={() => setLanguage('hi')}
              >
                <Text style={[styles.langChipText, language === 'hi' && styles.langChipTextActive]}>हिन्दी</Text>
              </Pressable>
              <Pressable
                style={[styles.langChip, language === 'mr' && styles.langChipActive]}
                onPress={() => setLanguage('mr')}
              >
                <Text style={[styles.langChipText, language === 'mr' && styles.langChipTextActive]}>मराठी</Text>
              </Pressable>
            </View>
          </View>
        </View>

        {/* Device Permissions */}
        <Text style={styles.sectionTitle}>{t('devicePermissions')}</Text>
        <View style={styles.card}>
          <SettingLink icon="location-outline" label={t('locationServices')} onPress={() => {}} value={t('granted')} />
          <View style={styles.divider} />
          <SettingLink icon="pulse-outline" label={t('motionSensors')} onPress={() => {}} value={t('granted')} />
        </View>

        {/* Account & Security */}
        <Text style={styles.sectionTitle}>{t('accountSecurity')}</Text>
        <View style={styles.card}>
          <SettingLink icon="key-outline" label={t('changePassword')} onPress={() => {}} />
          <View style={styles.divider} />
          <SettingLink icon="call-outline" label={t('emergencyContacts')} onPress={() => {}} value={`2 ${t('set')}`} />
          <View style={styles.divider} />
          <SettingLink
            icon="log-out-outline"
            label={t('logOut')}
            onPress={async () => {
              await logout();
              router.replace('/(auth)/login');
            }}
            danger
          />
        </View>

        <Text style={styles.footerText}>RideShield v1.0.0 (Build 42)</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function SettingSwitch({
  icon,
  label,
  value,
  onValueChange,
  description,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: boolean;
  onValueChange: (val: boolean) => void;
  description?: string;
}) {
  return (
    <View style={styles.settingRow}>
      <Ionicons name={icon} size={22} color={Colors.textSecondary} style={styles.settingIcon} />
      <View style={styles.settingTextContent}>
        <Text style={styles.settingLabel}>{label}</Text>
        {description && <Text style={styles.settingDesc}>{description}</Text>}
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        trackColor={{ false: Colors.border, true: Colors.primary }}
        thumbColor={Colors.textPrimary}
      />
    </View>
  );
}

function SettingLink({
  icon,
  label,
  onPress,
  value,
  danger,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
  value?: string;
  danger?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.settingRow, pressed && styles.pressed]}
    >
      <Ionicons
        name={icon}
        size={22}
        color={danger ? Colors.danger : Colors.textSecondary}
        style={styles.settingIcon}
      />
      <Text style={[styles.settingLabel, danger && { color: Colors.danger }]}>{label}</Text>
      {value && <Text style={styles.settingValue}>{value}</Text>}
      {!danger && <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.md,
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
  sectionTitle: {
    ...Typography.labelMD,
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
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
  },
  settingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: Spacing.md,
  },
  settingIcon: {
    marginRight: Spacing.md,
  },
  settingTextContent: {
    flex: 1,
    paddingRight: Spacing.sm,
  },
  settingLabel: {
    ...Typography.bodyLG,
    color: Colors.textPrimary,
    flex: 1,
  },
  settingDesc: {
    ...Typography.caption,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  settingValue: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    marginRight: Spacing.xs,
  },
  pressed: {
    opacity: 0.6,
  },
  footerText: {
    ...Typography.caption,
    color: Colors.textMuted,
    textAlign: 'center',
    marginTop: Spacing.xl,
  },
  langSelector: {
    flexDirection: 'row',
    gap: 6,
  },
  langChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: BorderRadius.lg,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  langChipActive: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  langChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: Colors.textSecondary,
  },
  langChipTextActive: {
    color: '#ffffff',
  },
});
