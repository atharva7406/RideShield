// ============================================================
// RideShield — Rides History Screen (Frosted Glass Glassmorphism)
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
  ImageBackground,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { shiftService } from '../../services/shiftService';
import { useAuth } from '../../store/authStore';
import { LoadingState } from '../../components/LoadingState';
import { ErrorState } from '../../components/ErrorState';
import type { RideHistoryItem } from '../../types/shift';

export default function HistoryScreen() {
  const router = useRouter();
  const { state: authState } = useAuth();
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

  const totalProtectedCount = rides.filter(r => r.status === 'COMPLETED' || r.status === 'ACTIVE').length;
  const totalPremiums = rides.reduce((acc, curr) => acc + curr.premiumInr, 0);

  const renderHeader = () => (
    <View style={styles.headerContent}>
      {/* Coverage History Title */}
      <View style={styles.titleSection}>
        <Text style={styles.headerTitleText}>Your Coverage History</Text>
        <Text style={styles.headerSubtitleText}>Review past rides and insurance details.</Text>
      </View>

      {/* Summary Cards Grid */}
      <View style={styles.summaryGrid}>
        {/* Card 1: Protected Rides */}
        <View style={styles.summaryCardPrimary}>
          <View style={styles.iconCircleWhite}>
            <Ionicons name="shield" size={20} color="#ffffff" />
          </View>
          <View>
            <Text style={styles.summaryValuePrimary}>{totalProtectedCount}</Text>
            <Text style={styles.summaryLabelPrimary}>Protected Rides</Text>
          </View>
        </View>

        {/* Card 2: Total Premiums */}
        <View style={styles.summaryCardSecondary}>
          <View style={styles.iconCircleDark}>
            <Ionicons name="wallet-outline" size={20} color="#0f172a" />
          </View>
          <View>
            <Text style={styles.summaryValueSecondary}>₹{totalPremiums.toFixed(2)}</Text>
            <Text style={styles.summaryLabelSecondary}>Total Premiums</Text>
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

  const renderFooter = () => (
    <View style={styles.footerNote}>
      <Ionicons name="sparkles" size={22} color="rgba(255, 255, 255, 0.7)" />
      <Text style={styles.footerNoteText}>
        All rides are automatically secured{'\n'}by your active coverage plan.
      </Text>
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
        onCardPress={() => router.push({ pathname: '/ride-details', params: { shiftId: item.id } })}
        onClaimPress={() => router.push({ pathname: '/ride-details', params: { shiftId: item.id } })}
        onTrackPress={() => router.push('/live-ride')}
        onEndShiftPress={() => handleEndActiveShift(item.id)}
      />
    ),
    [router, handleEndActiveShift]
  );

  if (loading) return <LoadingState fullScreen message="Loading rides…" />;
  if (error) return <ErrorState message={error} onRetry={fetchHistory} />;

  return (
    <View style={styles.container}>
      {/* Dark City Background */}
      <ImageBackground
        source={require('../../../assets/hero-bg.jpg')}
        style={StyleSheet.absoluteFillObject}
      >
        <View style={styles.darkOverlay} />
      </ImageBackground>

      <SafeAreaView style={styles.safe} edges={['top']}>
        {/* Fixed Top Bar */}
        <View style={styles.topBar}>
          <View style={styles.brandGroup}>
            <Ionicons name="shield-checkmark" size={24} color="#0058bc" />
            <Text style={styles.brandTitle}>Rides</Text>
          </View>
          <Pressable onPress={() => router.push('/(tabs)/profile')} style={styles.profileBadge}>
            <Text style={styles.profileInitial}>
              {authState.user?.fullName?.[0]?.toUpperCase() ?? 'M'}
            </Text>
          </Pressable>
        </View>

        <FlatList
          data={filteredRides}
          keyExtractor={(item) => item.id}
          renderItem={renderItem}
          ListHeaderComponent={renderHeader}
          ListFooterComponent={renderFooter}
          contentContainerStyle={styles.list}
          showsVerticalScrollIndicator={false}
          ItemSeparatorComponent={() => <View style={styles.separator} />}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="bicycle-outline" size={48} color="rgba(255, 255, 255, 0.5)" />
              <Text style={styles.emptyText}>No rides found</Text>
            </View>
          }
        />
      </SafeAreaView>
    </View>
  );
}

function RideItemCard({
  item,
  onCardPress,
  onClaimPress,
  onTrackPress,
  onEndShiftPress,
}: {
  item: RideHistoryItem;
  onCardPress: () => void;
  onClaimPress: () => void;
  onTrackPress?: () => void;
  onEndShiftPress?: () => void;
}) {
  const hasIncident = item.incidentCount > 0;
  const isActive = item.status === 'ACTIVE';

  return (
    <Pressable onPress={onCardPress} style={cardStyles.card}>
      {/* Top Status Row */}
      <View style={cardStyles.topRow}>
        <View style={cardStyles.titleGroup}>
          <Text style={cardStyles.title}>
            {hasIncident ? "Uptown Connector" : item.id === 'h1' ? "Downtown Delivery Route" : "Suburban Loop"}
          </Text>
          <Text style={cardStyles.date}>
            {item.date} {item.startTime ? `• ${item.startTime} - ${item.endTime}` : ''}
          </Text>
        </View>

        {/* Status Badge */}
        {isActive ? (
          <View style={cardStyles.badgeActive}>
            <View style={cardStyles.dotBlue} />
            <Text style={cardStyles.badgeActiveText}>ACTIVE</Text>
          </View>
        ) : hasIncident ? (
          <View style={cardStyles.badgeIncident}>
            <View style={cardStyles.dotRed} />
            <Text style={cardStyles.badgeIncidentText}>INCIDENT</Text>
          </View>
        ) : (
          <View style={cardStyles.badgeProtected}>
            <Ionicons name="checkmark-circle" size={14} color="#005047" />
            <Text style={cardStyles.badgeProtectedText}>PROTECTED</Text>
          </View>
        )}
      </View>

      <View style={cardStyles.divider} />

      {/* Metrics Row */}
      <View style={cardStyles.metricsRow}>
        <View style={cardStyles.metricCol}>
          <Text style={cardStyles.metricLabel}>Duration</Text>
          <Text style={cardStyles.metricValue}>
            {item.duration} {hasIncident && <Text style={cardStyles.haltedText}>(Halted)</Text>}
          </Text>
        </View>

        <View style={cardStyles.metricCol}>
          <Text style={cardStyles.metricLabel}>Distance</Text>
          <Text style={cardStyles.metricValue}>{item.distanceKm.toFixed(1)} km</Text>
        </View>

        <View style={[cardStyles.metricCol, { alignItems: 'flex-end' }]}>
          <Text style={cardStyles.metricLabel}>Premium</Text>
          <Text style={[cardStyles.metricValue, hasIncident ? cardStyles.premiumDanger : cardStyles.premiumPrimary]}>
            {hasIncident ? "Claim Initiated" : `₹${item.premiumInr.toFixed(2)}`}
          </Text>
        </View>
      </View>

      {/* Active Shift Buttons */}
      {isActive && (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
          <Pressable onPress={onTrackPress} style={[cardStyles.actionButton, { flex: 1, backgroundColor: '#0058bc' }]}>
            <Ionicons name="navigate-circle" size={18} color="#ffffff" />
            <Text style={[cardStyles.actionButtonText, { color: '#ffffff' }]}>Track Ride</Text>
          </Pressable>
          
          <Pressable onPress={onEndShiftPress} style={[cardStyles.actionButton, { flex: 1, borderColor: '#ef4444' }]}>
            <Ionicons name="stop-circle-outline" size={18} color="#ef4444" />
            <Text style={[cardStyles.actionButtonText, { color: '#ef4444' }]}>End Shift</Text>
          </Pressable>
        </View>
      )}

      {/* Quick Action Button for Incident */}
      {hasIncident && (
        <Pressable onPress={onClaimPress} style={cardStyles.actionButton}>
          <Ionicons name="document-text-outline" size={18} color="#0058bc" />
          <Text style={cardStyles.actionButtonText}>View Claim Status</Text>
        </Pressable>
      )}
    </Pressable>
  );
}

const cardStyles = StyleSheet.create({
  card: {
    backgroundColor: 'rgba(255, 255, 255, 0.88)',
    borderRadius: 24,
    padding: 16,
    gap: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.6)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 3,
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  titleGroup: {
    flex: 1,
    paddingRight: 8,
  },
  title: {
    fontSize: 18,
    fontWeight: '800',
    color: '#181c23',
    letterSpacing: -0.2,
  },
  date: {
    fontSize: 12,
    fontWeight: '500',
    color: '#414755',
    marginTop: 2,
  },
  badgeProtected: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(98, 250, 227, 0.25)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    gap: 4,
    borderWidth: 1,
    borderColor: 'rgba(98, 250, 227, 0.6)',
  },
  badgeProtectedText: {
    fontSize: 11,
    color: '#005047',
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  badgeActive: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#e0f2fe',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    gap: 4,
    borderWidth: 1,
    borderColor: '#bae6fd',
  },
  dotBlue: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#0284c7',
  },
  badgeActiveText: {
    fontSize: 11,
    color: '#0369a1',
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  badgeIncident: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fee2e2',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    gap: 4,
    borderWidth: 1,
    borderColor: '#fecaca',
  },
  dotRed: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#dc2626',
  },
  badgeIncidentText: {
    fontSize: 11,
    color: '#991b1b',
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  divider: {
    height: 1,
    width: '100%',
    backgroundColor: 'rgba(0, 0, 0, 0.08)',
    marginVertical: 4,
  },
  metricsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  metricCol: {
    flex: 1,
  },
  metricLabel: {
    fontSize: 11,
    color: '#414755',
    fontWeight: '500',
    marginBottom: 2,
  },
  metricValue: {
    fontSize: 15,
    color: '#181c23',
    fontWeight: '600',
  },
  haltedText: {
    color: '#dc2626',
    fontSize: 11,
  },
  premiumPrimary: {
    color: '#0058bc',
    fontWeight: '800',
  },
  premiumDanger: {
    color: '#dc2626',
    fontWeight: '700',
  },
  actionButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ffffff',
    paddingVertical: 10,
    borderRadius: 12,
    gap: 6,
    borderWidth: 1,
    borderColor: '#e2e8f0',
    marginTop: 4,
  },
  actionButtonText: {
    fontSize: 13,
    color: '#0058bc',
    fontWeight: '600',
  },
});

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#181c23',
  },
  darkOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.55)',
  },
  safe: {
    flex: 1,
  },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  brandGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  brandTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: -0.3,
  },
  profileBadge: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: '#0058bc',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: 'rgba(255, 255, 255, 0.3)',
  },
  profileInitial: {
    fontSize: 14,
    fontWeight: '700',
    color: '#ffffff',
  },
  list: {
    paddingHorizontal: 20,
    paddingBottom: 100,
  },
  headerContent: {
    gap: 16,
    paddingTop: 8,
    paddingBottom: 16,
  },
  titleSection: {
    gap: 4,
    marginTop: 4,
  },
  headerTitleText: {
    fontSize: 28,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: -0.4,
  },
  headerSubtitleText: {
    fontSize: 15,
    color: 'rgba(255, 255, 255, 0.8)',
  },
  summaryGrid: {
    flexDirection: 'row',
    gap: 12,
  },
  summaryCardPrimary: {
    flex: 1,
    backgroundColor: '#0058bc',
    borderRadius: 24,
    padding: 16,
    justifyContent: 'space-between',
    minHeight: 120,
    shadowColor: '#0058bc',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  iconCircleWhite: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  summaryValuePrimary: {
    fontSize: 32,
    fontWeight: '700',
    color: '#ffffff',
    letterSpacing: -0.5,
  },
  summaryLabelPrimary: {
    fontSize: 13,
    fontWeight: '600',
    color: 'rgba(255, 255, 255, 0.9)',
    marginTop: 2,
  },
  summaryCardSecondary: {
    flex: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.88)',
    borderRadius: 24,
    padding: 16,
    justifyContent: 'space-between',
    minHeight: 120,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.6)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  iconCircleDark: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(24, 28, 35, 0.08)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  summaryValueSecondary: {
    fontSize: 28,
    fontWeight: '700',
    color: '#181c23',
    letterSpacing: -0.5,
  },
  summaryLabelSecondary: {
    fontSize: 13,
    fontWeight: '600',
    color: '#414755',
    marginTop: 2,
  },
  filterRow: {
    flexDirection: 'row',
    gap: 10,
  },
  filterPill: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.85)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.5)',
  },
  filterPillActive: {
    backgroundColor: '#006b5f',
    borderColor: '#006b5f',
  },
  filterPillText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#414755',
  },
  filterPillTextActive: {
    color: '#ffffff',
    fontWeight: '700',
  },
  separator: {
    height: 12,
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 48,
    gap: 12,
  },
  emptyText: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.7)',
    fontWeight: '500',
  },
  footerNote: {
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
    marginBottom: 16,
    gap: 8,
  },
  footerNoteText: {
    fontSize: 12,
    color: 'rgba(255, 255, 255, 0.65)',
    textAlign: 'center',
    lineHeight: 18,
  },
});
