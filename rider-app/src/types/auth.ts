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
