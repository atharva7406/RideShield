// ============================================================
// RideShield — LoadingState Component
// ============================================================

import React, { useRef, useEffect } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, Animated } from 'react-native';
import { Colors, Spacing, Typography } from '../constants/theme';

interface LoadingStateProps {
  message?: string;
  fullScreen?: boolean;
}

export function LoadingState({
  message = 'Loading…',
  fullScreen = false,
}: LoadingStateProps) {
  const fadeAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start();
  }, [fadeAnim]);

  return (
    <Animated.View
      style={[styles.container, fullScreen && styles.fullScreen, { opacity: fadeAnim }]}
    >
      <ActivityIndicator color={Colors.primary} size="large" />
      <Text style={styles.message}>{message}</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing.xl,
    gap: Spacing.md,
  },
  fullScreen: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  message: {
    ...Typography.bodyMD,
    color: Colors.textSecondary,
    textAlign: 'center',
  },
});
