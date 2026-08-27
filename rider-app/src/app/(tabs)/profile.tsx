// ============================================================
// RideShield — Profile Screen (Modern Soft Blue Style)
// ============================================================

import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../../store/authStore';
import { useLanguage } from '../../store/languageContext';
import { SOSButton } from '../../components/SOSButton';
import { VehicleTypeLabels } from '../../types/auth';

type RowItem = {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  danger?: boolean;
  badge?: string;
};

export default function ProfileScreen() {
  const router = useRouter();
  const { state, logout, refreshUser } = useAuth();
  const { language, setLanguage, t } = useLanguage();
  const user = state.user;

  useFocusEffect(
    useCallback(() => {
      refreshUser();
    }, [refreshUser])
  );

  const handleLogout = useCallback(async () => {
    await logout();
    router.replace('/(auth)/login');
  }, [logout, router]);

  const getTranslatedVehicleType = () => {
    if (!user?.vehicleType) return t('twoWheeler');
    switch (user.vehicleType) {
      case 'two_wheeler': return t('twoWheeler');
      case 'three_wheeler': return t('threeWheeler');
      case 'four_wheeler': return t('fourWheeler');
      case 'bicycle': return t('bicycle');
      default: return VehicleTypeLabels[user.vehicleType] || t('twoWheeler');
    }
  };

  return (
    <View style={styles.container}>
      {/* Soft Blue Sky Gradient Header Background */}
      <LinearGradient
        colors={['#7dd3fc', '#bae6fd', '#e0f2fe', '#f8fafc']}
        locations={[0, 0.35, 0.7, 1]}
        style={styles.gradientHeader}
      />

      <SafeAreaView style={styles.safe} edges={['top']}>
        {/* Top Header */}
        <View style={styles.topHeader}>
          <Text style={styles.brandText}>RideShield</Text>
          <View style={styles.liveBadge}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>{t('live')}</Text>
          </View>
        </View>

        <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
          {/* Avatar Section */}
          <View style={styles.avatarSection}>
            <View style={styles.avatarCircle}>
              <Text style={styles.avatarInitial}>
                {user?.fullName?.[0]?.toUpperCase() ?? 'R'}
              </Text>
            </View>
            <Text style={styles.userName}>{user?.fullName ?? 'Alex Mercer'}</Text>
            <Text style={styles.userPhone}>{user?.phone ?? '+91 98765 43210'}</Text>

            <View style={styles.badgeRow}>
              <View style={styles.ratingBadge}>
                <Ionicons name="speedometer-outline" size={14} color="#ffffff" />
                <Text style={styles.ratingText}>{Math.max(0, Math.round((5.0 - (user?.safetyRating ?? 5.0)) * 20))}% {t('risk')}</Text>
              </View>
              <View style={styles.verifiedBadge}>
                <Ionicons
                  name={user?.kycStatus === 'APPROVED' ? "checkmark-circle" : "alert-circle"}
                  size={14}
                  color="#0284c7"
                />
                <Text style={styles.verifiedText}>
                  {user?.kycStatus === 'APPROVED' ? t('approved') : user?.kycStatus === 'REJECTED' ? t('rejected') : t('pending')}
                </Text>
              </View>
            </View>
          </View>

          {/* Rider Information Card */}
          <View style={styles.card}>
            <View style={styles.cardHeader}>
              <View style={styles.cardIconWrap}>
                <Ionicons name="bicycle-outline" size={20} color="#0284c7" />
              </View>
              <View>
                <Text style={styles.cardTitle}>{t('riderInformation')}</Text>
                <Text style={styles.cardSub}>{t('vehicleAndRegistration')}</Text>
              </View>
            </View>

            <View style={styles.divider} />

            <InfoRow label={t('vehicleType')} value={getTranslatedVehicleType()} />
            <InfoRow label={t('makeAndModel')} value={user?.vehicleType === 'bicycle' ? 'Hero Lectro C8' : 'Yamaha MT-07'} />
            <InfoRow label={t('licensePlate')} value={user?.licenseNumber || 'N/A'} valueColor="#0284c7" />
          </View>

          {/* Settings & Preferences Section */}
          <Text style={styles.sectionTitle}>{t('settingsAndPreferences')}</Text>
          <View style={styles.card}>
            <MenuRow
              label={t('notifications')}
              icon="notifications-outline"
              onPress={() => router.push('/notifications' as any)}
            />
            <View style={styles.divider} />
            <MenuRow
              label={t('privacyAndSecurity')}
              icon="lock-closed-outline"
              onPress={() => router.push('/privacy' as any)}
            />
            <View style={styles.divider} />

            {/* Language Selector Switch replacing Emergency Contacts */}
            <View style={styles.menuRow}>
              <View style={styles.menuIconWrap}>
                <Ionicons name="language-outline" size={18} color="#0284c7" />
              </View>
              <Text style={styles.menuLabel}>{t('language')}</Text>

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

          {/* Log Out Button */}
          <Pressable style={styles.logoutButton} onPress={handleLogout}>
            <Ionicons name="log-out-outline" size={20} color="#0369a1" />
            <Text style={styles.logoutText}>{t('logOut')}</Text>
          </Pressable>
        </ScrollView>

        {/* Floating SOS Button */}
        <View style={styles.sosContainer}>
          <SOSButton onPress={() => router.push('/sos')} size={56} />
        </View>
      </SafeAreaView>
    </View>
  );
}

function InfoRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, valueColor ? { color: valueColor, fontWeight: '700' } : {}]}>{value}</Text>
    </View>
  );
}

function MenuRow({ label, icon, onPress, danger, badge }: RowItem) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.menuRow, pressed && { opacity: 0.7 }]}
    >
      <View style={[styles.menuIconWrap, danger && { backgroundColor: '#fee2e2' }]}>
        <Ionicons name={icon} size={18} color={danger ? '#dc2626' : '#0284c7'} />
      </View>
      <Text style={[styles.menuLabel, danger && { color: '#dc2626' }]}>{label}</Text>

      {badge && (
        <View style={[styles.menuBadge, danger && { backgroundColor: '#dc2626' }]}>
          <Text style={styles.menuBadgeText}>{badge}</Text>
        </View>
      )}
      <Ionicons name="chevron-forward" size={18} color="#94a3b8" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8fafc',
  },
  gradientHeader: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 340,
  },
  safe: {
    flex: 1,
  },
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  brandText: {
    fontSize: 20,
    fontWeight: '800',
    color: '#0f172a',
    letterSpacing: -0.3,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 20,
    gap: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 2,
  },
  liveDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
    backgroundColor: '#22c55e',
  },
  liveText: {
    fontSize: 12,
    fontWeight: '800',
    color: '#16a34a',
    letterSpacing: 0.5,
  },
  scroll: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 100,
    gap: 16,
  },
  avatarSection: {
    alignItems: 'center',
    marginVertical: 8,
  },
  avatarCircle: {
    width: 88,
    height: 88,
    borderRadius: 44,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 8,
    shadowColor: '#0284c7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 10,
    elevation: 4,
    borderWidth: 3,
    borderColor: '#ffffff',
  },
  avatarInitial: {
    fontSize: 38,
    fontWeight: '800',
    color: '#0284c7',
  },
  userName: {
    fontSize: 22,
    fontWeight: '800',
    color: '#0f172a',
  },
  userPhone: {
    fontSize: 14,
    fontWeight: '500',
    color: '#475569',
    marginTop: 2,
    marginBottom: 12,
  },
  badgeRow: {
    flexDirection: 'row',
    gap: 10,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0284c7',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 6,
  },
  ratingText: {
    fontSize: 13,
    color: '#ffffff',
    fontWeight: '700',
  },
  verifiedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    gap: 6,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  verifiedText: {
    fontSize: 13,
    color: '#0284c7',
    fontWeight: '700',
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: 20,
    padding: 20,
    shadowColor: '#0f172a',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.04,
    shadowRadius: 8,
    elevation: 2,
    borderWidth: 1,
    borderColor: '#f1f5f9',
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  cardIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#e0f2fe',
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0f172a',
  },
  cardSub: {
    fontSize: 13,
    color: '#64748b',
    marginTop: 2,
  },
  divider: {
    height: 1,
    backgroundColor: '#f1f5f9',
    marginVertical: 14,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
  },
  infoLabel: {
    fontSize: 14,
    color: '#64748b',
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#0f172a',
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#0f172a',
    marginTop: 4,
    marginBottom: -4,
  },
  menuRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 2,
    gap: 12,
  },
  menuIconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#e0f2fe',
    alignItems: 'center',
    justifyContent: 'center',
  },
  menuLabel: {
    fontSize: 15,
    fontWeight: '500',
    color: '#0f172a',
    flex: 1,
  },
  menuBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
    backgroundColor: '#0284c7',
  },
  menuBadgeText: {
    fontSize: 10,
    color: '#ffffff',
    fontWeight: '700',
  },
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#bae6fd',
    paddingVertical: 14,
    borderRadius: 30,
    borderWidth: 1,
    borderColor: '#7dd3fc',
    marginTop: 8,
  },
  logoutText: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0369a1',
  },
  langSelector: {
    flexDirection: 'row',
    gap: 6,
  },
  langChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 16,
    backgroundColor: '#f1f5f9',
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  langChipActive: {
    backgroundColor: '#0284c7',
    borderColor: '#0284c7',
  },
  langChipText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#475569',
  },
  langChipTextActive: {
    color: '#ffffff',
  },
  sosContainer: {
    position: 'absolute',
    bottom: 20,
    right: 20,
  },
});
