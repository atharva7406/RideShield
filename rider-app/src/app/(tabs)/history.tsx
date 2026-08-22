// ============================================================
// RideShield — History / Rides Screen
// ============================================================

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  Pressable,
  ListRenderItem,
  Platform,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { shiftService } from '../../services/shiftService';
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../../constants/theme';
import type { RideHistoryItem } from '../../types/shift';

export default function HistoryScreen() {
  const router = useRouter();
  const [rides, setRides] = useState<RideHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'All' | 'Protected' | 'Incidents'>('All');

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await shiftService.getRideHistory();
      setRides(data);
    } catch (err: any) {
      setError(err.message ?? 'Failed to load ride history.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const filteredRides = rides.filter(r => {
    if (activeTab === 'Protected') return r.coverageActive && r.incidentCount === 0;
    if (activeTab === 'Incidents') return r.incidentCount > 0;
    return true;
  });

  const totalProtectedCount = rides.filter(r => r.coverageActive).length * 28 + 2;
  const totalPremiums = rides.reduce((acc, curr) => acc + curr.premiumInr, 0);

  const renderHeader = () => (
    <View style={styles.headerContent}>
      {/* Dashboard Summary */}
      <View style={styles.summarySection}>
        <Text style={styles.sectionTitle}>Your Coverage History</Text>
        <Text style={styles.sectionSubtitle}>Review past rides and insurance details.</Text>

        <View style={styles.summaryGrid}>
          {/* Card 1: Protected Rides */}
          <View style={styles.summaryCardPrimary}>
            <Ionicons name="shield" size={24} color="#ffffff" style={styles.cardIcon} />
            <Text style={styles.summaryCardValuePrimary}>{totalProtectedCount}</Text>
            <Text style={styles.summaryCardLabelPrimary}>Protected Rides</Text>
          </View>

          {/* Card 2: Total Premiums */}
          <View style={styles.summaryCardSecondary}>
            <Ionicons name="wallet-outline" size={24} color={Colors.textSecondary} style={styles.cardIcon} />
            <Text style={styles.summaryCardValue}>₹{totalPremiums * 5}</Text>
            <Text style={styles.summaryCardLabel}>Total Premiums</Text>
          </View>
        </View>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        {[
          { label: 'All Rides', key: 'All' },
          { label: 'Protected Only', key: 'Protected' },
          { label: 'Incidents', key: 'Incidents' },
        ].map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <Pressable
              key={tab.key}
              onPress={() => setActiveTab(tab.key as any)}
              style={[styles.filterPill, isActive && styles.filterPillActive]}
            >
              <Text style={[styles.filterPillText, isActive && styles.filterPillTextActive]}>
                {tab.label}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );

  const handleEndActiveShift = useCallback(async (shiftId: string) => {
    const performEnd = async () => {
      try {
        await shiftService.endShift(shiftId);
        fetchHistory();
      } catch (err: any) {
        Alert.alert('Error', err.message || 'Failed to end shift.');
      }
    };

    if (Platform.OS === 'web') {
      if (window.confirm('Are you sure you want to end your shift?')) {
        await performEnd();
      }
    } else {
      Alert.alert(
        'End Shift',
        'Are you sure you want to end your shift?',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'End Shift', style: 'destructive', onPress: performEnd }
        ]
      );
    }
  }, [fetchHistory]);

  const renderItem: ListRenderItem<RideHistoryItem> = useCallback(
    ({ item }) => (
      <RideItemCard
        item={item}
        onClaimPress={() => router.push('/claim-status')}
        onTrackPress={() => router.push('/live-ride')}
        onEndShiftPress={() => handleEndActiveShift(item.id)}
      />
    ),
    [router, handleEndActiveShift]
  );

  if (loading) return <LoadingState fullScreen message="Loading rides…" />;
  if (error) return <ErrorState message={error} onRetry={fetchHistory} />;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Fixed Top Bar */}
      <View style={styles.topBar}>
        <View style={styles.brandGroup}>
          <Ionicons name="shield-checkmark" size={24} color={Colors.primary} />
          <Text style={styles.brandTitle}>Rides</Text>
        </View>
        <Pressable onPress={() => router.push('/(tabs)/profile')} style={styles.profileBadge}>
          <Ionicons name="person-outline" size={18} color="#ffffff" />
        </Pressable>
      </View>

      <FlatList
        data={filteredRides}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        ListHeaderComponent={renderHeader}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="bicycle-outline" size={48} color={Colors.textMuted} />
            <Text style={styles.emptyText}>No rides found</Text>
          </View>
        }
      />
    </SafeAreaView>
  );
}

function RideItemCard({
  item,
  onClaimPress,
  onTrackPress,
  onEndShiftPress,
}: {
  item: RideHistoryItem;
  onClaimPress: () => void;
  onTrackPress?: () => void;
  onEndShiftPress?: () => void;
}) {
  const hasIncident = item.incidentCount > 0;
  const isActive = item.status === 'ACTIVE';

  return (
    <View style={cardStyles.card}>
      {/* Top Status Row */}
      <View style={cardStyles.topRow}>
        <View style={cardStyles.titleGroup}>
          <Text style={cardStyles.title}>
            {hasIncident ? "Uptown Connector" : item.id === 'h1' ? "Downtown Delivery Route" : "Suburban Loop"}
          </Text>
          <Text style={cardStyles.date}>{item.date}</Text>
        </View>

        {/* Status Badge */}
        {isActive ? (
          <View style={[cardStyles.badgeProtected, { backgroundColor: '#e8f0fe' }]}>
            <View style={[cardStyles.dotGreen, { backgroundColor: Colors.primary }]} />
            <Text style={[cardStyles.badgeProtectedText, { color: Colors.primary }]}>ACTIVE</Text>
          </View>
        ) : hasIncident ? (
          <View style={cardStyles.badgeIncident}>
            <View style={cardStyles.dotRed} />
            <Text style={cardStyles.badgeIncidentText}>INCIDENT</Text>
          </View>
        ) : (
          <View style={cardStyles.badgeProtected}>
            <View style={cardStyles.dotGreen} />
            <Text style={cardStyles.badgeProtectedText}>PROTECTED</Text>
          </View>
        )}
      </View>

      {/* Metrics Row */}
      <View style={cardStyles.metricsRow}>
        <View style={cardStyles.metricCol}>
          <Text style={cardStyles.metricLabel}>DURATION</Text>
          <Text style={cardStyles.metricValue}>
            {item.duration} {hasIncident && <Text style={cardStyles.haltedText}>(Halted)</Text>}
          </Text>
        </View>

        <View style={cardStyles.divider} />

        <View style={cardStyles.metricCol}>
          <Text style={cardStyles.metricLabel}>DISTANCE</Text>
          <Text style={cardStyles.metricValue}>{item.distanceKm.toFixed(1)} km</Text>
        </View>

        <View style={cardStyles.divider} />

        <View style={[cardStyles.metricCol, { alignItems: 'flex-end' }]}>
          <Text style={cardStyles.metricLabel}>PREMIUM</Text>
          <Text style={[cardStyles.metricValue, hasIncident ? cardStyles.premiumDanger : cardStyles.premiumPrimary]}>
            {hasIncident ? "Claim Initiated" : `₹${item.premiumInr}.00`}
          </Text>
        </View>
      </View>

      {/* Active Shift Buttons */}
      {isActive && (
        <View style={{ flexDirection: 'row', gap: Spacing.sm, marginTop: Spacing.xs }}>
          <Pressable onPress={onTrackPress} style={[cardStyles.claimButton, { flex: 1, backgroundColor: Colors.primary }]}>
            <Ionicons name="navigate-circle" size={18} color="#ffffff" />
            <Text style={[cardStyles.claimButtonText, { color: '#ffffff' }]}>Track Ride</Text>
          </Pressable>
          
          <Pressable onPress={onEndShiftPress} style={[cardStyles.claimButton, { flex: 1, borderColor: Colors.danger }]}>
            <Ionicons name="stop-circle-outline" size={18} color={Colors.danger} />
            <Text style={[cardStyles.claimButtonText, { color: Colors.danger }]}>End Shift</Text>
          </Pressable>
        </View>
      )}

      {/* Quick Action Button for Incident */}
      {hasIncident && (
        <Pressable onPress={onClaimPress} style={cardStyles.claimButton}>
          <Ionicons name="document-text-outline" size={18} color={Colors.primary} />
          <Text style={cardStyles.claimButtonText}>View Claim Status</Text>
        </Pressable>
      )}
    </View>
  );
}

const cardStyles = StyleSheet.create({
  card: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    gap: Spacing.md,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  titleGroup: {
    flex: 1,
    paddingRight: Spacing.sm,
  },
  title: {
    ...Typography.bodyLG,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  date: {
    ...Typography.caption,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  badgeProtected: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#e6f4ea',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  dotGreen: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#1e8e3e',
  },
  badgeProtectedText: {
    ...Typography.labelSM,
    color: '#1e8e3e',
    fontWeight: '700',
    fontSize: 10,
    letterSpacing: 0.5,
  },
  badgeIncident: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.dangerMuted,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  dotRed: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.danger,
  },
  badgeIncidentText: {
    ...Typography.labelSM,
    color: Colors.danger,
    fontWeight: '700',
    fontSize: 10,
    letterSpacing: 0.5,
  },
  metricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingTop: Spacing.xs,
  },
  metricCol: {
    flex: 1,
  },
  metricLabel: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    letterSpacing: 0.8,
    fontSize: 11,
    marginBottom: 2,
  },
  metricValue: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  haltedText: {
    color: Colors.danger,
    fontSize: 11,
  },
  divider: {
    width: 1,
    height: 28,
    backgroundColor: Colors.border,
    marginHorizontal: Spacing.xs,
  },
  premiumPrimary: {
    color: Colors.primary,
  },
  premiumDanger: {
    color: Colors.danger,
  },
  claimButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
    paddingVertical: Spacing.sm,
    borderRadius: BorderRadius.md,
    gap: 6,
    borderWidth: 1,
    borderColor: Colors.border,
    marginTop: 2,
  },
  claimButtonText: {
    ...Typography.labelMD,
    color: Colors.primary,
    fontWeight: '600',
  },
});

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  brandGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  brandTitle: {
    ...Typography.h3,
    color: Colors.primary,
    fontWeight: '700',
  },
  profileBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  list: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
  headerContent: {
    gap: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.md,
  },
  summarySection: {
    gap: Spacing.xs,
  },
  sectionTitle: {
    ...Typography.h2,
    color: Colors.textPrimary,
  },
  sectionSubtitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    marginBottom: Spacing.sm,
  },
  summaryGrid: {
    flexDirection: 'row',
    gap: Spacing.md,
  },
  summaryCardPrimary: {
    flex: 1,
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    gap: Spacing.xs,
    ...Shadows.soft,
  },
  cardIcon: {
    marginBottom: 4,
  },
  summaryCardValuePrimary: {
    ...Typography.h1,
    color: '#ffffff',
    fontSize: 28,
  },
  summaryCardLabelPrimary: {
    ...Typography.labelSM,
    color: 'rgba(255, 255, 255, 0.9)',
  },
  summaryCardSecondary: {
    flex: 1,
    backgroundColor: '#eeedf3',
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    gap: Spacing.xs,
  },
  summaryCardValue: {
    ...Typography.h1,
    color: Colors.textPrimary,
    fontSize: 28,
  },
  summaryCardLabel: {
    ...Typography.labelSM,
    color: Colors.textSecondary,
  },
  filterRow: {
    flexDirection: 'row',
    gap: Spacing.sm,
  },
  filterPill: {
    paddingHorizontal: Spacing.md,
    paddingVertical: 8,
    borderRadius: BorderRadius.full,
    backgroundColor: '#eeedf3',
  },
  filterPillActive: {
    backgroundColor: '#00e3fd',
  },
  filterPillText: {
    ...Typography.labelMD,
    color: Colors.textSecondary,
  },
  filterPillTextActive: {
    color: '#001f24',
    fontWeight: '700',
  },
  separator: {
    height: Spacing.md,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.xxl,
    gap: Spacing.sm,
  },
  emptyText: {
    ...Typography.h3,
    color: Colors.textSecondary,
  },
});
