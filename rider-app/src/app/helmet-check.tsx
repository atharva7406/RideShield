// ============================================================
// RideShield — Helmet Verification Screen
// ============================================================
// Mandatory gate before starting a shift: rider takes a selfie, the
// server (not this screen) decides pass/fail. This screen never sets
// helmet_worn itself — it only shows whatever the backend returned.

import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  Image,
  ActivityIndicator,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { helmetService, HelmetVerifyResult } from '../services/helmetService';
import { PrimaryButton } from '../components/PrimaryButton';
import { SecondaryButton } from '../components/SecondaryButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography } from '../constants/theme';

type Stage = 'intro' | 'preview' | 'checking' | 'passed' | 'failed';

export default function HelmetCheckScreen() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>('intro');
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [result, setResult] = useState<HelmetVerifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const takeSelfie = useCallback(async () => {
    setError(null);
    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      setError('Camera permission is required to verify your helmet.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      cameraType: ImagePicker.CameraType.front,
      quality: 0.7,
      base64: false,
    });
    if (!result.canceled && result.assets?.[0]) {
      setPhotoUri(result.assets[0].uri);
      setStage('preview');
    }
  }, []);

  const submitForVerification = useCallback(async () => {
    if (!photoUri) return;
    setStage('checking');
    setError(null);
    try {
      const verifyResult = await helmetService.verifySelfie(photoUri);
      setResult(verifyResult);
      setStage(verifyResult.helmetWorn ? 'passed' : 'failed');
    } catch (err: any) {
      setError(err.message ?? 'Helmet verification failed. Please try again.');
      setStage('preview');
    }
  }, [photoUri]);

  const retake = useCallback(() => {
    setPhotoUri(null);
    setResult(null);
    setError(null);
    setStage('intro');
  }, []);

  const proceedToPayment = useCallback(() => {
    router.replace('/payment');
  }, [router]);

  return (
    <SafeAreaView style={styles.safe}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>Helmet Check</Text>
        <View style={{ width: 24 }} />
      </View>

      <View style={styles.content}>
        {stage === 'intro' && (
          <>
            <View style={styles.iconCircle}>
              <Ionicons name="camera-outline" size={40} color={Colors.primary} />
            </View>
            <Text style={styles.title}>Verify you're wearing a helmet</Text>
            <Text style={styles.subtitle}>
              A quick selfie is required before every shift. This is a mandatory
              safety check — you can't start your shift without it.
            </Text>
            {error && <Text style={styles.errorText}>{error}</Text>}
            <View style={styles.spacer} />
            <PrimaryButton label="Take Selfie" onPress={takeSelfie} />
          </>
        )}

        {stage === 'preview' && photoUri && (
          <>
            <Image source={{ uri: photoUri }} style={styles.preview} />
            {error && <Text style={styles.errorText}>{error}</Text>}
            <View style={styles.spacer} />
            <PrimaryButton label="Submit for Verification" onPress={submitForVerification} />
            <View style={{ height: Spacing.sm }} />
            <SecondaryButton label="Retake Photo" onPress={retake} />
          </>
        )}

        {stage === 'checking' && (
          <>
            <ActivityIndicator size="large" color={Colors.primary} />
            <Text style={styles.subtitle}>Checking your photo…</Text>
          </>
        )}

        {stage === 'passed' && result && (
          <>
            <View style={[styles.iconCircle, { backgroundColor: Colors.successMuted }]}>
              <Ionicons name="checkmark-circle" size={40} color={Colors.success} />
            </View>
            <Text style={styles.title}>Helmet Verified</Text>
            <Text style={styles.subtitle}>{result.message}</Text>
            <Text style={styles.detailText}>
              Detected: {result.predictedClass.replace(/_/g, ' ')} ({(result.confidence * 100).toFixed(0)}% confidence)
            </Text>
            <View style={styles.spacer} />
            <PrimaryButton label="Continue to Payment" onPress={proceedToPayment} />
          </>
        )}

        {stage === 'failed' && result && (
          <>
            <View style={[styles.iconCircle, { backgroundColor: Colors.dangerMuted }]}>
              <Ionicons name="close-circle" size={40} color={Colors.danger} />
            </View>
            <Text style={styles.title}>No Helmet Detected</Text>
            <Text style={styles.subtitle}>{result.message}</Text>
            <View style={styles.spacer} />
            <PrimaryButton label="Try Again" onPress={retake} />
          </>
        )}
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
    backgroundColor: Colors.primaryMuted,
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
    marginBottom: Spacing.md,
  },
  detailText: {
    ...Typography.bodySM,
    color: Colors.textMuted,
    textAlign: 'center',
  },
  errorText: {
    ...Typography.bodySM,
    color: Colors.danger,
    textAlign: 'center',
    marginTop: Spacing.sm,
  },
  spacer: { height: Spacing.lg },
  preview: {
    width: 240,
    height: 240,
    borderRadius: BorderRadius.lg,
    marginBottom: Spacing.md,
  },
});
