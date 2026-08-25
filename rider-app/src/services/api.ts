// ============================================================
// RideShield — API Service (axios base instance)
// ============================================================
// All backend HTTP calls go through this instance.
// Set Config.API_BASE_URL in src/constants/config.ts to point at your backend.

import { Config } from '../constants/config';
import { storage } from '../utils/storage';

const TOKEN_KEY = 'rideshield_auth_token';

// Minimal fetch-based API client (no axios to keep dependencies lean)
class ApiClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async getHeaders(): Promise<Record<string, string>> {
    const token = await storage.getItem(TOKEN_KEY);
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      'bypass-tunnel-reminder': 'true',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async get<T>(path: string): Promise<T> {
    const headers = await this.getHeaders();
    const response = await fetch(`${this.baseURL}${path}`, {
      method: 'GET',
      headers,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      const msg = err?.detail 
        ? (typeof err.detail === 'object' ? JSON.stringify(err.detail) : err.detail)
        : (err?.message ? (typeof err.message === 'object' ? JSON.stringify(err.message) : err.message) : `HTTP ${response.status}`);
      throw new Error(msg);
    }
    return response.json();
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const headers = await this.getHeaders();
    const response = await fetch(`${this.baseURL}${path}`, {
      method: 'POST',
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      const msg = err?.detail 
        ? (typeof err.detail === 'object' ? JSON.stringify(err.detail) : err.detail)
        : (err?.message ? (typeof err.message === 'object' ? JSON.stringify(err.message) : err.message) : `HTTP ${response.status}`);
      throw new Error(msg);
    }
    return response.json();
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    const headers = await this.getHeaders();
    const response = await fetch(`${this.baseURL}${path}`, {
      method: 'PUT',
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      const msg = err?.detail 
        ? (typeof err.detail === 'object' ? JSON.stringify(err.detail) : err.detail)
        : (err?.message ? (typeof err.message === 'object' ? JSON.stringify(err.message) : err.message) : `HTTP ${response.status}`);
      throw new Error(msg);
    }
    return response.json();
  }
}

export const TOKEN_STORAGE_KEY = TOKEN_KEY;
export const apiClient = new ApiClient(Config.API_BASE_URL);
