// ============================================================
// RideShield — Claim Types
// ============================================================

export type ClaimStatus =
  | 'submitted'
  | 'under_review'
  | 'approved'
  | 'rejected'
  | 'paid';

export interface Claim {
  id: string;
  claimNumber: string;   // e.g. RS-10291
  shiftId: string;
  userId: string;
  status: ClaimStatus;
  incidentTime: string;
  incidentLatitude: number;
  incidentLongitude: number;
  incidentAddress?: string;
  telemetryCaptured: boolean;
  locationCaptured: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ClaimTimelineStep {
  id: string;
  label: string;
  description: string;
  status: 'completed' | 'active' | 'pending';
  timestamp?: string;
}

export interface CreateClaimRequest {
  shiftId: string;
  incidentTime: string;
  incidentLatitude: number;
  incidentLongitude: number;
  riderConfirmed: boolean;
}

export interface CreateClaimResponse {
  claim: Claim;
}

// Crash event received from backend via Socket.IO
export interface CrashEvent {
  shiftId: string;
  detectedAt: string;
  confidence: number;     // 0-1
  latitude: number;
  longitude: number;
}
