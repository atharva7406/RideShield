// ============================================================
// RideShield — Auth Types
// ============================================================

export interface User {
  id: string;
  fullName: string;
  email: string;
  phone: string;
  vehicleType: VehicleType;
  walletBalance?: number;
  isPhoneVerified?: boolean;
  createdAt: string;
  // From the rider_profile the backend nests under /auth/me — not part of
  // the core User row. safetyRating: 0-5 (higher = safer), backend
  // default 5.00. kycStatus: backend's own strings ("PENDING" | "APPROVED"
  // | "REJECTED"), not a fixed enum here since the backend column is a
  // plain string, not a DB enum.
  safetyRating?: number;
  kycStatus?: string;
  licenseNumber?: string | null;
}

export type VehicleType =
  | 'two_wheeler'
  | 'three_wheeler'
  | 'four_wheeler'
  | 'bicycle';

export const VehicleTypeLabels: Record<VehicleType, string> = {
  two_wheeler: 'Two Wheeler (Bike/Scooter)',
  three_wheeler: 'Three Wheeler (Auto)',
  four_wheeler: 'Four Wheeler (Car/Taxi)',
  bicycle: 'Bicycle',
};

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  fullName: string;
  email: string;
  password: string;
  phone: string;
  vehicleType: VehicleType;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
