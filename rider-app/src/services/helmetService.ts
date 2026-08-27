// ============================================================
// RideShield — Helmet Safety Acknowledgment Service
// ============================================================
// Wraps POST /helmet/acknowledge. There is no photo/ML check anymore —
// the backend cannot verify from a selfie whether a rider keeps a
// helmet on for a whole shift, so this simply records the rider's
// explicit checkbox confirmation. The real consequence (claim
// rejection if a rider is found without a helmet at the time of an
// accident) is enforced at claim-review time, not by this call.

import { Config } from '../constants/config';
import { apiClient } from './api';

export interface HelmetAcknowledgeResult {
  verificationId: string;
  validForMinutes: number;
  message: string;
}

function mockAcknowledge(): Promise<HelmetAcknowledgeResult> {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({
        verificationId: `mock-${Date.now()}`,
        validForMinutes: 15,
        message: 'Helmet safety acknowledgment recorded.',
      });
    }, 300);
  });
}

export const helmetService = {
  async acknowledge(): Promise<HelmetAcknowledgeResult> {
    if (Config.USE_MOCK_RIDES) return mockAcknowledge();

    const res = await apiClient.post<any>('/helmet/acknowledge', {});
    return {
      verificationId: res.verification_id,
      validForMinutes: res.valid_for_minutes,
      message: res.message,
    };
  },
};
