// ============================================================
// RideShield — Helmet Safety Acknowledgment Screen
// ============================================================
// Mandatory gate before starting a shift. There is no photo/ML check —
// the rider must explicitly check a red acknowledgment checkbox
// confirming they will wear a helmet at all times. The backend records
// this acknowledgment (POST /helmet/acknowledge) and it's spent the
// moment a shift actually starts, same server-authoritative gate as
// before, just with an honest input instead of a probabilistic guess.

import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { helmetService } from '../services/helmetService';
import { PrimaryButton } from '../components/PrimaryButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';

export default function HelmetCheckScreen() {
  const router = useRouter();
  const [acknowledged, setAcknowledged] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleContinue = useCallback(async () => {
    if (!acknowledged || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await helmetService.acknowledge();
      router.replace('/payment');
    } catch (err: any) {
      setError(err.message ?? 'Failed to record your acknowledgment. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }, [acknowledged, submitting, router]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Helmet Safety</Text>
        <View style={{ width: 24 }} />
      </View>

      <View style={styles.content}>
        <View style={styles.iconCircle}>
          <Ionicons name="warning" size={40} color={Colors.danger} />
        </View>
        <Text style={styles.title}>Mandatory Helmet Safety Acknowledgment</Text>
        <Text style={styles.subtitle}>
          This is a mandatory safety check — you can't start your shift without confirming it.
        </Text>

        <Pressable
          onPress={() => setAcknowledged(v => !v)}
          style={styles.checkboxRow}
          testID="helmet-acknowledgment-checkbox"
        >
          <View style={[styles.checkbox, acknowledged && styles.checkboxChecked]}>
            {acknowledged && <Ionicons name="checkmark" size={18} color="#ffffff" />}
          </View>
          <Text style={styles.checkboxLabel}>
            I confirm that I will wear a helmet at all times while riding during this shift.
            {' '}I understand that if it is found I was not wearing a helmet at the time of
            an accident, my claim will be rejected and void.
          </Text>
        </Pressable>

        {error && <Text style={styles.errorText}>{error}</Text>}

        <View style={styles.spacer} />
        <PrimaryButton
          label="Continue to Payment"
          onPress={handleContinue}
          disabled={!acknowledged}
          loading={submitting}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backButton: { padding: Spacing.xs },
  headerTitle: { ...Typography.bodyMD, color: Colors.textPrimary, fontWeight: '700' },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.lg,
  },
  iconCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: Colors.dangerMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.lg,
  },
  title: {
    ...Typography.h2,
    color: Colors.textPrimary,
    textAlign: 'center',
    marginBottom: Spacing.sm,
  },
  subtitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    textAlign: 'center',
    marginBottom: Spacing.lg,
  },
  checkboxRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing.md,
    backgroundColor: Colors.dangerMuted,
    borderWidth: 1,
    borderColor: Colors.danger,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
  },
  checkbox: {
    width: 26,
    height: 26,
    borderRadius: BorderRadius.sm,
    borderWidth: 2,
    borderColor: Colors.danger,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  checkboxChecked: {
    backgroundColor: Colors.danger,
  },
  checkboxLabel: {
    ...Typography.bodySM,
    color: Colors.textPrimary,
    flex: 1,
    lineHeight: 20,
  },
  errorText: {
    ...Typography.bodySM,
    color: Colors.danger,
    textAlign: 'center',
    marginTop: Spacing.sm,
  },
  spacer: { height: Spacing.lg },
});
