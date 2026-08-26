import React from 'react';
import {
  Text,
  StyleSheet,
  Pressable,
  ViewStyle,
  StyleProp,
} from 'react-native';
import { Colors } from '../constants/colors';
import { Typography, BorderRadius } from '../constants/theme';

export interface SecondaryButtonProps {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function SecondaryButton({
  label,
  onPress,
  disabled = false,
  style,
  testID,
}: SecondaryButtonProps) {
  return (
    <Pressable
      testID={testID}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        pressed && !disabled && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}
    >
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    width: '100%',
    height: 52,
    borderRadius: BorderRadius.full,
    backgroundColor: Colors.primaryMuted,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  label: {
    ...Typography.bodyLG,
    color: Colors.primary,
    fontWeight: '600',
  },
  pressed: {
    transform: [{ scale: 0.98 }],
    opacity: 0.8,
  },
  disabled: {
    opacity: 0.5,
  },
});
