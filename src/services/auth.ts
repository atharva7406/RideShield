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
  return apiClient.post<AuthResponse>('/auth/login', req);
}

async function realRegister(req: RegisterRequest): Promise<AuthResponse> {
  return apiClient.post<AuthResponse>('/auth/register', req);
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
};
