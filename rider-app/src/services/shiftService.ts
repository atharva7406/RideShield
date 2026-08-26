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
  async createPaymentOrder(premiumAmount: number = 5.0, shiftId?: string): Promise<{
    orderId: string;
    amount: number;
    currency: string;
    keyId: string;
    shiftId: string;
    paymentId: string;
  }> {
    if (Config.USE_MOCK_RIDES) {
      const mockOrd = `order_mock_${Date.now()}`;
      return {
        orderId: mockOrd,
        amount: premiumAmount * 100,
        currency: 'INR',
        keyId: 'rzp_test_mock',
        shiftId: shiftId || `shift-${Date.now()}`,
        paymentId: `pay_mock_${Date.now()}`,
      };
    }

    const res = await apiClient.post<any>('/payments/create-order', {
      shift_id: shiftId || null,
      premium_amount: premiumAmount,
    });

    return {
      orderId: res.order_id,
      amount: res.amount,
      currency: res.currency,
      keyId: res.key_id,
      shiftId: res.shift_id,
      paymentId: res.payment_id,
    };
  },

  async createRechargeOrder(amount: number): Promise<{
    orderId: string;
    amount: number;
    currency: string;
    keyId: string;
    paymentId: string;
  }> {
    if (Config.USE_MOCK_RIDES) {
      const mockOrd = `order_mock_${Date.now()}`;
      return {
        orderId: mockOrd,
        amount: amount * 100,
        currency: 'INR',
        keyId: 'rzp_test_mock',
        paymentId: `pay_mock_${Date.now()}`,
      };
    }

    const res = await apiClient.post<any>('/payments/create-recharge-order', {
      amount,
    });

    return {
      orderId: res.order_id,
      amount: res.amount,
      currency: res.currency,
      keyId: res.key_id,
      paymentId: res.payment_id,
    };
  },

  async verifyPayment(
    razorpayPaymentId: string,
    razorpayOrderId: string,
    razorpaySignature: string
  ): Promise<{
    status: string;
    message: string;
    shiftId: string;
    coverageActive: boolean;
  }> {
    if (Config.USE_MOCK_RIDES) {
      return {
        status: 'verified',
        message: 'Mock payment verified successfully.',
        shiftId: `shift-${Date.now()}`,
        coverageActive: true,
      };
    }

    const res = await apiClient.post<any>('/payments/verify', {
      razorpay_payment_id: razorpayPaymentId,
      razorpay_order_id: razorpayOrderId,
      razorpay_signature: razorpaySignature,
    });

    return {
      status: res.status,
      message: res.message,
      shiftId: res.shift_id,
      coverageActive: res.coverage_active,
    };
  },

  async startShift(userId: string, paymentMethod: string = 'upi', premiumAmount: number = 5.0): Promise<StartShiftResponse> {
    if (Config.USE_MOCK_RIDES) return mockStartShift({ userId });
    
    const backendShift = await apiClient.post<any>('/shifts/start', {
      premium_amount: premiumAmount,
      payment_method: paymentMethod,
    });
    
    return {
      shiftId: backendShift.id,
      shift: {
        id: backendShift.id,
        userId: backendShift.rider_id,
        status: 'active',
        startedAt: backendShift.start_time,
        premiumPaidInr: backendShift.premium_amount,
        coverageActive: true,
      },
    };
  },

  async endShift(shiftId: string, distanceKm?: number): Promise<EndShiftResponse> {
    if (Config.USE_MOCK_RIDES) return mockEndShift(shiftId);
    
    const backendShift = await apiClient.post<any>(`/shifts/${shiftId}/end`, {
      distance_km: distanceKm ?? 0.0,
    });
    
    const summary = backendShift.summary || {};
    const durationStr = summary.duration || '0h 0m';

    return {
      summary: {
        shiftId: backendShift.id,
        duration: durationStr,
        distanceKm: Number(backendShift.distance_km),
        avgSpeedKmh: summary.avgSpeedKmh ?? 0,
        peakSpeedKmh: summary.peakSpeedKmh ?? 0,
        peakGForce: summary.peakGForce ?? 1.0,
        incidentCount: summary.incidentCount ?? 0,
        premiumPaidInr: Number(backendShift.premium_amount),
        startedAt: backendShift.start_time,
        endedAt: backendShift.end_time || new Date().toISOString(),
      },
    };
  },

  async getActiveShift(): Promise<any> {
    if (Config.USE_MOCK_RIDES) return null;
    try {
      const shifts = await apiClient.get<any[]>('/shifts');
      const active = shifts.find(s => s.status === 'ACTIVE');
      return active ? {
        id: active.id,
        userId: active.rider_id,
        status: 'active',
        startedAt: active.start_time,
        premiumPaidInr: active.premium_amount,
        coverageActive: true,
      } : null;
    } catch (err) {
      console.warn('[shiftService] Failed to load active shift:', err);
      return null;
    }
  },

  async getRideHistory(): Promise<RideHistoryItem[]> {
    if (Config.USE_MOCK_RIDES) return mockGetRideHistory();
    
    const backendShifts = await apiClient.get<any[]>('/shifts');
    
    // Sort most recent first
    backendShifts.sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime());

    return backendShifts.map((shift) => {
      const start = new Date(shift.start_time).getTime();
      const end = shift.end_time ? new Date(shift.end_time).getTime() : Date.now();
      const diffMs = end - start;
      const hours = Math.floor(diffMs / 3600000);
      const mins = Math.floor((diffMs % 3600000) / 60000);

      const formatTime = (isoString?: string) => {
        if (!isoString) return '';
        const d = new Date(isoString);
        return d.toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
        });
      };

      return {
        id: shift.id,
        date: new Date(shift.start_time).toLocaleDateString('en-IN', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
        }),
        startTime: formatTime(shift.start_time),
        endTime: shift.end_time ? formatTime(shift.end_time) : 'Active',
        duration: `${hours}h ${mins}m`,
        distanceKm: Number(shift.distance_km),
        premiumInr: Number(shift.premium_amount),
        coverageActive: shift.status === 'ACTIVE' || shift.status === 'COMPLETED',
        incidentCount: shift.summary ? shift.summary.incidentCount : 0,
        status: shift.status,
      };
    });
  },
};
