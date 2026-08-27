// ============================================================
// RideShield — Shift Service
// ============================================================

import { Config } from '../constants/config';
import { apiClient } from './api';
import type {
  StartShiftRequest,
  StartShiftResponse,
  EndShiftResponse,
  RideHistoryItem,
} from '../types/shift';

// ---------------------------------------------------------------------------
// MOCK IMPLEMENTATIONS
// ---------------------------------------------------------------------------

let mockShiftIdCounter = 10001;

async function mockStartShift(
  _req: StartShiftRequest
): Promise<StartShiftResponse> {
  await new Promise(r => setTimeout(r, 600));
  const id = `shift-${Date.now()}`;
  return {
    shiftId: id,
    shift: {
      id,
      userId: _req.userId,
      status: 'active',
      startedAt: new Date().toISOString(),
      premiumPaidInr: Config.DAILY_PREMIUM_INR,
      coverageActive: true,
    },
  };
}

async function mockEndShift(shiftId: string): Promise<EndShiftResponse> {
  await new Promise(r => setTimeout(r, 800));
  return {
    summary: {
      shiftId,
      duration: '2h 15m',
      distanceKm: 34.7,
      avgSpeedKmh: 28,
      peakSpeedKmh: 62,
      peakGForce: 2.3,
      incidentCount: 0,
      premiumPaidInr: Config.DAILY_PREMIUM_INR,
      startedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      endedAt: new Date().toISOString(),
    },
  };
}

const MOCK_RIDE_HISTORY: RideHistoryItem[] = [
  {
    id: 'h1',
    date: '21 Aug 2026',
    duration: '6h 24m',
    distanceKm: 87.4,
    premiumInr: 5,
    coverageActive: true,
    incidentCount: 0,
  },
  {
    id: 'h2',
    date: '20 Aug 2026',
    duration: '5h 10m',
    distanceKm: 71.2,
    premiumInr: 5,
    coverageActive: true,
    incidentCount: 1,
    claimId: 'RS-10288',
  },
  {
    id: 'h3',
    date: '19 Aug 2026',
    duration: '4h 45m',
    distanceKm: 62.1,
    premiumInr: 5,
    coverageActive: true,
    incidentCount: 0,
  },
  {
    id: 'h4',
    date: '18 Aug 2026',
    duration: '7h 02m',
    distanceKm: 94.8,
    premiumInr: 5,
    coverageActive: true,
    incidentCount: 0,
  },
  {
    id: 'h5',
    date: '17 Aug 2026',
    duration: '3h 30m',
    distanceKm: 45.3,
    premiumInr: 5,
    coverageActive: true,
    incidentCount: 0,
  },
];

async function mockGetRideHistory(): Promise<RideHistoryItem[]> {
  await new Promise(r => setTimeout(r, 500));
  return MOCK_RIDE_HISTORY;
}

// ---------------------------------------------------------------------------
// PUBLIC SHIFT SERVICE
// ---------------------------------------------------------------------------

export const shiftService = {
  async startShift(userId: string): Promise<StartShiftResponse> {
    if (Config.USE_MOCK_RIDES) return mockStartShift({ userId });
    return apiClient.post<StartShiftResponse>('/shift/start', { userId });
  },

  async endShift(shiftId: string): Promise<EndShiftResponse> {
    if (Config.USE_MOCK_RIDES) return mockEndShift(shiftId);
    return apiClient.post<EndShiftResponse>('/shift/end', { shiftId });
  },

  async getRideHistory(): Promise<RideHistoryItem[]> {
    if (Config.USE_MOCK_RIDES) return mockGetRideHistory();
    return apiClient.get<RideHistoryItem[]>('/rides');
  },
};
