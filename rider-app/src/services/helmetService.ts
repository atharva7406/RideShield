// ============================================================
// RideShield — Helmet Verification Service
// ============================================================
// Wraps POST /helmet/verify. The backend is the sole authority on
// whether a rider is wearing a helmet — this service only uploads the
// selfie and relays the server's verdict; it never computes or assumes
// helmet_worn client-side.

import { Config } from '../constants/config';
import { apiClient } from './api';

export interface HelmetVerifyResult {
  verificationId: string;
  helmetWorn: boolean;
  predictedClass: string;
  confidence: number;
  modelVersion: string;
  validForMinutes: number;
  message: string;
}

function mockVerify(): Promise<HelmetVerifyResult> {
  return new Promise(resolve => {
    setTimeout(() => {
      resolve({
        verificationId: `mock-${Date.now()}`,
        helmetWorn: true,
        predictedClass: 'full_face_helmet',
        confidence: 0.95,
        modelVersion: 'mock',
        validForMinutes: 15,
        message: "Helmet verified. You're clear to start your shift.",
      });
    }, 600);
  });
}

export const helmetService = {
  async verifySelfie(fileUri: string, mimeType: string = 'image/jpeg'): Promise<HelmetVerifyResult> {
    if (Config.USE_MOCK_RIDES) return mockVerify();

    const form = new FormData();
    if (typeof window !== 'undefined' && fileUri.startsWith('data:')) {
      // Web: fileUri is a data: URL from expo-image-picker — convert to a Blob.
      const res = await fetch(fileUri);
      const blob = await res.blob();
      form.append('file', blob, 'selfie.jpg');
    } else {
      // Native: RN's fetch/FormData understands { uri, name, type } directly.
      form.append('file', {
        uri: fileUri,
        name: 'selfie.jpg',
        type: mimeType,
      } as any);
    }

    const res = await apiClient.postForm<any>('/helmet/verify', form);
    return {
      verificationId: res.verification_id,
      helmetWorn: res.helmet_worn,
      predictedClass: res.predicted_class,
      confidence: res.confidence,
      modelVersion: res.model_version,
      validForMinutes: res.valid_for_minutes,
      message: res.message,
    };
  },
};
