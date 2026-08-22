// ============================================================
// RideShield — SpeedMeter Component
// ============================================================

import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Svg, { Circle, Defs, LinearGradient, Stop } from 'react-native-svg';
import { Colors, Typography } from '../constants/theme';

interface SpeedMeterProps {
  speed: number;     // km/h
  maxSpeed?: number; // km/h
  size?: number;
}

export function SpeedMeter({ speed, maxSpeed = 120, size = 200 }: SpeedMeterProps) {
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const sweepAngle = 0.75; // 270° arc
  const dashLength = circumference * sweepAngle;
  const gap = circumference * (1 - sweepAngle);
  const progress = Math.min(speed / maxSpeed, 1);
  const strokeDash = dashLength * progress;

  // Color interpolation: cyan → warning → danger
  const color = useMemo(() => {
    if (speed < 40) return Colors.primary;
    if (speed < 80) return Colors.warning;
    return Colors.danger;
  }, [speed]);

  const rotation = 135; // start angle

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        <Defs>
          <LinearGradient id="speedGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <Stop offset="0%" stopColor={Colors.primary} stopOpacity="1" />
            <Stop offset="100%" stopColor={color} stopOpacity="1" />
          </LinearGradient>
        </Defs>

        {/* Background arc */}
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={Colors.border}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${dashLength} ${gap}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          rotation={rotation}
          origin={`${size / 2}, ${size / 2}`}
        />

        {/* Progress arc */}
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="url(#speedGrad)"
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={`${strokeDash} ${circumference - strokeDash}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          rotation={rotation}
          origin={`${size / 2}, ${size / 2}`}
        />
      </Svg>

      {/* Center display */}
      <View style={StyleSheet.absoluteFill}>
        <View style={styles.center}>
          <Text style={[styles.speedNumber, { color }]}>{Math.round(speed)}</Text>
          <Text style={styles.unit}>km/h</Text>
          <Text style={styles.label}>CURRENT SPEED</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 20,
  },
  speedNumber: {
    fontSize: 64,
    fontWeight: '700',
    letterSpacing: -2,
    lineHeight: 68,
  },
  unit: {
    ...Typography.h4,
    color: Colors.textSecondary,
    marginTop: 2,
  },
  label: {
    ...Typography.labelSM,
    color: Colors.textMuted,
    marginTop: 4,
    letterSpacing: 1.5,
  },
});
