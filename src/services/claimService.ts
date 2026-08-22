// ============================================================
// RideShield — Claim Service
// ============================================================

import { Config } from '../constants/config';
import { apiClient } from './api';
import type {
  Claim,
  ClaimStatus,
  ClaimTimelineStep,
  CreateClaimRequest,
  CreateClaimResponse,
} from '../types/claim';

// ---------------------------------------------------------------------------
// MOCK IMPLEMENTATIONS
// ---------------------------------------------------------------------------

function makeMockClaim(req: CreateClaimRequest): Claim {
  return {
    id: `claim-${Date.now()}`,
    claimNumber: `RS-${10290 + Math.floor(Math.random() * 10)}`,
    shiftId: req.shiftId,
    userId: 'mock-user-001',
    status: 'under_review',
    incidentTime: req.incidentTime,
    incidentLatitude: req.incidentLatitude,
    incidentLongitude: req.incidentLongitude,
    telemetryCaptured: true,
    locationCaptured: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

async function mockCreateClaim(
  req: CreateClaimRequest
): Promise<CreateClaimResponse> {
  await new Promise(r => setTimeout(r, 1000));
  return { claim: makeMockClaim(req) };
}

async function mockGetClaim(id: string): Promise<Claim> {
  await new Promise(r => setTimeout(r, 500));
  return {
    id,
    claimNumber: 'RS-10291',
    shiftId: 'shift-mock',
    userId: 'mock-user-001',
    status: 'under_review',
    incidentTime: new Date().toISOString(),
    incidentLatitude: 28.6139,
    incidentLongitude: 77.209,
    incidentAddress: 'Connaught Place, New Delhi',
    telemetryCaptured: true,
    locationCaptured: true,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// TIMELINE BUILDER
// ---------------------------------------------------------------------------

export function buildClaimTimeline(status: ClaimStatus): ClaimTimelineStep[] {
  const steps: { id: ClaimStatus | 'detected' | 'confirmed'; label: string; description: string }[] = [
    { id: 'detected', label: 'Incident Detected', description: 'Crash event identified by backend sensors.' },
    { id: 'confirmed', label: 'Rider Confirmation', description: 'Rider confirmed need for assistance.' },
    { id: 'submitted', label: 'Claim Submitted', description: 'Claim created and sent for review.' },
    { id: 'under_review', label: 'Under Review', description: 'Our team is reviewing your claim.' },
    { id: 'approved', label: 'Resolution', description: 'Claim resolved and payout processed.' },
  ];

  const statusOrder = ['detected', 'confirmed', 'submitted', 'under_review', 'approved'];
  const currentIdx = statusOrder.indexOf(status === 'rejected' ? 'approved' : status);

  return steps.map((step, idx) => ({
    ...step,
    status:
      idx < currentIdx
        ? 'completed'
        : idx === currentIdx
        ? 'active'
        : 'pending',
  }));
}

// ---------------------------------------------------------------------------
// PUBLIC CLAIM SERVICE
// ---------------------------------------------------------------------------

export const claimService = {
  async createClaim(req: CreateClaimRequest): Promise<CreateClaimResponse> {
    if (Config.USE_MOCK_RIDES) return mockCreateClaim(req);
    return apiClient.post<CreateClaimResponse>('/claim/create', req);
  },

  async getClaim(id: string): Promise<Claim> {
    if (Config.USE_MOCK_RIDES) return mockGetClaim(id);
    return apiClient.get<Claim>(`/claim/${id}`);
  },
};
