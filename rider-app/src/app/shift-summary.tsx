// ============================================================
// RideShield — Shift Summary Screen (Vibrant Style)
// ============================================================

import React, { useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRide } from '../store/rideStore';
import { PrimaryButton } from '../components/PrimaryButton';
import { SOSButton } from '../components/SOSButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../constants/theme';

export default function ShiftSummaryScreen() {
  const router = useRouter();
  const { state: rideState } = useRide();
  const summary = rideState.shiftSummary;

  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 600,
      useNativeDriver: true,
    }).start();
  }, [fadeAnim]);

  const handleDone = useCallback(() => {
    router.replace('/(tabs)/home');
  }, [router]);

  if (!summary) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.emptyContainer}>
          <Text style={styles.title}>No summary available</Text>
          <PrimaryButton label="GO HOME" onPress={handleDone} />
        </View>
      </SafeAreaView>
    );
  }

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
        {/* Hero */}
        <Animated.View style={[styles.hero, { opacity: fadeAnim }]}>
          <View style={styles.iconWrap}>
            <Ionicons name="checkmark" size={32} color={Colors.primary} />
          </View>
          <Text style={styles.title}>Shift Complete</Text>
          <Text style={styles.subtitle}>Great job! Here's a breakdown of your ride.</Text>
        </Animated.View>

        {/* Total Premium Banner */}
        <Animated.View style={[styles.premiumCard, { opacity: fadeAnim }]}>
          <Text style={styles.premiumLabel}>TOTAL PREMIUM</Text>
          <View style={styles.premiumRow}>
            <Text style={styles.premiumValue}>₹{summary.premiumPaidInr}</Text>
            <View style={styles.coveredBadge}>
              <Ionicons name="shield-checkmark" size={14} color="#ffffff" />
              <Text style={styles.coveredText}>Fully Covered</Text>
            </View>
          </View>
          {/* Abstract dark blue shapes would go here in background */}
        </Animated.View>

        {/* Stats Grid */}
        <Animated.View style={[{ opacity: fadeAnim }]}>
          <View style={styles.gridRow}>
            <View style={styles.gridCard}>
              <View style={styles.cardHeader}>
                <Ionicons name="time-outline" size={16} color={Colors.primary} />
                <Text style={styles.cardLabel}>Duration</Text>
              </View>
              <Text style={styles.cardValue}>{summary.duration}</Text>
            </View>

            <View style={styles.gridCard}>
              <View style={styles.cardHeader}>
                <Ionicons name="map-outline" size={16} color={Colors.primary} />
                <Text style={styles.cardLabel}>Distance</Text>
              </View>
              <Text style={styles.cardValue}>{summary.distanceKm.toFixed(1)} km</Text>
            </View>
          </View>

          <View style={styles.gridRow}>
            <View style={styles.gridCard}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardLabel}>Avg Speed</Text>
              </View>
              <Text style={styles.cardValue}>{Math.round(summary.avgSpeedKmh)} km/h</Text>
              <View style={[styles.mockChartLine, { borderColor: Colors.primary }]} />
            </View>

            <View style={styles.gridCard}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardLabel}>Peak Speed</Text>
              </View>
              <Text style={styles.cardValue}>{Math.round(summary.peakSpeedKmh)} km/h</Text>
              <View style={[styles.mockChartLine, { borderColor: Colors.warning }]} />
            </View>
          </View>

          <View style={styles.gridRow}>
            <View style={styles.gridCard}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardLabel}>Max G-Force</Text>
              </View>
              <Text style={styles.cardValue}>{summary.peakGForce.toFixed(2)} G</Text>
            </View>

            <View style={styles.gridCard}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardLabel}>Incidents</Text>
              </View>
              <Text style={[styles.cardValue, summary.incidentCount > 0 && { color: Colors.danger }]}>
                {summary.incidentCount} Log
              </Text>
            </View>
          </View>
        </Animated.View>

        {rideState.activeClaim && (
          <Animated.View style={{ opacity: fadeAnim, marginHorizontal: Spacing.lg, marginBottom: Spacing.sm }}>
            <PrimaryButton
              label="VIEW ACTIVE CLAIM"
              onPress={() => router.replace('/claim-status')}
              style={{ backgroundColor: Colors.primary }}
            />
          </Animated.View>
        )}

        <Animated.View style={{ opacity: fadeAnim }}>
          <PrimaryButton
            testID="summary-done"
            label="DONE"
            onPress={handleDone}
            style={styles.doneButton}
          />
        </Animated.View>
        
        {/* Float SOS over content near bottom */}
        <View style={styles.sosContainer}>
           <SOSButton onPress={() => router.push('/sos')} size={56} />
        </View>

      </ScrollView>
    </SafeAreaView>
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
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
  },
  // Hero
  hero: {
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.sm,
  },
  title: {
    ...Typography.h2,
    color: Colors.textPrimary,
    marginBottom: 4,
  },
  subtitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  // Premium Card
  premiumCard: {
    backgroundColor: '#002B49', // Very dark blue for contrast
    borderRadius: BorderRadius.xl,
    padding: Spacing.xl,
    marginBottom: Spacing.lg,
    ...Shadows.medium,
  },
  premiumLabel: {
    ...Typography.labelSM,
    color: 'rgba(255,255,255,0.7)',
    letterSpacing: 1.5,
    marginBottom: 4,
  },
  premiumRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  premiumValue: {
    fontSize: 40,
    fontWeight: '800',
    color: '#ffffff',
  },
  coveredBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 6,
  },
  coveredText: {
    ...Typography.caption,
    color: '#ffffff',
    fontWeight: '600',
  },
  // Grid
  gridRow: {
    flexDirection: 'row',
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  gridCard: {
    flex: 1,
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: Spacing.sm,
  },
  cardLabel: {
    ...Typography.labelSM,
    color: Colors.textSecondary,
  },
  cardValue: {
    ...Typography.h3,
    color: Colors.textPrimary,
  },
  mockChartLine: {
    height: 20,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderBottomLeftRadius: 10,
    marginTop: 8,
    opacity: 0.5,
  },
  doneButton: {
    marginTop: Spacing.lg,
  },
  sosContainer: {
    alignItems: 'flex-end',
    marginTop: Spacing.lg,
  },
});
