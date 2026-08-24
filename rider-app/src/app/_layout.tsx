// ============================================================
// RideShield — Root Layout (Expo Router)
// ============================================================

import React, { useEffect } from 'react';
import { Stack, useSegments, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StyleSheet } from 'react-native';
import { AuthProvider, useAuth } from '../store/authStore';
import { RideProvider } from '../store/rideStore';
import { Colors } from '../constants/colors';

function AuthGate({ children }: { children: React.ReactNode }) {
  const { state: authState } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (authState.isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';
    const isVerifying = segments[1] === 'verify';

    if (!authState.isAuthenticated) {
      if (!inAuthGroup) {
        router.replace('/(auth)/login');
      }
    } else {
      if (!authState.user?.isPhoneVerified) {
        if (!isVerifying) {
          router.replace('/(auth)/verify');
        }
      } else if (inAuthGroup) {
        router.replace('/(tabs)/home');
      }
    }
  }, [authState.isAuthenticated, authState.user?.isPhoneVerified, authState.isLoading, segments]);

  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={styles.flex}>
      <SafeAreaProvider>
        <AuthProvider>
          <RideProvider>
            <AuthGate>
              <StatusBar style="dark" />
              <Stack
                screenOptions={{
                  headerShown: false,
                  contentStyle: { backgroundColor: Colors.background },
                  animation: 'slide_from_right',
                }}
              >
                <Stack.Screen name="index" options={{ animation: 'none' }} />
                <Stack.Screen name="(auth)" options={{ animation: 'none' }} />
                <Stack.Screen name="(tabs)" options={{ animation: 'none' }} />
                <Stack.Screen name="settings" />
                <Stack.Screen name="notifications" />
                <Stack.Screen name="privacy" />
                <Stack.Screen name="payment" />
                <Stack.Screen name="permissions" />
                <Stack.Screen name="live-ride" options={{ animation: 'slide_from_bottom', gestureEnabled: false }} />
                <Stack.Screen name="crash-alert" options={{ presentation: 'modal', animation: 'fade', gestureEnabled: false }} />
                <Stack.Screen name="sos" options={{ presentation: 'modal', animation: 'fade' }} />
                <Stack.Screen name="claim" />
                <Stack.Screen name="claim-status" />
                <Stack.Screen name="shift-summary" />
              </Stack>
            </AuthGate>
          </RideProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
});
