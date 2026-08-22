// ============================================================
// RideShield — Signup / Create Account Screen
// ============================================================

import React, { useState, useCallback } from 'react';
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
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography } from '../../constants/theme';
import type { VehicleType } from '../../types/auth';
import { VehicleTypeLabels } from '../../types/auth';

const VEHICLE_OPTIONS: { type: VehicleType; icon: keyof typeof Ionicons.glyphMap }[] = [
  { type: 'two_wheeler', icon: 'bicycle-outline' },
  // { type: 'three_wheeler', icon: 'car-sport-outline' },
  // { type: 'four_wheeler', icon: 'car-outline' },
  { type: 'bicycle', icon: 'bicycle' },
];

interface FormErrors {
  fullName?: string;
  email?: string;
  password?: string;
  phone?: string;
}

export default function SignupScreen() {
  const router = useRouter();
  const { register, state, clearError } = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [phone, setPhone] = useState('');
  const [vehicleType, setVehicleType] = useState<VehicleType>('two_wheeler');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});

  const validate = useCallback((): boolean => {
    const newErrors: FormErrors = {};
    if (!fullName.trim()) newErrors.fullName = 'Full name is required';
    if (!email.trim()) newErrors.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      newErrors.email = 'Enter a valid email';
    if (!password) newErrors.password = 'Password is required';
    else if (password.length < 6)
      newErrors.password = 'Password must be at least 6 characters';
    if (!phone.trim()) newErrors.phone = 'Phone number is required';
    else if (!/^\+?[\d\s\-]{8,15}$/.test(phone))
      newErrors.phone = 'Enter a valid phone number';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [fullName, email, password, phone]);

  const handleSignup = useCallback(async () => {
    clearError();
    if (!validate()) return;
    try {
      await register({
        fullName: fullName.trim(),
        email: email.trim(),
        password,
        phone: phone.trim(),
        vehicleType,
      });
      router.replace('/(tabs)/home');
    } catch {
      // Error banner is rendered automatically via state.error
    }
  }, [fullName, email, password, phone, vehicleType, register, validate, clearError, router]);

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
            {/* Top Header */}
            <View style={styles.header}>
              <View style={styles.headerLeft}>
                <Pressable onPress={() => router.back()} style={styles.backButton}>
                  <Ionicons name="arrow-back" size={22} color="#1F2937" />
                </Pressable>
                <View style={styles.logoRow}>
                  <View style={styles.shieldBadge}>
                    <Ionicons name="shield-checkmark" size={16} color="#ffffff" />
                  </View>
                  <Text style={styles.appName}>RideShield</Text>
                </View>
              </View>
              <Pressable onPress={() => router.push('/settings' as any)} style={styles.settingsButton}>
                <Ionicons name="settings-outline" size={18} color="#6B7280" />
              </Pressable>
            </View>

            {/* Hero Titles */}
            <View style={styles.heroSection}>
              <Text style={styles.title}>Create Account</Text>
              <Text style={styles.subtitle}>
                Join thousands of riders protected on every shift.
              </Text>
            </View>

            {/* Global Error Banner */}
            {state.error && (
              <View style={styles.errorBanner}>
                <Ionicons name="alert-circle" size={16} color={Colors.danger} />
                <Text style={styles.errorBannerText}>{state.error}</Text>
              </View>
            )}

            {/* Full Name */}
            <InputField
              label="Full Name"
              icon="person-outline"
              placeholder="Raj Sharma"
              value={fullName}
              onChangeText={(v) => { setFullName(v); setErrors(e => ({ ...e, fullName: undefined })); }}
              error={errors.fullName}
              autoCapitalize="words"
            />

            {/* Email */}
            <InputField
              label="Email"
              icon="mail-outline"
              placeholder="raj@example.com"
              value={email}
              onChangeText={(v) => { setEmail(v); setErrors(e => ({ ...e, email: undefined })); }}
              error={errors.email}
              keyboardType="email-address"
              autoCapitalize="none"
            />

            {/* Password */}
            <View style={styles.fieldGroup}>
              <Text style={styles.fieldLabel}>Password</Text>
              <View style={[styles.inputWrapper, errors.password && styles.inputError]}>
                <Ionicons name="lock-closed-outline" size={18} color="#9CA3AF" style={styles.inputIcon} />
                <TextInput
                  style={styles.input}
                  placeholder="Min. 6 characters"
                  placeholderTextColor="#9CA3AF"
                  value={password}
                  onChangeText={(v) => { setPassword(v); setErrors(e => ({ ...e, password: undefined })); }}
                  secureTextEntry={!showPassword}
                />
                <Pressable onPress={() => setShowPassword(s => !s)} style={styles.eyeButton}>
                  <Ionicons
                    name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                    size={20}
                    color="#9CA3AF"
                  />
                </Pressable>
              </View>
              {errors.password && <Text style={styles.fieldError}>{errors.password}</Text>}
            </View>

            {/* Phone */}
            <InputField
              label="Phone Number"
              icon="call-outline"
              placeholder="+91 98765 43210"
              value={phone}
              onChangeText={(v) => { setPhone(v); setErrors(e => ({ ...e, phone: undefined })); }}
              error={errors.phone}
              keyboardType="phone-pad"
            />

            {/* Vehicle Type Options (2x2 Grid) */}
            <View style={styles.vehicleSection}>
              <Text style={styles.vehicleSectionTitle}>Select Vehicle Type</Text>
              <View style={styles.vehicleGrid}>
                {VEHICLE_OPTIONS.map((item) => {
                  const isSelected = vehicleType === item.type;
                  return (
                    <Pressable
                      key={item.type}
                      onPress={() => setVehicleType(item.type)}
                      style={[
                        styles.vehicleCard,
                        isSelected && styles.vehicleCardSelected,
                      ]}
                    >
                      <Ionicons
                        name={item.icon}
                        size={24}
                        color={isSelected ? Colors.primary : "#9CA3AF"}
                        style={styles.vehicleIcon}
                      />
                      <Text
                        style={[
                          styles.vehicleText,
                          isSelected && styles.vehicleTextSelected,
                        ]}
                      >
                        {VehicleTypeLabels[item.type]}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            {/* Footer Actions */}
            <View style={styles.footerSection}>
              <Pressable
                testID="signup-submit"
                onPress={handleSignup}
                style={({ pressed }) => [
                  styles.submitButton,
                  pressed && { transform: [{ scale: 0.98 }] },
                  state.isLoading && { opacity: 0.8 },
                ]}
                disabled={state.isLoading}
              >
                <Text style={styles.submitButtonText}>
                  {state.isLoading ? 'Creating Account...' : 'Create Account'}
                </Text>
              </Pressable>

              <Pressable onPress={() => router.back()} style={styles.loginRow}>
                <Text style={styles.loginText}>Already have an account? </Text>
                <Text style={styles.loginLink}>Login</Text>
              </Pressable>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ImageBackground>
  );
}

// ---------------------------------------------------------------------------
// Helper: InputField
// ---------------------------------------------------------------------------

interface InputFieldProps {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  placeholder: string;
  value: string;
  onChangeText: (v: string) => void;
  error?: string;
  keyboardType?: 'default' | 'email-address' | 'phone-pad';
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
}

function InputField({
  label,
  icon,
  placeholder,
  value,
  onChangeText,
  error,
  keyboardType = 'default',
  autoCapitalize = 'sentences',
}: InputFieldProps) {
  return (
    <View style={styles.fieldGroup}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <View style={[styles.inputWrapper, error && styles.inputError]}>
        <Ionicons name={icon} size={18} color="#9CA3AF" style={styles.inputIcon} />
        <TextInput
          style={styles.input}
          placeholder={placeholder}
          placeholderTextColor="#9CA3AF"
          value={value}
          onChangeText={onChangeText}
          keyboardType={keyboardType}
          autoCapitalize={autoCapitalize}
          autoCorrect={false}
        />
      </View>
      {error && <Text style={styles.fieldError}>{error}</Text>}
    </View>
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
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
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
    justifyContent: 'space-between',
    marginBottom: Spacing.xs,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
  },
  backButton: {
    padding: Spacing.xs,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  shieldBadge: {
    width: 28,
    height: 28,
    borderRadius: 8,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  appName: {
    fontSize: 20,
    fontWeight: '800',
    color: '#1F2937',
    letterSpacing: -0.5,
  },
  settingsButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#E5E7EB',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroSection: {
    marginBottom: Spacing.xs,
  },
  title: {
    fontSize: 32,
    fontWeight: '800',
    color: '#111827',
    letterSpacing: -0.5,
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 15,
    color: '#6B7280',
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
  fieldGroup: { gap: 6 },
  fieldLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: Spacing.md,
    height: 54,
  },
  inputError: { borderColor: Colors.danger },
  inputIcon: { marginRight: Spacing.sm },
  input: {
    flex: 1,
    color: '#111827',
    fontSize: 15,
    fontWeight: '500',
  },
  eyeButton: { padding: 4 },
  fieldError: {
    ...Typography.caption,
    color: Colors.danger,
  },
  // Vehicle Selection 2x2 Grid
  vehicleSection: {
    paddingTop: Spacing.xs,
    gap: Spacing.xs,
  },
  vehicleSectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#111827',
    marginBottom: 4,
  },
  vehicleGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
  },
  vehicleCard: {
    width: '48%',
    backgroundColor: '#ffffff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingVertical: Spacing.md,
    paddingHorizontal: Spacing.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  vehicleCardSelected: {
    borderColor: Colors.primary,
    backgroundColor: '#EFF6FF',
    borderWidth: 2,
  },
  vehicleIcon: {
    marginBottom: 6,
  },
  vehicleText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#4B5563',
    textAlign: 'center',
  },
  vehicleTextSelected: {
    color: Colors.primary,
    fontWeight: '700',
  },
  // Footer
  footerSection: {
    marginTop: Spacing.md,
    gap: Spacing.md,
  },
  submitButton: {
    backgroundColor: Colors.primary,
    borderRadius: 16,
    height: 56,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: Colors.primary,
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 14,
    elevation: 6,
  },
  submitButtonText: {
    color: '#ffffff',
    fontSize: 17,
    fontWeight: '700',
  },
  loginRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loginText: {
    fontSize: 14,
    color: '#4B5563',
  },
  loginLink: {
    fontSize: 14,
    color: Colors.primary,
    fontWeight: '700',
  },
});
