// ============================================================
// RideShield — Profile Screen (Vibrant Style)
// ============================================================

import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../store/authStore';
import { SOSButton } from '../../components/SOSButton';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../../constants/theme';
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
  const { state, logout } = useAuth();
  const user = state.user;

  const handleLogout = useCallback(async () => {
    await logout();
    router.replace('/(auth)/login');
  }, [logout, router]);

  const menuRows: RowItem[] = [
    { label: 'Notifications', icon: 'notifications-outline', onPress: () => router.push('/notifications' as any) },
    { label: 'Privacy & Security', icon: 'lock-closed-outline', onPress: () => router.push('/privacy' as any) },
    { label: 'Emergency Contacts', icon: 'medical-outline', onPress: () => router.push('/privacy' as any), badge: '2 Set' },
  ];

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Top Header */}
      <View style={styles.topHeader}>
        <View style={styles.brandContainer}>
          <Text style={styles.brandText}>RideShield</Text>
        </View>
        <View style={styles.liveBadge}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>LIVE</Text>
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
          <Text style={styles.userPhone}>{user?.phone ?? '+1 (555) 019-2834'}</Text>
          
          <View style={styles.badgeRow}>
            <View style={styles.ratingBadge}>
              <Ionicons name="star" size={14} color="#ffffff" />
              <Text style={styles.ratingText}>4.9 Rating</Text>
            </View>
            <View style={styles.verifiedBadge}>
              <Ionicons name="checkmark-circle" size={14} color={Colors.success} />
              <Text style={styles.verifiedText}>Verified</Text>
            </View>
          </View>
        </View>

        {/* Rider Information */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardIconWrap}>
              <Ionicons name="bicycle" size={20} color={Colors.primary} />
            </View>
            <View>
              <Text style={styles.cardTitle}>Rider Information</Text>
              <Text style={styles.cardSub}>Vehicle & Registration</Text>
            </View>
          </View>

          <View style={styles.divider} />

          <InfoRow label="Vehicle Type" value={user?.vehicleType ? VehicleTypeLabels[user.vehicleType] : 'Motorcycle'} />
          <InfoRow label="Make & Model" value="Yamaha MT-07" />
          <InfoRow label="License Plate" value="ABC-1234" valueColor={Colors.primary} />
        </View>

        {/* Insurance Coverage */}
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={styles.cardIconWrapSuccess}>
              <Ionicons name="shield-checkmark" size={20} color={Colors.success} />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardTitle}>Insurance Coverage</Text>
              <Text style={styles.cardSub}>Active Plan Details</Text>
            </View>
            <View style={styles.activePill}>
              <Text style={styles.activePillText}>Active</Text>
            </View>
          </View>

          <View style={styles.planBox}>
            <Text style={styles.planName}>Comprehensive Gig Shield</Text>
            <Text style={styles.planPrice}>$45/mo</Text>
            <Text style={styles.planSub}>Billed Monthly</Text>
          </View>

          <View style={styles.checklist}>
            <CheckItem label="Liability Coverage" />
            <CheckItem label="Collision & Comprehensive" />
            <CheckItem label="Medical Payments" />
          </View>

          <Pressable style={styles.policyButton}>
            <Text style={styles.policyButtonText}>View Full Policy</Text>
          </Pressable>
        </View>

        {/* Settings & Preferences */}
        <Text style={styles.sectionTitle}>Settings & Preferences</Text>
        <View style={styles.card}>
          {menuRows.map((row, idx) => (
            <React.Fragment key={row.label}>
              <MenuRow {...row} />
              {idx < menuRows.length - 1 && <View style={styles.divider} />}
            </React.Fragment>
          ))}
        </View>

        {/* Log Out */}
        <Pressable style={styles.logoutButton} onPress={handleLogout}>
          <Ionicons name="log-out-outline" size={20} color={Colors.danger} />
          <Text style={styles.logoutText}>Log Out</Text>
        </Pressable>

      </ScrollView>

      {/* Float SOS over content near bottom */}
      <View style={styles.sosContainer}>
         <SOSButton onPress={() => router.push('/sos')} size={56} />
      </View>
    </SafeAreaView>
  );
}

function InfoRow({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={[styles.infoValue, valueColor ? { color: valueColor, fontWeight: '600' } : {}]}>{value}</Text>
    </View>
  );
}

function CheckItem({ label }: { label: string }) {
  return (
    <View style={styles.checkItem}>
      <Ionicons name="checkmark" size={18} color={Colors.success} />
      <Text style={styles.checkText}>{label}</Text>
    </View>
  );
}

function MenuRow({ label, icon, onPress, danger, badge }: RowItem) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.menuRow, pressed && { opacity: 0.6 }]}
    >
      <Ionicons name={icon} size={20} color={danger ? Colors.danger : Colors.textSecondary} />
      <Text style={[styles.menuLabel, danger && { color: Colors.danger }]}>{label}</Text>
      
      {badge && (
        <View style={[styles.menuBadge, danger && { backgroundColor: Colors.danger }]}>
          <Text style={styles.menuBadgeText}>{badge}</Text>
        </View>
      )}
      <Ionicons name="chevron-forward" size={18} color={Colors.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  // Header
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  brandContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  brandText: {
    ...Typography.h4,
    color: Colors.textPrimary,
    letterSpacing: -0.3,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.successMuted,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.success,
  },
  liveText: {
    ...Typography.labelSM,
    color: Colors.success,
  },

  scroll: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxl,
    gap: Spacing.lg,
  },
  
  // Avatar Section
  avatarSection: {
    alignItems: 'center',
  },
  avatarCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  avatarInitial: {
    fontSize: 32,
    fontWeight: '700',
    color: Colors.primary,
  },
  userName: {
    ...Typography.h2,
    color: Colors.textPrimary,
  },
  userPhone: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
  },
  badgeRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  ratingBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  ratingText: {
    ...Typography.caption,
    color: '#ffffff',
    fontWeight: '600',
  },
  verifiedBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.successMuted,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 4,
    borderWidth: 1,
    borderColor: 'rgba(0,138,61,0.2)',
  },
  verifiedText: {
    ...Typography.caption,
    color: Colors.success,
    fontWeight: '600',
  },

  // Cards
  card: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  cardIconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardIconWrapSuccess: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: Colors.successMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cardTitle: {
    ...Typography.bodyLG,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  cardSub: {
    ...Typography.caption,
    color: Colors.textSecondary,
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
  },

  // Info Row
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: Spacing.xs,
  },
  infoLabel: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  infoValue: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
  },

  // Insurance Card Specifics
  activePill: {
    backgroundColor: Colors.success,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
  },
  activePillText: {
    ...Typography.caption,
    color: '#ffffff',
    fontWeight: '700',
  },
  planBox: {
    backgroundColor: Colors.primaryMuted,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    marginVertical: Spacing.md,
  },
  planName: {
    ...Typography.bodyMD,
    fontWeight: '600',
    color: Colors.textPrimary,
  },
  planPrice: {
    ...Typography.labelMD,
    color: Colors.primary,
    marginTop: 2,
  },
  planSub: {
    ...Typography.caption,
    color: Colors.textSecondary,
  },
  checklist: {
    gap: Spacing.xs,
    marginBottom: Spacing.md,
  },
  checkItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  checkText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  policyButton: {
    backgroundColor: Colors.primary,
    paddingVertical: 12,
    borderRadius: BorderRadius.full,
    alignItems: 'center',
  },
  policyButtonText: {
    ...Typography.labelMD,
    color: '#ffffff',
  },

  // Menu List
  sectionTitle: {
    ...Typography.h4,
    color: Colors.textPrimary,
    marginBottom: -Spacing.md,
  },
  menuRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  menuLabel: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    flex: 1,
    fontWeight: '500',
  },
  menuBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: BorderRadius.full,
  },
  menuBadgeText: {
    ...Typography.caption,
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 10,
  },

  // Logout
  logoutButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.sm,
    backgroundColor: Colors.dangerMuted,
    paddingVertical: Spacing.md,
    borderRadius: BorderRadius.full,
    borderWidth: 1,
    borderColor: 'rgba(226, 36, 31, 0.2)',
  },
  logoutText: {
    ...Typography.labelMD,
    color: Colors.danger,
  },
  
  sosContainer: {
    position: 'absolute',
    bottom: Spacing.xl,
    right: Spacing.lg,
  },
});
