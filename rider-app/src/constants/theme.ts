// ============================================================
// RideShield — Spacing & Typography (Vibrant Light)
// ============================================================

export { Colors } from './colors';

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const BorderRadius = {
  sm: 6,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  full: 9999,
};

export const Shadows = {
  soft: {
    boxShadow: '0px 4px 12px rgba(0, 98, 204, 0.08)',
    elevation: 3,
  },
  medium: {
    boxShadow: '0px 8px 24px rgba(0, 98, 204, 0.12)',
    elevation: 6,
  },
};

export const Typography = {
  h1: {
    fontSize: 28,
    fontWeight: '800' as const,
    letterSpacing: -0.5,
  },
  h2: {
    fontSize: 24,
    fontWeight: '700' as const,
    letterSpacing: -0.5,
  },
  h3: {
    fontSize: 20,
    fontWeight: '700' as const,
    letterSpacing: -0.25,
  },
  h4: {
    fontSize: 18,
    fontWeight: '600' as const,
  },
  bodyLG: {
    fontSize: 16,
    fontWeight: '500' as const,
  },
  bodyMD: {
    fontSize: 15,
    fontWeight: '400' as const,
  },
  bodySM: {
    fontSize: 14,
    fontWeight: '400' as const,
  },
  labelMD: {
    fontSize: 13,
    fontWeight: '600' as const,
    letterSpacing: 0.3,
  },
  labelSM: {
    fontSize: 11,
    fontWeight: '600' as const,
    letterSpacing: 0.5,
  },
  caption: {
    fontSize: 12,
    fontWeight: '400' as const,
  },
};
