// ============================================================
// RideShield — App Entry / Auth Gate
// ============================================================

import React, { useEffect } from 'react';
import { View, ActivityIndicator, StyleSheet } from 'react-native';
import { Redirect } from 'expo-router';
import { useAuth } from '../store/authStore';
import { Colors } from '../constants/colors';

export default function IndexScreen() {
  const { state } = useAuth();

  if (state.isLoading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator color={Colors.primary} size="large" />
      </View>
    );
  }

  if (state.isAuthenticated) {
    return <Redirect href="/(tabs)/home" />;
  }

  return <Redirect href="/(auth)/login" />;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
