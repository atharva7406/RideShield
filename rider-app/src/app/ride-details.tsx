// ============================================================
// RideShield — Ride Details Screen
// ============================================================

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { shiftService } from '../services/shiftService';
import { claimService } from '../services/claimService';
import { apiClient } from '../services/api';
import { useRide } from '../store/rideStore';
import { PrimaryButton } from '../components/PrimaryButton';
import { LoadingState } from '../components/LoadingState';
import { ErrorState } from '../components/ErrorState';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../constants/theme';
import type { RideHistoryItem } from '../types/shift';

export default function RideDetailsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ shiftId: string }>();
  const shiftId = params.shiftId;
  const { setActiveClaim } = useRide();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ride, setRide] = useState<RideHistoryItem | null>(null);
  const [incident, setIncident] = useState<any | null>(null);
  const [claim, setClaim] = useState<any | null>(null);

  const loadData = useCallback(async () => {
    if (!shiftId) {
      setError('Shift ID missing');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. Fetch shift details from history
      const history = await shiftService.getRideHistory();
      const currentRide = history.find((r) => r.id === shiftId) || null;
      setRide(currentRide);

      // 2. Fetch incidents for this shift
      const incidents = await apiClient.get<any[]>('/incidents').catch(() => []);
      const shiftIncidents = incidents.filter((inc) => inc.shift_id === shiftId);
      shiftIncidents.sort((a, b) => new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime());
      const currentIncident = shiftIncidents[0] || null;
      setIncident(currentIncident);

      // 3. Fetch claim for this shift (match by incident_id or shift_id)
      const claims = await apiClient.get<any[]>('/claims').catch(() => []);
      const matchingClaim = claims.find(
        (c) => (currentIncident && c.incident_id === currentIncident.id) || c.shift_id === shiftId
      ) || null;
      setClaim(matchingClaim);
    } catch (err: any) {
      setError(err.message ?? 'Failed to load ride details.');
    } finally {
      setLoading(false);
    }
  }, [shiftId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleViewClaimTimeline = useCallback(() => {
    if (claim) {
      setActiveClaim({
        id: claim.id,
        claimNumber: claim.claim_number,
        shiftId: claim.shift_id,
        userId: claim.rider_id,
        status: claim.status.toLowerCase(),
        incidentTime: incident?.detected_at || new Date().toISOString(),
        incidentLatitude: incident?.latitude || 0,
        incidentLongitude: incident?.longitude || 0,
        telemetryCaptured: true,
        locationCaptured: true,
        createdAt: claim.created_at || new Date().toISOString(),
        updatedAt: claim.updated_at || new Date().toISOString(),
      });
      router.push('/claim-status');
    }
  }, [claim, incident, setActiveClaim, router]);

  if (loading) return <LoadingState fullScreen message="Loading ride details…" />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;

  const hasIncident = !!incident || (ride && ride.incidentCount > 0);
  const hasClaim = !!claim;

  return (
    <SafeAreaView style={styles.safe}>
      {/* Top Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Ride Details</Text>
        <View style={{ width: 40 }} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Main Card */}
        <View style={styles.heroCard}>
          <View style={styles.heroHeader}>
            <View>
              <Text style={styles.heroTitle}>
                {hasIncident ? "Uptown Delivery Loop" : "Standard Commercial Shift"}
              </Text>
              <Text style={styles.heroSub}>{ride?.date || 'Today'}</Text>
            </View>

            {ride?.status === 'ACTIVE' ? (
              <View style={[styles.badge, { backgroundColor: '#e8f0fe' }]}>
                <View style={[styles.dot, { backgroundColor: Colors.primary }]} />
                <Text style={[styles.badgeText, { color: Colors.primary }]}>ACTIVE</Text>
              </View>
            ) : hasIncident ? (
              <View style={[styles.badge, { backgroundColor: Colors.dangerMuted }]}>
                <View style={[styles.dot, { backgroundColor: Colors.danger }]} />
                <Text style={[styles.badgeText, { color: Colors.danger }]}>INCIDENT</Text>
              </View>
            ) : (
              <View style={[styles.badge, { backgroundColor: '#e6f4ea' }]}>
                <View style={[styles.dot, { backgroundColor: '#1e8e3e' }]} />
                <Text style={[styles.badgeText, { color: '#1e8e3e' }]}>PROTECTED</Text>
              </View>
            )}
          </View>

          <View style={styles.divider} />

          {/* Metrics Row */}
          <View style={styles.metricsGrid}>
            <View style={styles.metricCell}>
              <Text style={styles.metricLabel}>DISTANCE</Text>
              <Text style={styles.metricVal}>{(ride?.distanceKm ?? 0).toFixed(1)} km</Text>
            </View>
            <View style={styles.metricCell}>
              <Text style={styles.metricLabel}>DURATION</Text>
              <Text style={styles.metricVal}>{ride?.duration || '1h 12m'}</Text>
            </View>
            <View style={styles.metricCell}>
              <Text style={styles.metricLabel}>PREMIUM</Text>
              <Text style={styles.metricValPrimary}>₹{ride?.premiumInr ?? 5}.00</Text>
            </View>
          </View>
        </View>

        {/* Claim & Insurance Status Section */}
        <Text style={styles.sectionHeader}>Insurance & Claims</Text>
        
        {hasClaim ? (
          <View style={styles.claimCardSuccess}>
            <View style={styles.claimCardTop}>
              <View style={styles.claimIconWrap}>
                <Ionicons name="shield-checkmark" size={28} color={Colors.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.claimStatusBadge}>CLAIM FILED & PROCESSED</Text>
                <Text style={styles.claimNumber}>#{claim.claim_number}</Text>
              </View>
            </View>

            <View style={styles.divider} />

            <View style={styles.claimMetaRow}>
              <View>
                <Text style={styles.claimMetaLabel}>
                  {claim.status.toUpperCase() === 'APPROVED' || claim.status.toUpperCase() === 'PAID'
                    ? 'APPROVED PAYOUT'
                    : 'ESTIMATED PAYOUT'}
                </Text>
                <Text style={styles.claimMetaAmount}>₹{(claim.claimed_amount || 50000).toLocaleString('en-IN')}</Text>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                <Text style={styles.claimMetaLabel}>STATUS</Text>
                <Text style={styles.claimMetaStatus}>{claim.status.toUpperCase()}</Text>
              </View>
            </View>

            <PrimaryButton
              label="VIEW CLAIM TIMELINE & PAYOUT"
              onPress={handleViewClaimTimeline}
              style={{ marginTop: Spacing.md }}
            />
          </View>
        ) : hasIncident ? (
          <View style={styles.claimCardWarning}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
              <Ionicons name="warning-outline" size={24} color={Colors.danger} />
              <Text style={{ ...Typography.bodyLG, fontWeight: '700', color: Colors.danger }}>
                Incident Recorded
              </Text>
            </View>
            <Text style={{ ...Typography.bodyMD, color: Colors.textSecondary, marginVertical: 6 }}>
              Telemetry detected an impact during this ride. A claim has been logged for processing.
            </Text>
          </View>
        ) : (
          <View style={styles.claimCardClean}>
            <Ionicons name="checkmark-circle" size={32} color={Colors.success} />
            <View style={{ flex: 1 }}>
              <Text style={{ ...Typography.bodyLG, fontWeight: '700', color: Colors.textPrimary }}>
                100% Protected Shift
              </Text>
              <Text style={{ ...Typography.bodySM, color: Colors.textSecondary }}>
                No incidents reported. Complete commercial coverage was active until end of shift.
              </Text>
            </View>
          </View>
        )}

        {/* Sensor Telemetry Evidence Card */}
        <Text style={styles.sectionHeader}>Sensor Telemetry Evidence</Text>
        <View style={styles.evidenceCard}>
          <View style={styles.evidenceRow}>
            <Ionicons name="speedometer-outline" size={20} color={Colors.primary} />
            <Text style={styles.evidenceLabel}>Impact Force (G-Sensor):</Text>
            <Text style={styles.evidenceVal}>{incident ? `${incident.peak_g_force.toFixed(1)} G` : '1.1 G (Normal)'}</Text>
          </View>

          <View style={styles.evidenceRow}>
            <Ionicons name="location-outline" size={20} color={Colors.primary} />
            <Text style={styles.evidenceLabel}>GPS Coordinates:</Text>
            <Text style={styles.evidenceVal}>
              {incident ? `${incident.latitude.toFixed(4)}, ${incident.longitude.toFixed(4)}` : 'Recorded (10Hz)'}
            </Text>
          </View>

          <View style={styles.evidenceRow}>
            <Ionicons name="hardware-chip-outline" size={20} color={Colors.primary} />
            <Text style={styles.evidenceLabel}>AI Risk Assessment:</Text>
            <Text style={styles.evidenceVal}>
              {incident ? `High Confidence (${(incident.confidence_score * 100).toFixed(0)}%)` : 'Low Risk'}
            </Text>
          </View>
        </View>

        {/* Policy Information */}
        <Text style={styles.sectionHeader}>Policy Details</Text>
        <View style={styles.policyCard}>
          <View style={styles.policyRow}>
            <Text style={styles.policyLabel}>Policy Number</Text>
            <Text style={styles.policyVal}>POL-4A82F19E</Text>
          </View>
          <View style={styles.policyRow}>
            <Text style={styles.policyLabel}>Insurer Partner</Text>
            <Text style={styles.policyVal}>RideShield Micro-Insurance</Text>
          </View>
          <View style={styles.policyRow}>
            <Text style={styles.policyLabel}>Coverage Limit</Text>
            <Text style={styles.policyVal}>₹50,000.00 / Shift</Text>
          </View>
        </View>

      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
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
  // Hero Card
  heroCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadows.soft,
  },
  heroHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  heroTitle: {
    ...Typography.h3,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  heroSub: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  badgeText: {
    ...Typography.labelSM,
    fontWeight: '700',
    fontSize: 10,
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
  },
  metricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metricCell: {
    flex: 1,
  },
  metricLabel: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    fontSize: 11,
    marginBottom: 2,
  },
  metricVal: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  metricValPrimary: {
    ...Typography.bodyMD,
    color: Colors.primary,
    fontWeight: '700',
  },

  sectionHeader: {
    ...Typography.h3,
    color: Colors.textPrimary,
    marginTop: Spacing.sm,
    marginBottom: 2,
  },

  // Claim Cards
  claimCardSuccess: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.primary,
  },
  claimCardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  claimIconWrap: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  claimStatusBadge: {
    ...Typography.labelSM,
    color: Colors.primary,
    fontWeight: '700',
  },
  claimNumber: {
    ...Typography.h2,
    color: Colors.textPrimary,
  },
  claimMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  claimMetaLabel: {
    ...Typography.labelSM,
    color: Colors.textMuted,
  },
  claimMetaAmount: {
    ...Typography.h2,
    color: Colors.success,
  },
  claimMetaStatus: {
    ...Typography.bodyLG,
    color: Colors.primary,
    fontWeight: '700',
  },

  claimCardWarning: {
    backgroundColor: Colors.dangerMuted,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Colors.danger,
  },

  claimCardClean: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#e6f4ea',
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
  },

  // Evidence Card
  evidenceCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  evidenceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.sm,
  },
  evidenceLabel: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    flex: 1,
  },
  evidenceVal: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
  },

  // Policy Card
  policyCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  policyRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  policyLabel: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  policyVal: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
});
