// ============================================================
// RideShield — Home Screen
// ============================================================

import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  ImageBackground,
  Linking,
  Modal,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useAuth } from '../../store/authStore';
import { useRide } from '../../store/rideStore';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Typography, Shadows } from '../../constants/theme';
import { storage } from '../../utils/storage';
import { Config } from '../../constants/config';
import { shiftService } from '../../services/shiftService';

export default function HomeScreen() {
  const router = useRouter();
  const { state: authState, refreshUser } = useAuth();
  const { state: rideState } = useRide();

  const [showRechargeModal, setShowRechargeModal] = useState(false);
  const [rechargeLoading, setRechargeLoading] = useState(false);
  const [showWebView, setShowWebView] = useState(false);
  const [checkoutUrl, setCheckoutUrl] = useState<string | null>(null);
  const [rechargeError, setRechargeError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      refreshUser();
    }, [refreshUser])
  );

  const user = authState.user;
  const walletBalance = user?.walletBalance ?? 500.00;
  const hasActiveShift = rideState.activeShift?.status === 'active';
  const firstName = user?.fullName?.split(' ')[0] ?? 'Rider';

  const activePremium = rideState.activeShift?.premiumPaidInr ?? 0;
  const activeCoverage = activePremium <= 3 ? 10000 : activePremium <= 5 ? 25000 : activePremium <= 7 ? 50000 : 100000;

  const handleStartShift = useCallback(() => {
    router.push('/helmet-check');
  }, [router]);

  const handleGoToLiveRide = useCallback(() => {
    router.push('/live-ride');
  }, [router]);

  const handleOpenWhatsApp = useCallback(async () => {
    const botNumber = Config.WHATSAPP_BOT_PHONE_NUMBER;
    const url = `https://wa.me/${botNumber}?text=Hi`;
    try {
      const supported = await Linking.canOpenURL(url);
      if (supported) {
        await Linking.openURL(url);
      } else {
        console.warn(`Cannot open WhatsApp URL: ${url}`);
      }
    } catch (err) {
      console.error('Error opening WhatsApp link:', err);
    }
  }, []);

  const handleRecharge = async (amount: number) => {
    setRechargeLoading(true);
    setRechargeError(null);
    try {
      const order = await shiftService.createRechargeOrder(amount);
      const url = `${Config.API_BASE_URL}/payments/checkout?order_id=${order.orderId}&amount=${order.amount}&key_id=${order.keyId}`;
      setCheckoutUrl(url);
      setShowWebView(true);
      setShowRechargeModal(false);
    } catch (err: any) {
      setRechargeError(err.message ?? 'Failed to initialize recharge payment.');
    } finally {
      setRechargeLoading(false);
    }
  };

  const handleWebViewNavigationStateChange = async (navState: any) => {
    const url = navState.url;
    if (url.includes('/payments/success')) {
      setShowWebView(false);
      setRechargeLoading(true);
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

        await shiftService.verifyPayment(paymentId, orderId, signature);
        await refreshUser();
      } catch (err: any) {
        setRechargeError(err.message ?? 'Verification failed.');
      } finally {
        setRechargeLoading(false);
      }
    }
    if (url.includes('/payments/cancel')) {
      setShowWebView(false);
      setRechargeError('Recharge payment cancelled.');
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* Top Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Ionicons name="shield-checkmark" size={24} color={Colors.primary} />
          <Text style={styles.headerBrand}>RideShield</Text>
        </View>
        <Pressable onPress={() => router.push('/(tabs)/profile')} style={styles.profileBadge}>
          <Text style={styles.profileInitial}>{firstName[0]?.toUpperCase() ?? 'R'}</Text>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={styles.scroll} showsVerticalScrollIndicator={false}>
        {/* Hero Banner */}
        <View style={styles.heroWrapper}>
          <ImageBackground
            source={{
              uri: 'https://images.unsplash.com/photo-1508847154043-be12a62861c1?q=80&w=800&auto=format&fit=crop',
            }}
            style={styles.heroBackground}
            imageStyle={styles.heroImageStyle}
          >
            <LinearGradient
              colors={['transparent', 'rgba(0, 30, 80, 0.4)', 'rgba(0, 20, 65, 0.88)']}
              style={styles.heroGradient}
            />
            <View style={styles.heroContent}>
              <View style={styles.heroTextGroup}>
                <Text style={styles.heroSub}>
                  {hasActiveShift ? "Active Shift" : "Today's Shift"}
                </Text>
                <Text style={styles.heroTitle}>
                  {hasActiveShift ? "Ready & Protected" : "Ready to Ride"}
                </Text>
              </View>

              <Pressable
                testID={hasActiveShift ? "go-to-live-ride" : "start-shift"}
                style={({ pressed }) => [
                  styles.startButton,
                  hasActiveShift && styles.liveButton,
                  pressed && { transform: [{ scale: 0.96 }] },
                ]}
                onPress={hasActiveShift ? handleGoToLiveRide : handleStartShift}
              >
                <Ionicons
                  name={hasActiveShift ? "navigate-circle" : "power-outline"}
                  size={22}
                  color={hasActiveShift ? "#ffffff" : "#001f24"}
                />
                <Text style={[styles.startButtonText, hasActiveShift && { color: '#ffffff' }]}>
                  {hasActiveShift ? "Dashboard" : "Start Shift"}
                </Text>
              </Pressable>
            </View>
          </ImageBackground>
        </View>

        {/* Wallet Balance Card */}
        <View style={styles.walletCard}>
          <View style={styles.walletTextGroup}>
            <Text style={styles.walletLabel}>WALLET BALANCE</Text>
            <Text style={styles.walletAmount}>₹{walletBalance.toFixed(2)}</Text>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <Pressable
              style={({ pressed }) => [
                styles.rechargeButton,
                pressed && { opacity: 0.8 },
              ]}
              onPress={() => setShowRechargeModal(true)}
            >
              <Ionicons name="add-circle-outline" size={16} color="#ffffff" />
              <Text style={styles.rechargeButtonText}>Recharge</Text>
            </Pressable>
            <View style={styles.walletIconCircle}>
              <Ionicons name="wallet-outline" size={24} color={Colors.primary} />
            </View>
          </View>
        </View>

        {/* Recharge Wallet Selector Modal */}
        <Modal
          visible={showRechargeModal}
          transparent={true}
          animationType="fade"
          onRequestClose={() => setShowRechargeModal(false)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.rechargeModalContent}>
              <View style={styles.rechargeModalHeader}>
                <Text style={styles.rechargeModalTitle}>Recharge Wallet</Text>
                <Pressable onPress={() => setShowRechargeModal(false)} style={styles.modalCloseButton}>
                  <Ionicons name="close" size={24} color={Colors.textPrimary} />
                </Pressable>
              </View>

              <Text style={styles.rechargeModalSubtitle}>Select recharge amount (Razorpay Secure Checkout):</Text>

              <View style={styles.rechargeOptionsContainer}>
                <Pressable
                  style={styles.rechargeOptionBtn}
                  onPress={() => handleRecharge(100)}
                >
                  <Text style={styles.rechargeOptionText}>₹100</Text>
                </Pressable>

                <Pressable
                  style={styles.rechargeOptionBtn}
                  onPress={() => handleRecharge(500)}
                >
                  <Text style={styles.rechargeOptionText}>₹500</Text>
                </Pressable>
              </View>

              {rechargeError && (
                <Text style={styles.rechargeErrorText}>{rechargeError}</Text>
              )}
            </View>
          </View>
        </Modal>

        {/* Razorpay WebView Modal for Recharge */}
        <Modal
          visible={showWebView}
          animationType="slide"
          onRequestClose={() => {
            setShowWebView(false);
            setRechargeError('Payment window closed.');
          }}
        >
          <SafeAreaView style={{ flex: 1, backgroundColor: '#ffffff' }} edges={['top']}>
            <View style={styles.webViewHeader}>
              <Pressable
                onPress={() => {
                  setShowWebView(false);
                  setRechargeError('Payment window closed.');
                }}
                style={styles.webViewCloseButton}
              >
                <Ionicons name="close" size={24} color="#1e293b" />
              </Pressable>
              <Text style={styles.webViewHeaderTitle}>Razorpay Secure Payment</Text>
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

        {/* WhatsApp Chatbot Card */}
        <View style={styles.whatsappCard}>
          <View style={styles.whatsappTextGroup}>
            <View style={styles.whatsappHeader}>
              <Ionicons name="logo-whatsapp" size={20} color="#25D366" />
              <Text style={styles.whatsappLabel}>WHATSAPP CHATBOT</Text>
            </View>
            <Text style={styles.whatsappTitle}>RideShield Bot</Text>
            <Text style={styles.whatsappDesc}>
              Connect with our bot to receive real-time notifications, confirm safety alerts, and manage SOS claims for free.
            </Text>
          </View>
          <Pressable
            style={({ pressed }) => [
              styles.whatsappButton,
              pressed && { transform: [{ scale: 0.97 }] },
            ]}
            onPress={handleOpenWhatsApp}
          >
            <Ionicons name="chatbubbles-outline" size={18} color="#ffffff" />
            <Text style={styles.whatsappButtonText}>Chat on WhatsApp</Text>
          </Pressable>
        </View>

        {/* Active Protection */}
        <View style={styles.protectionSection}>
          <Text style={styles.sectionTitle}>
            {hasActiveShift ? `Active Protection (Tier: ₹${activePremium})` : "Protection Details"}
          </Text>
          <View style={styles.protectionList}>
            {/* Item 1 */}
            <View style={[styles.protectionCard, !hasActiveShift && { opacity: 0.6 }]}>
              <View style={[styles.protectionIconCircle, { backgroundColor: '#ffdad5' }]}>
                <Ionicons name="bicycle-outline" size={22} color="#410001" />
              </View>
              <View style={styles.protectionTextGroup}>
                <Text style={styles.protectionTitle}>Vehicle Damage</Text>
                <Text style={styles.protectionDesc}>
                  {hasActiveShift 
                    ? `Accidental damage coverage up to ₹${activeCoverage.toLocaleString('en-IN')}.`
                    : "Accidental damage coverage up to ₹1,00,000 depending on selected tier."}
                </Text>
              </View>
              <Ionicons 
                name={hasActiveShift ? "checkmark-circle" : "ellipse-outline"} 
                size={22} 
                color={hasActiveShift ? Colors.success : Colors.textMuted} 
              />
            </View>

            {/* Item 2 */}
            <View style={[styles.protectionCard, !hasActiveShift && { opacity: 0.6 }]}>
              <View style={[styles.protectionIconCircle, { backgroundColor: '#d8e2ff' }]}>
                <Ionicons name="medical-outline" size={22} color="#001a41" />
              </View>
              <View style={styles.protectionTextGroup}>
                <Text style={styles.protectionTitle}>Personal Accident & Medical</Text>
                <Text style={styles.protectionDesc}>
                  {hasActiveShift
                    ? `Medical bills and hospitalization expense coverage up to ₹${activeCoverage.toLocaleString('en-IN')}.`
                    : "Medical bill coverage up to ₹1,00,000 for injuries sustained during shifts."}
                </Text>
              </View>
              <Ionicons 
                name={hasActiveShift ? "checkmark-circle" : "ellipse-outline"} 
                size={22} 
                color={hasActiveShift ? Colors.success : Colors.textMuted} 
              />
            </View>
          </View>
        </View>

        {/* Daily Insight Banner */}
        <View style={styles.insightCard}>
          <View style={styles.insightHeader}>
            <Ionicons name="bulb-outline" size={20} color="#ffffff" />
            <Text style={styles.insightTitle}>Daily Insight</Text>
          </View>
          <Text style={styles.insightBody}>
            Wet roads reported downtown. Reduce speed by 15% and increase braking distance to maintain optimal safety ratings today.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.background },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.sm,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerBrand: {
    ...Typography.h3,
    color: Colors.primary,
    fontWeight: '700',
  },
  profileBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  profileInitial: {
    ...Typography.labelMD,
    color: '#ffffff',
    fontWeight: '700',
  },
  scroll: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.xxl,
    gap: Spacing.lg,
  },
  // Hero Banner
  heroWrapper: {
    height: 280,
    borderRadius: BorderRadius.xl,
    overflow: 'hidden',
    ...Shadows.medium,
  },
  heroBackground: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  heroImageStyle: {
    borderRadius: BorderRadius.xl,
  },
  heroGradient: {
    ...StyleSheet.absoluteFill,
  },
  heroContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    padding: Spacing.lg,
    zIndex: 10,
  },
  heroTextGroup: {
    flex: 1,
    paddingRight: Spacing.sm,
  },
  heroSub: {
    ...Typography.bodyMD,
    color: 'rgba(255, 255, 255, 0.8)',
    marginBottom: 2,
  },
  heroTitle: {
    ...Typography.h1,
    color: '#ffffff',
    fontSize: 28,
  },
  startButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#00daf3',
    paddingHorizontal: Spacing.lg,
    paddingVertical: 14,
    borderRadius: BorderRadius.full,
    gap: 8,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 6,
  },
  liveButton: {
    backgroundColor: Colors.success,
  },
  startButtonText: {
    ...Typography.labelMD,
    color: '#001f24',
    fontWeight: '700',
  },
  // Wallet Card
  walletCard: {
    backgroundColor: '#f4f3f8',
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: Colors.border,
  },
  walletTextGroup: {
    gap: 2,
  },
  walletLabel: {
    ...Typography.labelSM,
    color: Colors.textSecondary,
    letterSpacing: 1.2,
  },
  walletAmount: {
    ...Typography.h2,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  walletIconCircle: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Protection Section
  protectionSection: {
    gap: Spacing.md,
  },
  sectionTitle: {
    ...Typography.h4,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  protectionList: {
    gap: Spacing.sm,
  },
  protectionCard: {
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.md,
    ...Shadows.soft,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  protectionIconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    alignItems: 'center',
    justifyContent: 'center',
  },
  protectionTextGroup: {
    flex: 1,
  },
  protectionTitle: {
    ...Typography.bodyLG,
    fontWeight: '700',
    color: Colors.textPrimary,
  },
  protectionDesc: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  // Insight Card
  insightCard: {
    backgroundColor: Colors.primary,
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.xs,
    ...Shadows.soft,
  },
  insightHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  insightTitle: {
    ...Typography.labelMD,
    color: '#ffffff',
    fontWeight: '700',
  },
  insightBody: {
    ...Typography.bodyMD,
    color: 'rgba(255, 255, 255, 0.95)',
    lineHeight: 22,
  },
  // WhatsApp Card Styling
  whatsappCard: {
    backgroundColor: '#E8F5E9',
    borderRadius: BorderRadius.xl,
    padding: Spacing.lg,
    gap: Spacing.md,
    borderWidth: 1,
    borderColor: '#C8E6C9',
  },
  whatsappHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  whatsappTextGroup: {
    gap: 2,
  },
  whatsappLabel: {
    ...Typography.labelSM,
    color: '#2E7D32',
    fontWeight: '700',
    letterSpacing: 1.2,
  },
  whatsappTitle: {
    ...Typography.h3,
    color: '#1B5E20',
    fontWeight: '800',
  },
  whatsappDesc: {
    ...Typography.bodySM,
    color: '#388E3C',
    lineHeight: 18,
    marginTop: 4,
  },
  whatsappButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#25D366',
    paddingVertical: 12,
    borderRadius: BorderRadius.lg,
    gap: 8,
    shadowColor: '#25D366',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 6,
    elevation: 3,
  },
  whatsappButtonText: {
    ...Typography.labelMD,
    color: '#ffffff',
    fontWeight: '700',
  },
  rechargeButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.primary,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: BorderRadius.md,
    gap: 4,
  },
  rechargeButtonText: {
    ...Typography.caption,
    color: '#ffffff',
    fontWeight: '700',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.lg,
  },
  rechargeModalContent: {
    width: '100%',
    maxWidth: 340,
    backgroundColor: Colors.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.lg,
    ...Shadows.medium,
  },
  rechargeModalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: Spacing.md,
  },
  rechargeModalTitle: {
    ...Typography.bodyLG,
    color: Colors.textPrimary,
    fontWeight: '700',
  },
  modalCloseButton: {
    padding: 4,
  },
  rechargeModalSubtitle: {
    ...Typography.bodySM,
    color: Colors.textSecondary,
    marginBottom: Spacing.md,
  },
  rechargeOptionsContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    gap: 12,
    marginBottom: Spacing.md,
  },
  rechargeOptionBtn: {
    flex: 1,
    backgroundColor: Colors.primaryMuted,
    borderWidth: 1,
    borderColor: Colors.primary,
    borderRadius: BorderRadius.md,
    paddingVertical: 14,
    alignItems: 'center',
  },
  rechargeOptionText: {
    fontSize: 18,
    fontWeight: '700',
    color: Colors.primary,
  },
  rechargeErrorText: {
    ...Typography.bodySM,
    color: Colors.danger,
    textAlign: 'center',
    marginTop: Spacing.xs,
  },
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
});
