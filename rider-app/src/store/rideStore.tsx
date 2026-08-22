// ============================================================
// RideShield — Ride Store (React Context)
// ============================================================

import React, {
  createContext,
  useContext,
  useReducer,
  useCallback,
  ReactNode,
} from 'react';
import type { Shift, ShiftSummary } from '../types/shift';
import type { CrashEvent, Claim } from '../types/claim';

// ---------------------------------------------------------------------------
// State & Actions
// ---------------------------------------------------------------------------

interface RideState {
  activeShift: Shift | null;
  shiftSummary: ShiftSummary | null;
  crashEvent: CrashEvent | null;
  activeClaim: Claim | null;
  isPaymentProcessing: boolean;
  isShiftStarting: boolean;
  isShiftEnding: boolean;
}

type RideAction =
  | { type: 'SET_ACTIVE_SHIFT'; payload: Shift }
  | { type: 'CLEAR_SHIFT' }
  | { type: 'SET_SHIFT_SUMMARY'; payload: ShiftSummary }
  | { type: 'SET_CRASH_EVENT'; payload: CrashEvent | null }
  | { type: 'SET_ACTIVE_CLAIM'; payload: Claim | null }
  | { type: 'SET_PAYMENT_PROCESSING'; payload: boolean }
  | { type: 'SET_SHIFT_STARTING'; payload: boolean }
  | { type: 'SET_SHIFT_ENDING'; payload: boolean };

const initialState: RideState = {
  activeShift: null,
  shiftSummary: null,
  crashEvent: null,
  activeClaim: null,
  isPaymentProcessing: false,
  isShiftStarting: false,
  isShiftEnding: false,
};

function rideReducer(state: RideState, action: RideAction): RideState {
  switch (action.type) {
    case 'SET_ACTIVE_SHIFT':
      return { ...state, activeShift: action.payload, isShiftStarting: false };
    case 'CLEAR_SHIFT':
      return {
        ...state,
        activeShift: null,
        crashEvent: null,
        isShiftEnding: false,
      };
    case 'SET_SHIFT_SUMMARY':
      return { ...state, shiftSummary: action.payload };
    case 'SET_CRASH_EVENT':
      return { ...state, crashEvent: action.payload };
    case 'SET_ACTIVE_CLAIM':
      return { ...state, activeClaim: action.payload };
    case 'SET_PAYMENT_PROCESSING':
      return { ...state, isPaymentProcessing: action.payload };
    case 'SET_SHIFT_STARTING':
      return { ...state, isShiftStarting: action.payload };
    case 'SET_SHIFT_ENDING':
      return { ...state, isShiftEnding: action.payload };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface RideContextValue {
  state: RideState;
  setActiveShift: (shift: Shift) => void;
  clearShift: () => void;
  setShiftSummary: (summary: ShiftSummary) => void;
  setCrashEvent: (event: CrashEvent | null) => void;
  setActiveClaim: (claim: Claim | null) => void;
  setPaymentProcessing: (val: boolean) => void;
  setShiftStarting: (val: boolean) => void;
  setShiftEnding: (val: boolean) => void;
}

const RideContext = createContext<RideContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function RideProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(rideReducer, initialState);

  const setActiveShift = useCallback((shift: Shift) =>
    dispatch({ type: 'SET_ACTIVE_SHIFT', payload: shift }), []);
  const clearShift = useCallback(() =>
    dispatch({ type: 'CLEAR_SHIFT' }), []);
  const setShiftSummary = useCallback((summary: ShiftSummary) =>
    dispatch({ type: 'SET_SHIFT_SUMMARY', payload: summary }), []);
  const setCrashEvent = useCallback((event: CrashEvent | null) =>
    dispatch({ type: 'SET_CRASH_EVENT', payload: event }), []);
  const setActiveClaim = useCallback((claim: Claim | null) =>
    dispatch({ type: 'SET_ACTIVE_CLAIM', payload: claim }), []);
  const setPaymentProcessing = useCallback((val: boolean) =>
    dispatch({ type: 'SET_PAYMENT_PROCESSING', payload: val }), []);
  const setShiftStarting = useCallback((val: boolean) =>
    dispatch({ type: 'SET_SHIFT_STARTING', payload: val }), []);
  const setShiftEnding = useCallback((val: boolean) =>
    dispatch({ type: 'SET_SHIFT_ENDING', payload: val }), []);

  return (
    <RideContext.Provider
      value={{
        state,
        setActiveShift,
        clearShift,
        setShiftSummary,
        setCrashEvent,
        setActiveClaim,
        setPaymentProcessing,
        setShiftStarting,
        setShiftEnding,
      }}
    >
      {children}
    </RideContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useRide(): RideContextValue {
  const ctx = useContext(RideContext);
  if (!ctx) throw new Error('useRide must be used inside RideProvider');
  return ctx;
}
