// ============================================================
// RideShield — Payment Screen (Vibrant Style)
// ============================================================

import React, { useState, useCallback, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Pressable,
  ScrollView,
} from 'react-native';
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

export default function PaymentScreen() {
  const router = useRouter();
  const { state: authState, refreshUser } = useAuth();
  const { setActiveShift } = useRide();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<'upi' | 'wallet'>('upi');

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const walletBalance = authState.user?.walletBalance ?? 500.00;

  const handlePay = useCallback(async () => {
    setError(null);
    setLoading(true);

    try {
      const userId = authState.user?.id ?? 'unknown';

      if (paymentMethod === 'wallet') {
        // Direct wallet payment deduction
        const response = await shiftService.startShift(userId, 'wallet');
        setActiveShift(response.shift);
        await refreshUser();
        router.replace('/live-ride');
        return;
      }

      // 1. Create Razorpay Order on trusted backend
      const order = await shiftService.createPaymentOrder();

      // 2. Open Razorpay Standard Checkout (on Web / RN)
      let paymentRes: { razorpay_payment_id: string; razorpay_order_id: string; razorpay_signature: string };

      if (typeof window !== 'undefined') {
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
        throw new Error("Razorpay Checkout is only supported on web environment in this build.");
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
            premiumPaidInr: Config.DAILY_PREMIUM_INR,
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
    }
  }, [authState.user?.id, setActiveShift, router, refreshUser, paymentMethod]);

  return (
    <SafeAreaView style={styles.safe}>
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

        {/* Price Card */}
        <View style={styles.priceCard}>
          <Text style={styles.priceAmount}>₹{Config.DAILY_PREMIUM_INR}</Text>
          <Text style={styles.priceLabel}>PER DAY</Text>
        </View>

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
              walletBalance < Config.DAILY_PREMIUM_INR && { opacity: 0.5 }
            ]}
            onPress={() => {
              if (walletBalance >= Config.DAILY_PREMIUM_INR) {
                setPaymentMethod('wallet');
              }
            }}
          >
            <Ionicons name="wallet-outline" size={20} color={paymentMethod === 'wallet' ? Colors.primary : Colors.textSecondary} />
            <View style={{ flex: 1, marginLeft: 12 }}>
              <Text style={[styles.paymentMethodTitle, paymentMethod === 'wallet' && { color: Colors.primary, fontWeight: '700' }]}>Wallet Balance</Text>
              <Text style={styles.paymentMethodSub}>Available: ₹{walletBalance.toFixed(2)}</Text>
            </View>
            {walletBalance < Config.DAILY_PREMIUM_INR ? (
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
          <Text style={styles.errorText}>{error}</Text>
        )}

        <Text style={styles.termsText}>
          By proceeding, you agree to the RideShield Commercial terms of service.
        </Text>

      </ScrollView>

      {/* Fixed Bottom Layout */}
      <View style={styles.bottomContainer}>
        <View style={styles.bottomNav}>
          <View style={styles.navItem}>
            <Ionicons name="home" size={24} color={Colors.primary} />
            <Text style={styles.navLabelActive}>Home</Text>
          </View>
          <View style={styles.navItem}>
            <Ionicons name="list-outline" size={24} color={Colors.textMuted} />
            <Text style={styles.navLabel}>Rides</Text>
          </View>
          <View style={styles.navItem}>
            <Ionicons name="person-outline" size={24} color={Colors.textMuted} />
            <Text style={styles.navLabel}>Profile</Text>
          </View>
        </View>
        
        <View style={styles.sosContainer}>
           <SOSButton onPress={() => router.push('/sos')} size={56} />
        </View>

        {/* Floating Pay button in center of nav for visual fidelity to mockup if needed, but standard is bottom */}
        <View style={{position: 'absolute', bottom: 100, width: '100%', paddingHorizontal: Spacing.lg}}>
          <PrimaryButton
            label={`PAY ₹${Config.DAILY_PREMIUM_INR}`}
            onPress={handlePay}
            loading={loading}
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
  bottomNav: {
    flexDirection: 'row',
    backgroundColor: Colors.card,
    paddingVertical: Spacing.md,
    paddingBottom: Spacing.xl, // safe area
    borderTopWidth: 1,
    borderTopColor: Colors.border,
    justifyContent: 'space-around',
  },
  navItem: {
    alignItems: 'center',
  },
  navLabelActive: {
    ...Typography.caption,
    color: Colors.primary,
    fontWeight: '600',
    marginTop: 4,
  },
  navLabel: {
    ...Typography.caption,
    color: Colors.textMuted,
    marginTop: 4,
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
});
