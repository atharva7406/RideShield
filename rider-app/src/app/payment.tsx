// ============================================================
// RideShield — Payment Screen (Vibrant Style)
// ============================================================

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
  Modal,
  ActivityIndicator,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '../store/authStore';
import { useRide } from '../store/rideStore';
import { shiftService } from '../services/shiftService';
import { PrimaryButton } from '../components/PrimaryButton';
import { SOSButton } from '../components/SOSButton';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../constants/theme';
import { Config } from '../constants/config';
import { storage } from '../utils/storage';
import type { PremiumPreview } from '../types/shift';

export default function PaymentScreen() {
  const router = useRouter();
  const { state: authState, refreshUser } = useAuth();
  const { setActiveShift } = useRide();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<'upi' | 'wallet'>('upi');
  const [showWebView, setShowWebView] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const isSubmitting = useRef(false);
  const [preview, setPreview] = useState<PremiumPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [selectedTier, setSelectedTier] = useState(Config.PREMIUM_TIERS[1]);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  useEffect(() => {
    let cancelled = false;
    setPreviewLoading(true);
    shiftService
      .getPremiumPreview(selectedTier.premium)
      .then(p => { if (!cancelled) setPreview(p); })
      .catch(err => {
        // Non-fatal: the backend is still the authority on what actually
        // gets charged at payment time — this preview is display-only.
        // Falling back to the flat demo constant just keeps the screen
        // from breaking if the preview call fails.
        console.warn('[PaymentScreen] Failed to load premium preview:', err);
      })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, [selectedTier]);

  // Server-computed premium is the number that will actually be charged;
  // selectedTier.premium is only a fallback while the preview is
  // loading or if it failed to load.
  const displayedPremium = preview?.finalPremium ?? selectedTier.premium;

  const walletBalance = authState.user?.walletBalance ?? 500.00;

  const handlePay = useCallback(async () => {
    if (isSubmitting.current) return;
    setError(null);
    setLoading(true);
    isSubmitting.current = true;

    try {
      const userId = authState.user?.id ?? 'unknown';

      if (paymentMethod === 'wallet') {
        // Direct wallet payment deduction
        const response = await shiftService.startShift(userId, 'wallet', selectedTier.premium);
        setActiveShift(response.shift);
        await refreshUser();
        router.replace('/live-ride');
        return;
      }

      // 1. Create Razorpay Order on trusted backend
      const order = await shiftService.createPaymentOrder(undefined, selectedTier.premium);

      // 2. Open Razorpay Standard Checkout (on Web / RN)
      let paymentRes: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };

      if (typeof window !== 'undefined' && typeof document !== 'undefined') {
        // Dynamically load Razorpay SDK on web if not present
        if (!(window as any).Razorpay) {
          await new Promise<void>((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://checkout.razorpay.com/v1/checkout.js';
            script.onload = () => resolve();
            script.onerror = () => reject(new Error('Failed to load Razorpay SDK'));
            document.body.appendChild(script);
          });
        }

        paymentRes = await new Promise((resolve, reject) => {
          const options = {
            key: order.keyId,
            amount: order.amount,
            currency: order.currency,
            name: 'RideShield Microinsurance',
            description: 'Daily Commercial Protection',
            order_id: order.orderId,
            handler: function (res: any) {
              resolve(res);
            },
            modal: {
              ondismiss: function () {
                reject(new Error('Payment checkout cancelled by user'));
              },
            },
            theme: { color: '#0d9488' },
          };
          const rzp = new (window as any).Razorpay(options);
          rzp.open();
        });
      } else {
        // Native (no window/document): fall back to a WebView-hosted
        // checkout page served by the backend, since the Razorpay web
        // SDK script-injection approach above only works in a browser.
        const url = `${Config.API_BASE_URL}/payments/checkout?order_id=${order.orderId}&amount=${order.amount}&key_id=${order.keyId}`;
        setCheckoutUrl(url);
        setShowWebView(true);
        setLoading(false);
        return;
      }

      // 3. Verify Payment Signature Server-Side
      const verifyRes = await shiftService.verifyPayment(
        paymentRes.razorpay_payment_id,
        paymentRes.razorpay_order_id,
        paymentRes.razorpay_signature
      );

      if (verifyRes.coverageActive) {
        // Fetch active shift details
        const activeShiftData = await shiftService.getActiveShift();
        if (activeShiftData) {
          setActiveShift(activeShiftData);
        } else {
          setActiveShift({
            id: verifyRes.shiftId,
            userId: userId,
            status: 'active',
            startedAt: new Date().toISOString(),
            premiumPaidInr: displayedPremium,
            coverageActive: true,
          });
        }
        await refreshUser();
        router.replace('/live-ride');
      } else {
        setError('Payment verification failed. Coverage not activated.');
      }
    } catch (err: any) {
      setError(err.message ?? 'Payment process failed. Please try again.');
    } finally {
      setLoading(false);
      isSubmitting.current = false;
    }
  }, [authState.user?.id, setActiveShift, router, refreshUser, paymentMethod, displayedPremium, selectedTier]);

  const handleWebViewNavigationStateChange = useCallback(async (navState: any) => {
    const url = navState.url;

    if (url.includes('/payments/success')) {
      setShowWebView(false);
      setLoading(true);

      try {
        const getParam = (name: string) => {
          const match = RegExp('[?&]' + name + '=([^&]*)').exec(url);
          return match ? decodeURIComponent(match[1].replace(/\+/g, ' ')) : '';
        };

        const paymentId = getParam('razorpay_payment_id');
        const orderId = getParam('razorpay_order_id');
        const signature = getParam('razorpay_signature');

        if (!paymentId || !orderId) {
          throw new Error("Missing payment credentials in response redirection.");
        }

        const verifyRes = await shiftService.verifyPayment(paymentId, orderId, signature);

        if (verifyRes.coverageActive) {
          const activeShiftData = await shiftService.getActiveShift();
          if (activeShiftData) {
            setActiveShift(activeShiftData);
          } else {
            setActiveShift({
              id: verifyRes.shiftId,
              userId: authState.user?.id ?? 'unknown',
              status: 'active',
              startedAt: new Date().toISOString(),
              premiumPaidInr: displayedPremium,
              coverageActive: true,
            });
          }
          await refreshUser();
          router.replace('/live-ride');
        } else {
          setError('Payment verification failed. Coverage not activated.');
        }
      } catch (err: any) {
        setError(err.message ?? 'Verification failed.');
      } finally {
        setLoading(false);
      }
    }

    if (url.includes('/payments/cancel')) {
      setShowWebView(false);
      setError('Payment cancelled by user.');
    }
  }, [authState.user?.id, refreshUser, router, setActiveShift, displayedPremium]);

  return (
    <SafeAreaView style={styles.safe}>
      {/* WebView Modal for Razorpay Checkout on Mobile */}
      <Modal
        visible={showWebView}
        animationType="slide"
        onRequestClose={() => {
          setShowWebView(false);
          setError('Payment window closed.');
        }}
      >
        <SafeAreaView style={{ flex: 1, backgroundColor: '#ffffff' }}>
          <View style={styles.webViewHeader}>
            <Pressable
              onPress={() => {
                setShowWebView(false);
                setError('Payment window closed.');
              }}
              style={styles.webViewCloseButton}
            >
              <Ionicons name="close" size={24} color="#1e293b" />
            </Pressable>
            <Text style={styles.webViewHeaderTitle}>Secure Payment Gateway</Text>
            <View style={{ width: 40 }} />
          </View>
          {checkoutUrl && (
            <WebView
              source={{
                uri: checkoutUrl,
                headers: {
                  'bypass-tunnel-reminder': 'true'
                }
              }}
              onNavigationStateChange={handleWebViewNavigationStateChange}
              javaScriptEnabled={true}
              domStorageEnabled={true}
              startInLoadingState={true}
              style={{ flex: 1 }}
            />
          )}
        </SafeAreaView>
      </Modal>
      {/* Top Header */}
      <View style={styles.topHeader}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.headerTitle}>RideShield</Text>
        <View style={styles.liveBadge}>
          <View style={styles.liveDot} />
          <Text style={styles.liveText}>LIVE</Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Hero */}
        <View style={styles.hero}>
          <View style={styles.shieldIconContainer}>
            <Ionicons name="shield-checkmark" size={32} color={Colors.primary} />
          </View>
          <Text style={styles.heroTitle}>Start today's protection</Text>
          <Text style={styles.heroSubtitle}>Daily commercial insurance coverage</Text>
        </View>

        {/* Protection Tier Selector */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Select Protection Tier</Text>
        </View>

        <View style={styles.tiersContainer}>
          {Config.PREMIUM_TIERS.map((tier) => {
            const isSelected = selectedTier.premium === tier.premium;
            return (
              <Pressable
                key={tier.premium}
                style={[
                  styles.tierCard,
                  isSelected && styles.tierCardSelected
                ]}
                onPress={() => setSelectedTier(tier)}
              >
                <View style={styles.tierHeader}>
                  <Text style={[styles.tierLabel, isSelected && styles.tierTextSelected]}>
                    {tier.label}
                  </Text>
                  <Ionicons 
                    name={isSelected ? "checkbox-sharp" : "square-outline"} 
                    size={16} 
                    color={isSelected ? Colors.primary : Colors.textMuted} 
                  />
                </View>
                <Text style={[styles.tierPremium, isSelected && styles.tierTextSelected]}>
                  ₹{tier.premium}
                </Text>
                <Text style={styles.tierCoverage}>
                  Upto ₹{tier.coverage.toLocaleString()}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Dynamic Price Card (Base Premium +/- Risk Adjustment) */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Your Risk-Adjusted Premium</Text>
        </View>

        {/* Price Card */}
        <View style={styles.priceCard}>
          {previewLoading ? (
            <ActivityIndicator color={Colors.primary} />
          ) : (
            <Text style={styles.priceAmount}>₹{displayedPremium.toFixed(2)}</Text>
          )}
          <Text style={styles.priceLabel}>PER DAY</Text>
          {preview && !preview.isColdStart && preview.riskBand && (
            <Text style={styles.priceRiskBand}>
              Personalized · {preview.riskBand.replace('_', ' ')} risk
            </Text>
          )}
        </View>

        {/* Pricing Breakdown ("why this price?") */}
        {preview && preview.explanation && (
          <Pressable
            style={styles.breakdownCard}
            onPress={() => setShowBreakdown(v => !v)}
          >
            <View style={styles.breakdownHeader}>
              <Ionicons name="receipt-outline" size={18} color={Colors.primary} />
              <Text style={styles.breakdownHeaderText}>Why this price?</Text>
              <Ionicons
                name={showBreakdown ? 'chevron-up' : 'chevron-down'}
                size={18}
                color={Colors.textSecondary}
              />
            </View>
            {showBreakdown && (
              <View style={styles.breakdownBody}>
                {preview.explanation.split('\n').map((line, idx) => (
                  <Text key={idx} style={styles.breakdownLine}>{line}</Text>
                ))}
              </View>
            )}
          </Pressable>
        )}

        {/* Details Card */}
        <View style={styles.detailsCard}>
          {/* Row 1 */}
          <View style={styles.detailRow}>
            <View style={styles.detailIconWrap}>
              <Ionicons name="calendar-outline" size={20} color={Colors.success} />
            </View>
            <View style={styles.detailTextContent}>
              <Text style={styles.detailTitle}>Coverage</Text>
              <Text style={styles.detailSub}>Valid till midnight</Text>
            </View>
            <Text style={styles.detailTrailing}>1 Day</Text>
          </View>

          <View style={styles.divider} />

          {/* Row 2 */}
          <View style={styles.detailRow}>
            <View style={styles.detailIconWrap}>
              <Ionicons name="checkmark-circle-outline" size={20} color={Colors.success} />
            </View>
            <View style={styles.detailTextContent}>
              <Text style={styles.detailTitle}>Status</Text>
              <View style={styles.statusBadge}>
                <Text style={styles.statusBadgeText}>Ready to activate</Text>
              </View>
            </View>
          </View>

          <View style={styles.divider} />

          {/* Payment Method Selector */}
          <Text style={[styles.detailTitle, { marginBottom: Spacing.xs, paddingHorizontal: Spacing.xs, color: Colors.textSecondary }]}>Payment method</Text>

          <Pressable
            style={[styles.paymentMethodOption, paymentMethod === 'upi' && styles.paymentMethodOptionSelected]}
            onPress={() => setPaymentMethod('upi')}
          >
            <Ionicons name="phone-portrait-outline" size={20} color={paymentMethod === 'upi' ? Colors.primary : Colors.textSecondary} />
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={[styles.paymentMethodTitle, paymentMethod === 'upi' && { color: Colors.primary, fontWeight: '700' }]}>UPI</Text>
              <Text style={styles.paymentMethodSub}>Linked Bank Account</Text>
            </View>
            <Ionicons
              name={paymentMethod === 'upi' ? "radio-button-on" : "radio-button-off"}
              size={20}
              color={paymentMethod === 'upi' ? Colors.primary : Colors.border}
            />
          </Pressable>

          <Pressable
            style={[
              styles.paymentMethodOption,
              paymentMethod === 'wallet' && styles.paymentMethodOptionSelected,
              walletBalance < displayedPremium && { opacity: 0.5 }
            ]}
            onPress={() => {
              if (walletBalance >= displayedPremium) {
                setPaymentMethod('wallet');
              }
            }}
          >
            <Ionicons name="wallet-outline" size={20} color={paymentMethod === 'wallet' ? Colors.primary : Colors.textSecondary} />
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={[styles.paymentMethodTitle, paymentMethod === 'wallet' && { color: Colors.primary, fontWeight: '700' }]}>Wallet Balance</Text>
              <Text style={styles.paymentMethodSub}>Available: ₹{walletBalance.toFixed(2)}</Text>
            </View>
            {walletBalance < displayedPremium ? (
              <Text style={{ color: Colors.danger, fontSize: 12, fontWeight: '600', marginRight: 4 }}>Insufficient</Text>
            ) : (
              <Ionicons
                name={paymentMethod === 'wallet' ? "radio-button-on" : "radio-button-off"}
                size={20}
                color={paymentMethod === 'wallet' ? Colors.primary : Colors.border}
              />
            )}
          </Pressable>
        </View>

        {error && (
          <View style={{ width: '100%', alignItems: 'center', marginTop: Spacing.sm }}>
            <Text style={styles.errorText}>{error}</Text>
            {error.toLowerCase().includes('helmet') && (
              <Pressable
                style={({ pressed }) => [styles.reconfirmBtn, pressed && { opacity: 0.8 }]}
                onPress={() => router.replace('/helmet-check')}
              >
                <Ionicons name="shield-outline" size={16} color="#ffffff" style={{ marginRight: 6 }} />
                <Text style={styles.reconfirmBtnText}>Re-confirm Helmet Safety Acknowledgment</Text>
              </Pressable>
            )}
          </View>
        )}

        <Text style={styles.termsText}>
          By proceeding, you agree to the RideShield Commercial terms of service.
        </Text>

      </ScrollView>

      {/* Fixed Bottom Layout */}
      <View style={styles.bottomContainer}>
        <View style={styles.sosContainer}>
           <SOSButton onPress={() => router.push('/sos')} size={56} />
        </View>

        {/* Floating Pay button in center of nav for visual fidelity to mockup if needed, but standard is bottom */}
        <View style={{position: 'absolute', bottom: 100, width: '100%', paddingHorizontal: Spacing.lg}}>
          <PrimaryButton
            label={`PAY ₹${displayedPremium.toFixed(2)}`}
            onPress={handlePay}
            loading={loading || previewLoading}
          />
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  // Top Header
  topHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.background,
  },
  backButton: { padding: Spacing.xs },
  headerTitle: { ...Typography.bodyMD, color: Colors.primary, fontWeight: '700' },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.successMuted,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: BorderRadius.full,
    gap: 4,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Colors.success,
  },
  liveText: {
    ...Typography.labelSM,
    color: Colors.success,
  },

  scroll: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xl,
    paddingBottom: 180, // Space for fixed bottom
    alignItems: 'center',
  },
  // Hero
  hero: {
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  shieldIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing.md,
  },
  heroTitle: {
    ...Typography.h2,
    color: Colors.textPrimary,
    marginBottom: 4,
    textAlign: 'center',
  },
  heroSubtitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
  // Price Card
  priceCard: {
    width: '100%',
    backgroundColor: Colors.primaryMuted,
    borderRadius: BorderRadius.lg,
    paddingVertical: Spacing.xl,
    alignItems: 'center',
    marginBottom: Spacing.lg,
  },
  priceAmount: {
    fontSize: 40,
    fontWeight: '800',
    color: Colors.primary,
    marginBottom: 4,
  },
  priceLabel: {
    ...Typography.labelSM,
    color: Colors.primary,
    letterSpacing: 1.5,
  },
  priceRiskBand: {
    ...Typography.caption,
    color: Colors.textSecondary,
    marginTop: 6,
  },
  // Pricing Breakdown
  breakdownCard: {
    width: '100%',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.lg,
  },
  breakdownHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  breakdownHeaderText: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
    flex: 1,
  },
  breakdownBody: {
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  breakdownLine: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    lineHeight: 20,
  },
  // Details Card
  detailsCard: {
    width: '100%',
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.xl,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  detailIconWrap: {
    width: 40,
    alignItems: 'center',
  },
  detailTextContent: {
    flex: 1,
    paddingLeft: Spacing.sm,
  },
  detailTitle: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  detailSub: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
  },
  detailTrailing: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
  },
  detailTrailingBold: {
    ...Typography.bodyMD,
    color: Colors.primary,
    fontWeight: '700',
  },
  statusBadge: {
    backgroundColor: Colors.successMuted,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginTop: 4,
  },
  statusBadgeText: {
    ...Typography.caption,
    color: Colors.success,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    backgroundColor: Colors.border,
    marginVertical: Spacing.md,
  },

  errorText: {
    ...Typography.bodyMD,
    color: Colors.danger,
    marginBottom: Spacing.md,
    textAlign: 'center',
  },
  termsText: {
    ...Typography.bodySM,
    color: Colors.textMuted,
    textAlign: 'center',
    paddingHorizontal: Spacing.lg,
  },

  // Bottom Mock Nav (Since payment might not be in tabs but looks like it in mockup)
  bottomContainer: {
    position: 'absolute',
    bottom: 0,
    width: '100%',
  },
  sosContainer: {
    position: 'absolute',
    bottom: 80,
    right: Spacing.md,
  },
  paymentMethodOption: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    marginVertical: 6,
  },
  paymentMethodOptionSelected: {
    borderColor: Colors.primary,
    backgroundColor: '#f0fbfc',
  },
  paymentMethodTitle: {
    ...Typography.bodyMD,
    color: Colors.textPrimary,
    fontWeight: '600',
  },
  paymentMethodSub: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    marginTop: 2,
  },
  // WebView Header Styles
  webViewHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: Spacing.md,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
    backgroundColor: '#ffffff',
  },
  webViewCloseButton: {
    padding: 6,
  },
  webViewHeaderTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1e293b',
  },
  reconfirmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.danger,
    borderRadius: BorderRadius.md,
    paddingHorizontal: 16,
    paddingVertical: 10,
    marginTop: Spacing.sm,
  },
  reconfirmBtnText: {
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 14,
  },
  sectionHeader: {
    width: '100%',
    alignSelf: 'flex-start',
    marginTop: Spacing.md,
    marginBottom: Spacing.xs,
  },
  sectionTitle: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  tiersContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    width: '100%',
    marginVertical: Spacing.xs,
  },
  tierCard: {
    width: '48%',
    backgroundColor: Colors.card,
    borderWidth: 1,
    borderColor: Colors.border,
    borderRadius: BorderRadius.md,
    padding: Spacing.sm,
    marginBottom: Spacing.sm,
    justifyContent: 'space-between',
  },
  tierCardSelected: {
    borderColor: Colors.primary,
    backgroundColor: '#f0fbfc',
  },
  tierHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  tierLabel: {
    ...Typography.caption,
    fontWeight: '600',
    color: Colors.textMuted,
  },
  tierPremium: {
    ...Typography.h3,
    fontWeight: '800',
    color: Colors.textPrimary,
  },
  tierCoverage: {
    ...Typography.caption,
    color: Colors.textSecondary,
    fontSize: 10,
    marginTop: 2,
  },
  tierTextSelected: {
    color: Colors.primary,
  },
});
