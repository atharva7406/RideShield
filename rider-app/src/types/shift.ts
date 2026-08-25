// ============================================================
// RideShield — Shift Types
// ============================================================

export type ShiftStatus = 'idle' | 'active' | 'ended' | 'crashed';

export interface Shift {
  id: string;
  userId: string;
  status: ShiftStatus;
  startedAt: string;
  endedAt?: string;
  durationSeconds?: number;
  distanceKm?: number;
  avgSpeedKmh?: number;
  peakSpeedKmh?: number;
  peakGForce?: number;
  incidentCount?: number;
  premiumPaidInr: number;
  coverageActive: boolean;
}

export interface ShiftSummary {
  shiftId: string;
  duration: string;           // formatted "6h 24m"
  distanceKm: number;
  avgSpeedKmh: number;
  peakSpeedKmh: number;
  peakGForce: number;
  incidentCount: number;
  premiumPaidInr: number;
  startedAt: string;
  endedAt: string;
}

export interface RideHistoryItem {
  id: string;
  date: string;               // formatted display date
  startTime?: string;
  endTime?: string;
  duration: string;
  distanceKm: number;
  premiumInr: number;
  coverageActive: boolean;
  incidentCount: number;
  claimId?: string;
  status?: string;
}

export interface StartShiftRequest {
  userId: string;
}

export interface StartShiftResponse {
  shiftId: string;
  shift: Shift;
}

export interface EndShiftRequest {
  shiftId: string;
}

export interface EndShiftResponse {
  summary: ShiftSummary;
}
