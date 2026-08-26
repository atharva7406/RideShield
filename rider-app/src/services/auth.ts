// ============================================================
// RideShield — Auth Service
// ============================================================
// Replace mock implementations with real API calls when backend is ready.
// Set Config.USE_MOCK_AUTH = false to use real endpoints.

import { Config } from '../constants/config';
import { storage } from '../utils/storage';
import { apiClient, TOKEN_STORAGE_KEY } from './api';
import type {
  LoginRequest,
  RegisterRequest,
  AuthResponse,
  User,
} from '../types/auth';

export const USER_PROFILE_STORAGE_KEY = 'rideshield_user_profile';

// ---------------------------------------------------------------------------
// MOCK IMPLEMENTATIONS (used when Config.USE_MOCK_AUTH = true)
// ---------------------------------------------------------------------------

const MOCK_USER: User = {
  id: 'mock-user-001',
  fullName: 'Raj Sharma',
  email: 'raj@example.com',
  phone: '+91 98765 43210',
  vehicleType: 'two_wheeler',
  walletBalance: 500.00,
  isPhoneVerified: false, // Set false to demonstrate verification screen on first login
  createdAt: new Date().toISOString(),
};

const MOCK_TOKEN = 'mock-jwt-token-rideshield-dev';

async function mockLogin(req: LoginRequest): Promise<AuthResponse> {
  await new Promise(r => setTimeout(r, 600)); // simulate network delay
  if (!req.email || !req.password) {
    throw new Error('Email and password are required.');
  }
  if (req.password.length < 6) {
    throw new Error('Invalid credentials.');
  }
  return {
    token: MOCK_TOKEN,
    user: { ...MOCK_USER, email: req.email },
  };
}

async function mockRegister(req: RegisterRequest): Promise<AuthResponse> {
  await new Promise(r => setTimeout(r, 600));
  if (!req.fullName || !req.email || !req.password || !req.phone) {
    throw new Error('All fields are required.');
  }
  return {
    token: MOCK_TOKEN,
    user: {
      id: 'mock-user-' + Date.now(),
      fullName: req.fullName,
      email: req.email,
      phone: req.phone,
      vehicleType: req.vehicleType,
      createdAt: new Date().toISOString(),
    },
  };
}

// ---------------------------------------------------------------------------
// REAL API IMPLEMENTATIONS (used when Config.USE_MOCK_AUTH = false)
// ---------------------------------------------------------------------------

async function realLogin(req: LoginRequest): Promise<AuthResponse> {
  const tokenRes = await apiClient.post<{ access_token: string; token_type: string }>('/auth/login/json', {
    email: req.email,
    password: req.password,
  });

  // Temporarily store token so that getHeaders() in apiClient can read it for subsequent requests
  await storage.setItem(TOKEN_STORAGE_KEY, tokenRes.access_token);

  const me = await apiClient.get<any>('/auth/me');
  return {
    token: tokenRes.access_token,
    user: {
      id: me.id,
      fullName: me.full_name,
      email: me.email,
      phone: me.phone_number,
      vehicleType: me.rider_profile?.vehicle_type === '2-wheeler' ? 'two_wheeler' : me.rider_profile?.vehicle_type || 'two_wheeler',
      walletBalance: me.wallet_balance,
      isPhoneVerified: me.is_phone_verified,
      createdAt: me.created_at,
      safetyRating: me.rider_profile?.safety_rating,
      kycStatus: me.rider_profile?.kyc_status,
      licenseNumber: me.rider_profile?.license_number,
    },
  };
}

async function realRegister(req: RegisterRequest): Promise<AuthResponse> {
  await apiClient.post<any>('/auth/register', {
    email: req.email,
    phone_number: req.phone,
    password: req.password,
    full_name: req.fullName,
    role: 'RIDER',
    vehicle_type: req.vehicleType === 'two_wheeler' ? '2-wheeler' : req.vehicleType,
  });

  // Automatically log in user after successful registration
  return realLogin({ email: req.email, password: req.password });
}

// ---------------------------------------------------------------------------
// PUBLIC AUTH SERVICE
// ---------------------------------------------------------------------------

export const authService = {
  async login(req: LoginRequest): Promise<AuthResponse> {
    const response = Config.USE_MOCK_AUTH
      ? await mockLogin(req)
      : await realLogin(req);
    await storage.setItem(TOKEN_STORAGE_KEY, response.token);
    await storage.setItem(USER_PROFILE_STORAGE_KEY, JSON.stringify(response.user));
    return response;
  },

  async register(req: RegisterRequest): Promise<AuthResponse> {
    const response = Config.USE_MOCK_AUTH
      ? await mockRegister(req)
      : await realRegister(req);
    await storage.setItem(TOKEN_STORAGE_KEY, response.token);
    await storage.setItem(USER_PROFILE_STORAGE_KEY, JSON.stringify(response.user));
    return response;
  },

  async logout(): Promise<void> {
    await storage.removeItem(TOKEN_STORAGE_KEY);
    await storage.removeItem(USER_PROFILE_STORAGE_KEY);
  },

  async getStoredToken(): Promise<string | null> {
    return storage.getItem(TOKEN_STORAGE_KEY);
  },

  async getStoredUser(): Promise<User | null> {
    const raw = await storage.getItem(USER_PROFILE_STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  },

  async isLoggedIn(): Promise<boolean> {
    const token = await storage.getItem(TOKEN_STORAGE_KEY);
    return !!token;
  },

  async sendOtp(phone: string): Promise<any> {
    if (Config.USE_MOCK_AUTH) {
      await new Promise(r => setTimeout(r, 500));
      console.log(`[MOCK OTP] Sent code '123456' to ${phone}`);
      return { status: 'success', message: 'Verification code sent' };
    }
    return apiClient.post('/auth/send-otp', { phone_number: phone });
  },

  async verifyOtp(phone: string, code: string): Promise<any> {
    if (Config.USE_MOCK_AUTH) {
      await new Promise(r => setTimeout(r, 600));
      if (code !== '123456') {
        throw new Error('Invalid verification code. Use 123456');
      }
      
      const stored = await storage.getItem(USER_PROFILE_STORAGE_KEY);
      if (stored) {
        const u = JSON.parse(stored) as User;
        u.isPhoneVerified = true;
        u.phone = phone;
        await storage.setItem(USER_PROFILE_STORAGE_KEY, JSON.stringify(u));
        return { status: 'verified', user: u };
      }
      throw new Error('No user profile found');
    }
    return apiClient.post('/auth/verify-otp', { phone_number: phone, code });
  },
};
