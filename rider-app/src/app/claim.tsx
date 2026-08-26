// ============================================================
// RideShield — Claim Screen
// ============================================================

import React, { useCallback, useEffect, useRef } from 'react';
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
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';
import { StatusBadge } from '../components/StatusBadge';

export default function ClaimScreen() {
  const router = useRouter();
  const { state: rideState } = useRide();
  const claim = rideState.activeClaim;

  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fadeAnim, { toValue: 1, duration: 400, useNativeDriver: true }),
      Animated.timing(slideAnim, { toValue: 0, duration: 400, useNativeDriver: true }),
    ]).start();
  }, [fadeAnim, slideAnim]);

  const handleViewClaimStatus = useCallback(() => {
    router.replace('/claim-status');
  }, [router]);

  // Fallback if accessed without a claim
  if (!claim) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.emptyContainer}>
          <Text style={styles.title}>No Active Claim</Text>
          <PrimaryButton label="GO HOME" onPress={() => router.replace('/(tabs)/home')} />
        </View>
      </SafeAreaView>
    );
  }

  const formattedTime = new Date(claim.incidentTime).toLocaleString();

  return (
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        <Animated.View
          style={[
            styles.hero,
            { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
          ]}
        >
          <View style={styles.checkCircle}>
            <Ionicons name="checkmark" size={56} color="#FFFFFF" />
          </View>
          <Text style={styles.title}>Claim Initiated</Text>
          <Text style={styles.subtitle}>
            Your accident information has been securely recorded.
          </Text>
        </Animated.View>

        <Animated.View
          style={[
            styles.detailsCard,
            { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
          ]}
        >
          <View style={styles.claimHeader}>
            <Text style={styles.claimIdLabel}>Claim ID</Text>
            <Text style={styles.claimId}>{claim.claimNumber}</Text>
          </View>

          <View style={styles.divider} />

          <View style={styles.capturedList}>
            <CapturedItem label="Location" value={`${claim.incidentLatitude.toFixed(4)}, ${claim.incidentLongitude.toFixed(4)}`} />
            <CapturedItem label="Time" value={formattedTime} />
            <CapturedItem label="Telemetry" value="High-res sensor data attached" />
            <CapturedItem label="Shift" value={`#${claim.shiftId.slice(-6)}`} />
          </View>

          <View style={styles.divider} />

          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Current Status:</Text>
            <StatusBadge label="Under Review" variant="warning" />
          </View>
        </Animated.View>

        <Animated.View style={{ opacity: fadeAnim }}>
          <PrimaryButton
            testID="view-claim"
            label="VIEW CLAIM STATUS"
            onPress={handleViewClaimStatus}
            style={styles.actionButton}
          />
        </Animated.View>
      </ScrollView>
    </SafeAreaView>
  );
}

function CapturedItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.capturedItem}>
      <Ionicons name="checkmark-circle" size={20} color={Colors.success} style={styles.capturedIcon} />
      <View>
        <Text style={styles.capturedLabel}>{label}</Text>
        <Text style={styles.capturedValue}>{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  scroll: {
    padding: Spacing.lg,
    paddingTop: Spacing.xxl,
    gap: Spacing.xl,
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.md,
  },
  hero: {
    alignItems: 'center',
    gap: Spacing.md,
  },
  checkCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: Colors.success,
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0px 0px 20px rgba(16, 185, 129, 0.5)',
    elevation: 10,
    marginBottom: Spacing.sm,
  },
  title: {
    ...Typography.h1,
    color: Colors.textPrimary,
    textAlign: 'center',
  },
  subtitle: {
    ...Typography.bodyLG,
    color: Colors.textSecondary,
    textAlign: 'center',
    paddingHorizontal: Spacing.lg,
  },
  detailsCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  claimHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  claimIdLabel: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  claimId: {
    ...Typography.h3,
    color: Colors.textPrimary,
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
  },
  capturedList: {
    gap: Spacing.md,
  },
  capturedItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.sm,
  },
  capturedIcon: {
    marginTop: 2,
  },
  capturedLabel: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  capturedValue: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statusLabel: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  actionButton: {
    marginTop: Spacing.md,
  },
});
