// ─────────────────────────────────────────────────────────────────────────────
// RideShield API Service Layer
// Currently returns mock data. Replace each function body with a real
// fetch/axios call when the FastAPI backend is ready.
// ─────────────────────────────────────────────────────────────────────────────
import { CLAIMS, SHIFTS, POLICIES, RIDERS, ANALYTICS, getClaimById, getRiderById, getShiftById } from '../data/mockData';

const SIMULATED_DELAY = 200; // ms — remove for production

function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
export async function login(email, password) {
  await delay(SIMULATED_DELAY);
  if (email && password) {
    return { token: 'mock-jwt-token', user: { name: 'Sunita Rao', role: 'Insurer Admin', email } };
  }
  throw new Error('Invalid credentials');
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export async function getDashboardStats() {
  await delay(SIMULATED_DELAY);
  return {
    activeShifts: SHIFTS.filter(s => s.status === 'ACTIVE').length,
    activePolicies: POLICIES.filter(p => p.status === 'ACTIVE').length,
    totalClaims: CLAIMS.length,
    verifiedIncidents: CLAIMS.filter(c => c.status !== 'REJECTED').length,
  };
}

export async function getRecentClaims(limit = 3) {
  await delay(SIMULATED_DELAY);
  return CLAIMS.slice(0, limit).map(c => ({
    ...c,
    rider: getRiderById(c.riderId),
  }));
}

// ─── Shifts ──────────────────────────────────────────────────────────────────
export async function getActiveShifts() {
  await delay(SIMULATED_DELAY);
  return SHIFTS.map(s => ({
    ...s,
    rider: getRiderById(s.riderId),
  }));
}

// ─── Claims ──────────────────────────────────────────────────────────────────
export async function getClaims() {
  await delay(SIMULATED_DELAY);
  return CLAIMS.map(c => ({
    ...c,
    rider: getRiderById(c.riderId),
    shift: getShiftById(c.shiftId),
  }));
}

export async function getClaimDetails(claimId) {
  await delay(SIMULATED_DELAY);
  const claim = getClaimById(claimId);
  if (!claim) throw new Error(`Claim ${claimId} not found`);
  return {
    ...claim,
    rider: getRiderById(claim.riderId),
    shift: getShiftById(claim.shiftId),
  };
}

export async function updateClaimStatus(claimId, status) {
  await delay(SIMULATED_DELAY);
  // In production: PATCH /claims/:id { status }
  return { claimId, status, updatedAt: new Date().toISOString() };
}

// ─── Policies ─────────────────────────────────────────────────────────────────
export async function getPolicies() {
  await delay(SIMULATED_DELAY);
  return POLICIES.map(p => ({
    ...p,
    rider: getRiderById(p.riderId),
  }));
}

// ─── Analytics ───────────────────────────────────────────────────────────────
export async function getAnalytics() {
  await delay(SIMULATED_DELAY);
  return ANALYTICS;
}

export async function getRiskDistribution() {
  await delay(SIMULATED_DELAY);
  return ANALYTICS.riskDistribution;
}
