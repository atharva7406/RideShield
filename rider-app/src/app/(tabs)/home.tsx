// ============================================================
// RideShield — Home Screen
// ============================================================

import React, { useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ImageBackground,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../../store/authStore';
import { useRide } from '../../store/rideStore';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../../constants/theme';
import { storage } from '../../utils/storage';

export default function HomeScreen() {
  const router = useRouter();
  const { state: authState, refreshUser } = useAuth();
  const { state: rideState } = useRide();

  useFocusEffect(
    useCallback(() => {
      refreshUser();
    }, [refreshUser])
  );

  const user = authState.user;
  const walletBalance = user?.walletBalance ?? 500.00;
  const hasActiveShift = rideState.activeShift?.status === 'active';
  const firstName = user?.fullName?.split(' ')[0] ?? 'Rider';

  const handleStartShift = useCallback(() => {
    router.push('/payment');
  }, [router]);

  const handleGoToLiveRide = useCallback(() => {
    router.push('/live-ride');
  }, [router]);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Top Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="shield-checkmark" size={24} color={Colors.primary} />
          <Text style={styles.headerBrand}>RideShield</Text>
        </View>
        <Pressable onPress={() => router.push('/(tabs)/profile')} style={styles.profileBadge}>
          <Text style={styles.profileInitial}>{firstName[0]?.toUpperCase() ?? 'R'}</Text>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Hero Banner */}
        <View style={styles.heroWrapper}>
          <ImageBackground
            source={{
              uri: 'https://lh3.googleusercontent.com/aida/AEtjO1VV1HFqNgIO3G8F_ub4pahkRcGuN4CeLizMeeRYRdU_sE1DxKLZQmxpwdSjj7ITmC_6hImU3K5FFqlYKZ38n-6vb11gIakY50huZqws35ZfF1ckeNZHTQdhY47oMGL25jXJk9XLErV2Y0cR5N21AFe7wUnt9pQYKKB7Z-x29wNY-LDsGE1iP5huoHzXdhvKIOWhMoWSJiajyB0tTH4nH6_5wgUy40M0qlfeeezR4XEGZr3dvqF3gMlzhmU',
            }}
            style={styles.heroBackground}
            imageStyle={styles.heroImageStyle}
          >
            <LinearGradient
              colors={['transparent', 'rgba(0, 30, 80, 0.4)', 'rgba(0, 20, 65, 0.88)']}
              style={styles.heroGradient}
            />
            <View style={styles.heroContent}>
              <View style={styles.heroTextGroup}>
                <Text style={styles.heroSub}>
                  {hasActiveShift ? "Active Shift" : "Today's Shift"}
                </Text>
                <Text style={styles.heroTitle}>
                  {hasActiveShift ? "Ready & Protected" : "Ready to Ride"}
                </Text>
              </View>

              <Pressable
                testID={hasActiveShift ? "go-to-live-ride" : "start-shift"}
                style={({ pressed }) => [
                  styles.startButton,
                  hasActiveShift && styles.liveButton,
                  pressed && { transform: [{ scale: 0.96 }] },
                ]}
                onPress={hasActiveShift ? handleGoToLiveRide : handleStartShift}
              >
                <Ionicons
                  name={hasActiveShift ? "navigate-circle" : "power-outline"}
                  size={22}
                  color={hasActiveShift ? "#ffffff" : "#001f24"}
                />
                <Text style={[styles.startButtonText, hasActiveShift && { color: '#ffffff' }]}>
                  {hasActiveShift ? "Dashboard" : "Start Shift"}
                </Text>
              </Pressable>
            </View>
          </ImageBackground>
        </View>

        {/* Wallet Balance Card */}
        <View style={styles.walletCard}>
          <View style={styles.walletTextGroup}>
            <Text style={styles.walletLabel}>WALLET BALANCE</Text>
            <Text style={styles.walletAmount}>₹{walletBalance.toFixed(2)}</Text>
          </View>
          <View style={styles.walletIconCircle}>
            <Ionicons name="wallet-outline" size={24} color={Colors.primary} />
          </View>
        </View>

        {/* Active Protection */}
        <View style={styles.protectionSection}>
          <Text style={styles.sectionTitle}>Active Protection</Text>
          <View style={styles.protectionList}>
            {/* Item 1 */}
            <View style={styles.protectionCard}>
              <View style={[styles.protectionIconCircle, { backgroundColor: '#ffdad5' }]}>
                <Ionicons name="bicycle-outline" size={22} color="#410001" />
              </View>
              <View style={styles.protectionTextGroup}>
                <Text style={styles.protectionTitle}>Vehicle Damage</Text>
                <Text style={styles.protectionDesc}>
                  Coverage up to ₹50,000 for accidental damage while on active delivery.
                </Text>
              </View>
              <Ionicons name="checkmark-circle" size={22} color={Colors.success} />
            </View>

            {/* Item 2 */}
            <View style={styles.protectionCard}>
              <View style={[styles.protectionIconCircle, { backgroundColor: '#d8e2ff' }]}>
                <Ionicons name="medical-outline" size={22} color="#001a41" />
              </View>
              <View style={styles.protectionTextGroup}>
                <Text style={styles.protectionTitle}>Personal Accident</Text>
                <Text style={styles.protectionDesc}>
                  Comprehensive medical coverage for injuries sustained on duty.
                </Text>
              </View>
              <Ionicons name="checkmark-circle" size={22} color={Colors.success} />
            </View>
          </View>
        </View>

        {/* Daily Insight Banner */}
        <View style={styles.insightCard}>
          <View style={styles.insightHeader}>
            <Ionicons name="bulb-outline" size={20} color="#ffffff" />
            <Text style={styles.insightTitle}>Daily Insight</Text>
          </View>
          <Text style={styles.insightBody}>
            Wet roads reported downtown. Reduce speed by 15% and increase braking distance to maintain optimal safety ratings today.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerBrand: {
    ...Typography.h3,
    color: Colors.primary,
    fontWeight: '700',
  },
  profileBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileInitial: {
    ...Typography.labelMD,
    color: '#ffffff',
    fontWeight: '700',
  },
  scroll: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.xxl,
    gap: Spacing.lg,
  },
  // Hero Banner
  heroWrapper: {
    height: 280,
    borderRadius: BorderRadius.xl,
    overflow: 'hidden',
    ...Shadows.medium,
  },
  heroBackground: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  heroImageStyle: {
    borderRadius: BorderRadius.xl,
  },
  heroGradient: {
    ...StyleSheet.absoluteFill,
  },
  heroContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    padding: Spacing.lg,
    zIndex: 10,
  },
  heroTextGroup: {
    flex: 1,
    paddingRight: Spacing.sm,
  },
  heroSub: {
    ...Typography.bodyMD,
    color: 'rgba(255, 255, 255, 0.8)',
    marginBottom: 2,
  },
  heroTitle: {
    ...Typography.h1,
    color: '#ffffff',
    fontSize: 28,
  },
  startButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#00daf3',
    paddingHorizontal: Spacing.lg,
    paddingVertical: 14,
    borderRadius: BorderRadius.full,
    gap: 8,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 6,
  },
  liveButton: {
    backgroundColor: Colors.success,
  },
  startButtonText: {
    ...Typography.labelMD,
    color: '#001f24',
    fontWeight: '700',
  },
  // Wallet Card
  walletCard: {
    backgroundColor: '#f4f3f8',
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  walletTextGroup: {
    gap: 2,
  },
  walletLabel: {
    ...Typography.labelSM,
    color: Colors.textSecondary,
    letterSpacing: 1.2,
  },
  walletAmount: {
    ...Typography.h2,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  walletIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Protection Section
  protectionSection: {
    gap: Spacing.md,
  },
  sectionTitle: {
    ...Typography.h4,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  protectionList: {
    gap: Spacing.sm,
  },
  protectionCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  protectionIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  protectionTextGroup: {
    flex: 1,
  },
  protectionTitle: {
    ...Typography.bodyLG,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  protectionDesc: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  // Insight Card
  insightCard: {
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.xs,
    ...Shadows.soft,
  },
  insightHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  insightTitle: {
    ...Typography.labelMD,
    color: '#ffffff',
    fontWeight: '700',
  },
  insightBody: {
    ...Typography.bodyMD,
    color: 'rgba(255, 255, 255, 0.95)',
    lineHeight: 22,
  },
});
