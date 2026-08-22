// ============================================================
// RideShield — Auth Store (React Context)
// ============================================================

import React, {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import { authService } from '../services/auth';
import type { User, AuthState, LoginRequest, RegisterRequest } from '../types/auth';

// ---------------------------------------------------------------------------
// State & Actions
// ---------------------------------------------------------------------------

type AuthAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_USER'; payload: { user: User; token: string } }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'LOGOUT' };

const initialState: AuthState = {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
};

function authReducer(state: AuthState, action: AuthAction): AuthState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload, error: null };
    case 'SET_USER':
      return {
        ...state,
        user: action.payload.user,
        token: action.payload.token,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    case 'LOGOUT':
      return { ...initialState, isLoading: false };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

interface AuthContextValue {
  state: AuthState;
  login: (req: LoginRequest) => Promise<void>;
  register: (req: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(authReducer, initialState);

  // Check for existing session on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const token = await authService.getStoredToken();
        const storedUser = await authService.getStoredUser();
        if (token) {
          dispatch({
            type: 'SET_USER',
            payload: {
              token,
              user: storedUser ?? {
                id: 'restored-session',
                fullName: 'Raj Sharma',
                email: 'raj@example.com',
                phone: '+91 98765 43210',
                vehicleType: 'two_wheeler',
                createdAt: new Date().toISOString(),
              },
            },
          });
        } else {
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      } catch {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    };
    checkSession();
  }, []);

  const login = useCallback(async (req: LoginRequest) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const response = await authService.login(req);
      dispatch({
        type: 'SET_USER',
        payload: { user: response.user, token: response.token },
      });
    } catch (err: any) {
      dispatch({ type: 'SET_ERROR', payload: err.message ?? 'Login failed.' });
      throw err;
    }
  }, []);

  const register = useCallback(async (req: RegisterRequest) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const response = await authService.register(req);
      dispatch({
        type: 'SET_USER',
        payload: { user: response.user, token: response.token },
      });
    } catch (err: any) {
      dispatch({ type: 'SET_ERROR', payload: err.message ?? 'Registration failed.' });
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    dispatch({ type: 'LOGOUT' });
  }, []);

  const clearError = useCallback(() => {
    dispatch({ type: 'SET_ERROR', payload: null });
  }, []);

  return (
    <AuthContext.Provider value={{ state, login, register, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
