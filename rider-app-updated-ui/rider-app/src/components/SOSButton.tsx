import React, { useEffect, useRef } from 'react';
import {
  Pressable,
  Text,
  StyleSheet,
  Animated,
  ViewStyle,
  StyleProp,
} from 'react-native';
import { Colors } from '../constants/colors';
import { Typography, Shadows } from '../constants/theme';

interface SOSButtonProps {
  onPress: () => void;
  size?: number;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function SOSButton({ onPress, size = 64, style, testID }: SOSButtonProps) {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(scaleAnim, {
          toValue: 1.05,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.timing(scaleAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [scaleAnim]);

  return (
    <Animated.View style={[{ transform: [{ scale: scaleAnim }] }, style]}>
      <Pressable
        testID={testID}
        onPress={onPress}
        style={({ pressed }) => [
          styles.button,
          { width: size, height: size, borderRadius: size / 2 },
          pressed && styles.pressed,
        ]}
      >
        <Text style={styles.text}>SOS</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: Colors.danger,
    alignItems: 'center',
    justifyContent: 'center',
    ...Shadows.medium,
    shadowColor: Colors.danger,
  },
  text: {
    ...Typography.labelMD,
    color: '#ffffff',
    fontWeight: '800',
    letterSpacing: 1,
  },
  pressed: {
    opacity: 0.8,
  },
});
