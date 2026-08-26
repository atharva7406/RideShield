// ============================================================
// RideShield — Login Screen
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
  Image,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../../store/authStore';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography } from '../../constants/theme';

export default function LoginScreen() {
  const router = useRouter();
  const { login, state, clearError } = useAuth();
  const isSubmitting = useRef(false);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});

  const validate = useCallback(() => {
    const newErrors: typeof errors = {};
    if (!email.trim()) newErrors.email = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      newErrors.email = 'Enter a valid email';
    if (!password) newErrors.password = 'Password is required';
    else if (password.length < 6)
      newErrors.password = 'Password must be at least 6 characters';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [email, password]);

  const handleLogin = useCallback(async () => {
    if (isSubmitting.current) return;
    clearError();
    if (!validate()) return;
    isSubmitting.current = true;
    try {
      await login({ email: email.trim(), password });
      router.replace('/(tabs)/home');
    } catch {
      // Error banner is rendered automatically via state.error
    } finally {
      isSubmitting.current = false;
    }
  }, [email, password, login, validate, clearError, router]);

  const handleSignup = useCallback(() => {
    router.push('/(auth)/signup');
  }, [router]);

  return (
    <ImageBackground
      source={require('../../../assets/login-bg.jpg')}
      style={styles.backgroundImage}
      blurRadius={4}
    >
      <LinearGradient
        colors={['rgba(0,0,0,0.35)', 'transparent', 'rgba(0,0,0,0.85)']}
        style={styles.gradientOverlay}
      />

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
            {/* Top Settings Button */}
            <View style={styles.topActions}>
              <Pressable style={styles.settingsButton}>
                <Ionicons name="settings-outline" size={20} color="#ffffff" />
              </Pressable>
            </View>

            {/* Branding Section */}
            <View style={styles.hero}>
              <View style={styles.logoWrapper}>
                <Image
                  source={{
                    uri: 'https://lh3.googleusercontent.com/aida/AEtjO1UIwoqmjhvEkSO66F3z0RL8JVfK3jHf_Iyll-7wVNM3CE2zBWXiUCVWyqDr4KFePzKcqPuu973K2-JKmkxutxzk6ILQ_1oPNtVV8N0E4XK1qiDJsCO_vHq9_ELZFtnJwRx_O9vH1VPSCIMKcf50tbAANGi14ALplKws8O8JLn5Nvdt629qk6nivzab6neja6uEwTeCLFoXlL9MkVvcdh3zz2LvTPZ3gyVYOmGJsDkEys80-IUpdd_h_ffPC',
                  }}
                  style={styles.logoImage}
                  resizeMode="contain"
                />
              </View>
              <Text style={styles.appName}>RideShield</Text>
              <Text style={styles.tagline}>Protection for every ride.</Text>
            </View>

            {/* Glassmorphism Card */}
            <View style={styles.glassCard}>
              {/* Global Error Banner */}
              {state.error && (
                <View style={styles.errorBanner}>
                  <Ionicons name="alert-circle" size={16} color={Colors.danger} />
                  <Text style={styles.errorBannerText}>{state.error}</Text>
                </View>
              )}

              {/* Phone or Email Field */}
              <View style={styles.fieldGroup}>
                <Text style={styles.blockLabel}>PHONE OR EMAIL</Text>
                <View style={[styles.inputWrapper, errors.email && styles.inputError]}>
                  <Ionicons name="person-outline" size={20} color="#9CA3AF" style={styles.inputIcon} />
                  <TextInput
                    testID="login-email"
                    style={styles.input}
                    placeholder="Enter your credential"
                    placeholderTextColor="#9CA3AF"
                    value={email}
                    onChangeText={(v) => {
                      setEmail(v);
                      setErrors((e) => ({ ...e, email: undefined }));
                    }}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    returnKeyType="next"
                  />
                </View>
                {errors.email && <Text style={styles.fieldError}>{errors.email}</Text>}
              </View>

              {/* Password Field */}
              <View style={styles.fieldGroup}>
                <Text style={styles.blockLabel}>PASSWORD</Text>
                <View style={[styles.inputWrapper, errors.password && styles.inputError]}>
                  <Ionicons name="lock-closed-outline" size={20} color="#9CA3AF" style={styles.inputIcon} />
                  <TextInput
                    testID="login-password"
                    style={styles.input}
                    placeholder="••••••••"
                    placeholderTextColor="#9CA3AF"
                    value={password}
                    onChangeText={(v) => {
                      setPassword(v);
                      setErrors((e) => ({ ...e, password: undefined }));
                    }}
                    secureTextEntry={!showPassword}
                    returnKeyType="done"
                    onSubmitEditing={handleLogin}
                  />
                  <Pressable onPress={() => setShowPassword((s) => !s)} style={styles.eyeButton}>
                    <Ionicons
                      name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                      size={20}
                      color="#9CA3AF"
                    />
                  </Pressable>
                </View>
                {errors.password && <Text style={styles.fieldError}>{errors.password}</Text>}
              </View>

              {/* Forgot Password Link */}
              <View style={styles.forgotRow}>
                <Pressable>
                  <Text style={styles.forgotText}>Forgot password?</Text>
                </Pressable>
              </View>

              {/* Submit Button */}
              <Pressable
                testID="login-submit"
                onPress={handleLogin}
                style={({ pressed }) => [
                  styles.loginButton,
                  pressed && { transform: [{ scale: 0.98 }] },
                  state.isLoading && { opacity: 0.8 },
                ]}
                disabled={state.isLoading}
              >
                {state.isLoading ? (
                  <Text style={styles.loginButtonText}>Logging in...</Text>
                ) : (
                  <>
                    <Text style={styles.loginButtonText}>Login securely</Text>
                    <Ionicons name="arrow-forward" size={20} color="#ffffff" />
                  </>
                )}
              </Pressable>
            </View>

            {/* Bottom Footer Area */}
            <View style={styles.footer}>
              <View style={styles.signupRow}>
                <Text style={styles.signupText}>New to RideShield? </Text>
                <Pressable testID="go-to-signup" onPress={handleSignup}>
                  <Text style={styles.signupLink}>Create Account</Text>
                </Pressable>
              </View>

              <View style={styles.securityBadge}>
                <Ionicons name="shield-checkmark" size={16} color="#00C2A8" />
                <Text style={styles.securityText}>BANK-GRADE ENCRYPTION</Text>
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
  gradientOverlay: {
    ...StyleSheet.absoluteFill,
  },
  safe: { flex: 1 },
  flex: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.xl,
  },
  topActions: {
    width: '100%',
    alignItems: 'flex-end',
    marginBottom: Spacing.xs,
  },
  settingsButton: {
    width: 38,
    height: 38,
    borderRadius: 19,
    backgroundColor: 'rgba(0,0,0,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Hero / Branding
  hero: {
    alignItems: 'center',
    marginBottom: Spacing.xl,
    width: '100%',
  },
  logoWrapper: {
    width: 96,
    height: 96,
    borderRadius: 24,
    backgroundColor: '#ffffff',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
    boxShadow: '0px 8px 16px rgba(0, 0, 0, 0.2)',
    elevation: 8,
  },
  logoImage: {
    width: 64,
    height: 64,
  },
  appName: {
    fontSize: 36,
    fontWeight: '800',
    color: '#ffffff',
    letterSpacing: -0.5,
    marginBottom: 4,
    textShadow: '0px 2px 4px rgba(0, 0, 0, 0.5)',
  },
  tagline: {
    fontSize: 15,
    color: 'rgba(255, 255, 255, 0.9)',
    fontWeight: '500',
    textShadow: '0px 1px 3px rgba(0, 0, 0, 0.4)',
  },
  // Glass Card
  glassCard: {
    width: '100%',
    backgroundColor: 'rgba(255, 255, 255, 0.92)',
    borderRadius: 32,
    padding: Spacing.xl,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.6)',
    boxShadow: '0px 16px 32px rgba(0, 0, 0, 0.22)',
    elevation: 12,
    gap: Spacing.lg,
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
  fieldGroup: {
    gap: 6,
  },
  blockLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#6B7280',
    letterSpacing: 0.8,
    marginLeft: 4,
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(249, 250, 251, 0.8)',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    paddingHorizontal: Spacing.md,
    height: 56,
  },
  inputError: {
    borderColor: Colors.danger,
  },
  inputIcon: {
    marginRight: Spacing.sm,
  },
  input: {
    flex: 1,
    color: '#1F2937',
    fontSize: 15,
    fontWeight: '500',
  },
  eyeButton: {
    padding: 4,
  },
  fieldError: {
    ...Typography.caption,
    color: Colors.danger,
    marginTop: 2,
  },
  forgotRow: {
    alignItems: 'flex-end',
    marginTop: -4,
  },
  forgotText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#007AFF',
  },
  loginButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#007AFF',
    borderRadius: 16,
    height: 60,
    gap: 10,
    boxShadow: '0px 10px 18px rgba(0, 122, 255, 0.35)',
    elevation: 8,
    marginTop: 4,
  },
  loginButtonText: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '700',
  },
  // Footer
  footer: {
    marginTop: Spacing.xl,
    alignItems: 'center',
    gap: Spacing.md,
  },
  signupRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  signupText: {
    fontSize: 15,
    color: '#ffffff',
    fontWeight: '500',
    textShadow: '0px 1px 2px rgba(0, 0, 0, 0.5)',
  },
  signupLink: {
    fontSize: 15,
    color: '#00C2A8',
    fontWeight: '700',
  },
  securityBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.3)',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: BorderRadius.full,
    gap: 6,
  },
  securityText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#00C2A8',
    letterSpacing: 1.2,
  },
});
