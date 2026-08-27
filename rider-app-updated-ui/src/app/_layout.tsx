// ============================================================
// RideShield — Root Layout (Expo Router)
// ============================================================

import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { StyleSheet } from 'react-native';
import { AuthProvider } from '../store/authStore';
import { RideProvider } from '../store/rideStore';
import { Colors } from '../constants/colors';

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={styles.flex}>
      <SafeAreaProvider>
        <AuthProvider>
          <RideProvider>
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
          </RideProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
});
