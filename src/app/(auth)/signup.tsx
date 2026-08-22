// ============================================================
// RideShield — Signup Screen
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
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../../store/authStore';
import { PrimaryButton } from '../../components/PrimaryButton';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography } from '../../constants/theme';
import type { VehicleType } from '../../types/auth';
import { VehicleTypeLabels } from '../../types/auth';

const VEHICLE_OPTIONS: VehicleType[] = [
  'two_wheeler',
  'three_wheeler',
  'four_wheeler',
  'bicycle',
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
            <Pressable onPress={() => router.back()} style={styles.backButton}>
              <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
            </Pressable>
            <View style={styles.logoRow}>
              <Ionicons name="shield-checkmark" size={22} color={Colors.primary} />
              <Text style={styles.appName}>RideShield</Text>
            </View>
          </View>

          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>
            Join thousands of riders protected on every shift.
          </Text>

          {/* Global error */}
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
              <Ionicons name="lock-closed-outline" size={18} color={Colors.textSecondary} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                placeholder="Min. 6 characters"
                placeholderTextColor={Colors.textMuted}
                value={password}
                onChangeText={(v) => { setPassword(v); setErrors(e => ({ ...e, password: undefined })); }}
                secureTextEntry={!showPassword}
              />
              <Pressable onPress={() => setShowPassword(s => !s)} style={styles.eyeButton}>
                <Ionicons
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color={Colors.textSecondary}
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

          {/* Vehicle Type */}
          <View style={styles.fieldGroup}>
            <Text style={styles.fieldLabel}>Vehicle Type</Text>
            <View style={styles.vehicleGrid}>
              {VEHICLE_OPTIONS.map((option) => (
                <Pressable
                  key={option}
                  onPress={() => setVehicleType(option)}
                  style={[
                    styles.vehicleOption,
                    vehicleType === option && styles.vehicleOptionSelected,
                  ]}
                >
                  <Text
                    style={[
                      styles.vehicleOptionText,
                      vehicleType === option && styles.vehicleOptionTextSelected,
                    ]}
                  >
                    {VehicleTypeLabels[option]}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>

          <PrimaryButton
            testID="signup-submit"
            label="Create Account"
            onPress={handleSignup}
            loading={state.isLoading}
            style={styles.submitButton}
          />

          <Pressable onPress={() => router.back()} style={styles.loginRow}>
            <Text style={styles.loginText}>Already have an account? </Text>
            <Text style={styles.loginLink}>Login</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
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
        <Ionicons name={icon} size={18} color={Colors.textSecondary} style={styles.inputIcon} />
        <TextInput
          style={styles.input}
          placeholder={placeholder}
          placeholderTextColor={Colors.textMuted}
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
  safe: { flex: 1, backgroundColor: Colors.background },
  flex: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xl,
    gap: Spacing.md,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingTop: Spacing.md,
    marginBottom: Spacing.sm,
  },
  backButton: {
    padding: Spacing.xs,
    marginRight: Spacing.sm,
  },
  logoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  appName: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  title: {
    ...Typography.h1,
    color: Colors.textPrimary,
  },
  subtitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    marginTop: -Spacing.sm,
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
    ...Typography.labelMD,
    color: Colors.textSecondary,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingHorizontal: Spacing.md,
    height: 52,
  },
  inputError: { borderColor: Colors.danger },
  inputIcon: { marginRight: Spacing.sm },
  input: {
    flex: 1,
    color: Colors.textPrimary,
    fontSize: 15,
  },
  eyeButton: { padding: 4 },
  fieldError: {
    ...Typography.caption,
    color: Colors.danger,
  },
  vehicleGrid: {
    gap: Spacing.sm,
  },
  vehicleOption: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    paddingVertical: Spacing.sm,
    paddingHorizontal: Spacing.md,
  },
  vehicleOptionSelected: {
    borderColor: Colors.primary,
    backgroundColor: Colors.primaryMuted,
  },
  vehicleOptionText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  vehicleOptionTextSelected: {
    color: Colors.primary,
    fontWeight: '600',
  },
  submitButton: { marginTop: Spacing.sm },
  loginRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loginText: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
  },
  loginLink: {
    ...Typography.bodyMD,
    color: Colors.primary,
    fontWeight: '600',
  },
});
