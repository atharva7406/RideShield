// ============================================================
// RideShield — Phone Verification Screen
// ============================================================

import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ImageBackground,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../store/authStore';
import { authService } from '../../services/auth';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography } from '../../constants/theme';

export default function VerifyScreen() {
  const router = useRouter();
  const { state: authState, refreshUser, logout } = useAuth();
  const initialPhone = authState.user?.phone || '';
  const isSubmitting = useRef(false);

  const [phone, setPhone] = useState(initialPhone);
  const [code, setCode] = useState('');
  const [isOtpSent, setIsOtpSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSendOtp = useCallback(async () => {
    if (isSubmitting.current) return;
    setError(null);
    if (!/^\+?[\d\s\-]{8,15}$/.test(phone)) {
      setError('Please enter a valid phone number');
      return;
    }
    isSubmitting.current = true;
    setIsLoading(true);
    try {
      await authService.sendOtp(phone);
      setIsOtpSent(true);
    } catch (err: any) {
      setError(err.message || 'Failed to send OTP code');
    } finally {
      setIsLoading(false);
      isSubmitting.current = false;
    }
  }, [phone]);

  const handleVerifyOtp = useCallback(async () => {
    if (isSubmitting.current) return;
    setError(null);
    if (!code || code.length !== 6) {
      setError('Please enter a valid 6-digit code');
      return;
    }
    isSubmitting.current = true;
    setIsLoading(true);
    try {
      await authService.verifyOtp(phone, code);
      await refreshUser();
    } catch (err: any) {
      setError(err.message || 'Verification failed. Please try again.');
    } finally {
      setIsLoading(false);
      isSubmitting.current = false;
    }
  }, [phone, code, refreshUser]);

  const handleBackToLogin = useCallback(async () => {
    await logout();
    router.replace('/(auth)/login');
  }, [logout, router]);

  return (
    <ImageBackground
      source={{
        uri: 'https://lh3.googleusercontent.com/aida/AEtjO1X5coJCgOHgQNg8CGqeEUNgLQgRqnPO927D-_MuE1lO0d-FWMyOe8wgHwv0BRz2dH_RGSziMJA8tucN3vgvQ9UfnNxjcHJD2ME-0kY1xvPwMsizVkbep9jgxHsGLFjxmlMtzplGprOXhQkXBIwpn2ppbngPLfHHUFWXUOG-v-VW8P0RqW68MYIs4YlmpJpzIu1W6YPcPLRP_OPxpHTVKPBvkq3Th9wdJfblYzN6jTM07vxKecxvpSPVuAkb',
      }}
      style={styles.backgroundImage}
      resizeMode="cover"
    >
      <View style={styles.whiteOverlay} />

      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView
          style={styles.flex}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {/* Header */}
            <View style={styles.header}>
              <Pressable onPress={handleBackToLogin} style={styles.backButton}>
                <Ionicons name="arrow-back" size={22} color="#1F2937" />
              </Pressable>
              <Text style={styles.headerTitle}>Phone Verification</Text>
            </View>

            {/* Sub-Header / Description */}
            <View style={styles.heroSection}>
              <Ionicons
                name="shield-checkmark-outline"
                size={64}
                color={Colors.primary}
                style={styles.heroIcon}
              />
              <Text style={styles.title}>Secure Your Account</Text>
              <Text style={styles.subtitle}>
                We require a verified mobile number to send immediate WhatsApp notifications and SMS alerts in the event of an accident.
              </Text>
            </View>

            {/* Error Message */}
            {error && (
              <View style={styles.errorBanner}>
                <Ionicons name="alert-circle" size={16} color={Colors.danger} />
                <Text style={styles.errorBannerText}>{error}</Text>
              </View>
            )}

            {/* Card Content */}
            <View style={styles.card}>
              {/* Phone Input / Edit */}
              <View style={styles.fieldGroup}>
                <Text style={styles.fieldLabel}>Mobile Number</Text>
                <View style={[styles.inputWrapper, isOtpSent && styles.disabledInput]}>
                  <Ionicons name="call-outline" size={18} color="#9CA3AF" style={styles.inputIcon} />
                  <TextInput
                    style={styles.input}
                    placeholder="+91 98765 43210"
                    placeholderTextColor="#9CA3AF"
                    value={phone}
                    onChangeText={setPhone}
                    keyboardType="phone-pad"
                    editable={!isOtpSent && !isLoading}
                  />
                  {isOtpSent && (
                    <Pressable
                      onPress={() => setIsOtpSent(false)}
                      style={styles.editButton}
                      disabled={isLoading}
                    >
                      <Text style={styles.editButtonText}>Edit</Text>
                    </Pressable>
                  )}
                </View>
              </View>

              {/* Send Button or OTP Code input */}
              {!isOtpSent ? (
                <Pressable
                  onPress={handleSendOtp}
                  style={({ pressed }) => [
                    styles.primaryButton,
                    pressed && { transform: [{ scale: 0.98 }] },
                    isLoading && { opacity: 0.8 },
                  ]}
                  disabled={isLoading}
                >
                  <Text style={styles.primaryButtonText}>
                    {isLoading ? 'Sending Code...' : 'Send Verification OTP'}
                  </Text>
                </Pressable>
              ) : (
                <>
                  <View style={styles.fieldGroup}>
                    <Text style={styles.fieldLabel}>Verification Code</Text>
                    <View style={styles.inputWrapper}>
                      <Ionicons name="key-outline" size={18} color="#9CA3AF" style={styles.inputIcon} />
                      <TextInput
                        style={styles.input}
                        placeholder="Enter 6-digit code"
                        placeholderTextColor="#9CA3AF"
                        value={code}
                        onChangeText={setCode}
                        keyboardType="number-pad"
                        maxLength={6}
                        editable={!isLoading}
                      />
                    </View>
                    <Pressable onPress={handleSendOtp} style={styles.resendLink} disabled={isLoading}>
                      <Text style={styles.resendLinkText}>Resend code</Text>
                    </Pressable>
                  </View>

                  <Pressable
                    onPress={handleVerifyOtp}
                    style={({ pressed }) => [
                      styles.primaryButton,
                      pressed && { transform: [{ scale: 0.98 }] },
                      isLoading && { opacity: 0.8 },
                    ]}
                    disabled={isLoading}
                  >
                    <Text style={styles.primaryButtonText}>
                      {isLoading ? 'Verifying...' : 'Verify & Log In'}
                    </Text>
                  </Pressable>
                </>
              )}
            </View>

            <View style={styles.footer}>
              <View style={styles.securityBadge}>
                <Ionicons name="lock-closed" size={12} color="#00C2A8" />
                <Text style={styles.securityText}>ENCRYPTED CONNECTION</Text>
              </View>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ImageBackground>
  );
}

const styles = StyleSheet.create({
  backgroundImage: {
    flex: 1,
    width: '100%',
    height: '100%',
  },
  whiteOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255, 255, 255, 0.96)',
  },
  safe: { flex: 1 },
  flex: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxl,
    gap: Spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    marginBottom: Spacing.xs,
  },
  backButton: {
    padding: Spacing.xs,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#1F2937',
  },
  heroSection: {
    alignItems: 'center',
    textAlign: 'center',
    marginVertical: Spacing.sm,
    gap: 8,
  },
  heroIcon: {
    marginBottom: 8,
  },
  title: {
    fontSize: 26,
    fontWeight: '800',
    color: '#111827',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    lineHeight: 20,
    paddingHorizontal: Spacing.sm,
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.dangerMuted,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    gap: Spacing.sm,
    borderWidth: 1,
    borderColor: 'rgba(255,59,48,0.3)',
  },
  errorBannerText: {
    ...Typography.bodySM,
    color: Colors.danger,
    flex: 1,
  },
  card: {
    backgroundColor: '#ffffff',
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 2,
  },
  fieldGroup: { gap: 6 },
  fieldLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#374151',
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: Spacing.md,
    height: 52,
  },
  disabledInput: {
    backgroundColor: '#F3F4F6',
  },
  inputIcon: { marginRight: Spacing.sm },
  input: {
    flex: 1,
    color: '#111827',
    fontSize: 15,
    fontWeight: '600',
  },
  editButton: {
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  editButtonText: {
    color: Colors.primary,
    fontWeight: '700',
    fontSize: 14,
  },
  resendLink: {
    alignSelf: 'flex-end',
    marginTop: 2,
  },
  resendLinkText: {
    color: Colors.primary,
    fontWeight: '700',
    fontSize: 13,
  },
  primaryButton: {
    backgroundColor: Colors.primary,
    borderRadius: 12,
    height: 52,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
    elevation: 4,
    marginTop: Spacing.xs,
  },
  primaryButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '700',
  },
  footer: {
    marginTop: Spacing.md,
    alignItems: 'center',
  },
  securityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  securityText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#4B5563',
    letterSpacing: 1.0,
  },
});
