// ============================================================
// RideShield — Claim Status Screen
// ============================================================

import React, { useState, useEffect, useCallback } from 'react';
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
import { useRide } from '../store/rideStore';
import { claimService, buildClaimTimeline } from '../services/claimService';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';
import type { ClaimTimelineStep } from '../types/claim';

export default function ClaimStatusScreen() {
  const router = useRouter();
  const { state: rideState } = useRide();
  const activeClaim = rideState.activeClaim;

  const [loading, setLoading] = useState(!activeClaim);
  const [error, setError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<ClaimTimelineStep[]>([]);

  const loadClaim = useCallback(async () => {
    if (!activeClaim?.id) {
      setError('No claim found.');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const claimData = await claimService.getClaim(activeClaim.id);
      setTimeline(buildClaimTimeline(claimData.status));
    } catch (err: any) {
      setError(err.message ?? 'Failed to load claim status.');
    } finally {
      setLoading(false);
    }
  }, [activeClaim]);

  useEffect(() => {
    loadClaim();
  }, [loadClaim]);

  if (loading) return <LoadingState fullScreen message="Loading claim status…" />;
  if (error) return <ErrorState message={error} onRetry={loadClaim} />;

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable onPress={() => router.replace('/(tabs)/home')} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Claim Status</Text>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Info Card */}
        <View style={styles.infoCard}>
          <View style={styles.infoTop}>
            <View>
              <Text style={styles.infoLabel}>CLAIM ID</Text>
              <Text style={styles.infoValue}>{activeClaim?.claimNumber}</Text>
            </View>
            <View style={styles.infoRight}>
              <Text style={styles.infoLabel}>SHIFT</Text>
              <Text style={styles.infoValue}>#{activeClaim?.shiftId?.slice(-6) ?? '—'}</Text>
            </View>
          </View>
          <View style={styles.infoDivider} />
          <View style={styles.infoRow}>
            <Ionicons name="location-outline" size={16} color={Colors.textSecondary} />
            <Text style={styles.infoText}>
              {activeClaim?.incidentLatitude.toFixed(4)}, {activeClaim?.incidentLongitude.toFixed(4)}
            </Text>
          </View>
          <View style={styles.infoRow}>
            <Ionicons name="time-outline" size={16} color={Colors.textSecondary} />
            <Text style={styles.infoText}>
              {activeClaim ? new Date(activeClaim.incidentTime).toLocaleString() : '—'}
            </Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>Timeline</Text>

        {/* Timeline */}
        <View style={styles.timelineContainer}>
          {timeline.map((step, index) => (
            <TimelineStep
              key={step.id}
              step={step}
              isLast={index === timeline.length - 1}
            />
          ))}
        </View>

        {/* Support Card */}
        <View style={styles.supportCard}>
          <Ionicons name="headset" size={24} color={Colors.primary} />
          <View style={styles.supportTextWrap}>
            <Text style={styles.supportTitle}>Need Help?</Text>
            <Text style={styles.supportText}>
              Our claims team is available 24/7. Reference your Claim ID when contacting support.
            </Text>
          </View>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

function TimelineStep({ step, isLast }: { step: ClaimTimelineStep; isLast: boolean }) {
  const isCompleted = step.status === 'completed';
  const isActive = step.status === 'active';
  const isPending = step.status === 'pending';

  const dotColor = isCompleted ? Colors.success : isActive ? Colors.primary : Colors.border;
  const icon = isCompleted ? 'checkmark' : isActive ? 'time' : 'ellipse';

  return (
    <View style={styles.timelineStep}>
      {/* Left rail */}
      <View style={styles.rail}>
        <View style={[styles.dot, { backgroundColor: isPending ? Colors.card : dotColor, borderColor: dotColor }]}>
          {!isPending && <Ionicons name={icon} size={12} color={isCompleted ? '#fff' : Colors.background} />}
        </View>
        {!isLast && (
          <View style={[styles.line, { backgroundColor: isCompleted ? Colors.success : Colors.border }]} />
        )}
      </View>

      {/* Content */}
      <View style={styles.stepContent}>
        <Text style={[styles.stepLabel, isActive && styles.stepLabelActive, isPending && styles.stepLabelPending]}>
          {step.label}
        </Text>
        <Text style={[styles.stepDesc, isPending && styles.stepDescPending]}>
          {step.description}
        </Text>
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
    gap: Spacing.lg,
  },
  // Info card
  infoCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  infoTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: Spacing.sm,
  },
  infoRight: {
    alignItems: 'flex-end',
  },
  infoLabel: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    letterSpacing: 1.2,
  },
  infoValue: {
    ...Typography.h3,
    color: Colors.textPrimary,
    marginTop: 2,
  },
  infoDivider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.sm,
  },
  infoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
    marginTop: Spacing.xs,
  },
  infoText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  sectionTitle: {
    ...Typography.h2,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
  },
  // Timeline
  timelineContainer: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  timelineStep: {
    flexDirection: 'row',
    minHeight: 70,
  },
  rail: {
    alignItems: 'center',
    width: 24,
    marginRight: Spacing.md,
  },
  dot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 2,
    marginTop: 2,
  },
  line: {
    flex: 1,
    width: 2,
    marginTop: -10,
    marginBottom: -4,
    zIndex: 1,
  },
  stepContent: {
    flex: 1,
    paddingBottom: Spacing.lg,
  },
  stepLabel: {
    ...Typography.bodyLG,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  stepLabelActive: {
    color: Colors.primary,
  },
  stepLabelPending: {
    color: Colors.textMuted,
  },
  stepDesc: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    marginTop: 2,
    lineHeight: 20,
  },
  stepDescPending: {
    color: Colors.textMuted,
  },
  // Support
  supportCard: {
    flexDirection: 'row',
    backgroundColor: Colors.primaryMuted,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    gap: Spacing.md,
    alignItems: 'flex-start',
    borderWidth: 1,
    borderColor: 'rgba(0,194,255,0.2)',
  },
  supportTextWrap: {
    flex: 1,
  },
  supportTitle: {
    ...Typography.bodyMD,
    fontWeight: '700',
    color: Colors.textPrimary,
    marginBottom: 4,
  },
  supportText: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    lineHeight: 18,
  },
});
