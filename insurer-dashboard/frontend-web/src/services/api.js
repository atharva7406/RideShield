// ─────────────────────────────────────────────────────────────────────────────
// RideShield API Service Layer — Real Backend Integration
// ─────────────────────────────────────────────────────────────────────────────

const API_BASE_URL = 'http://localhost:8000';

async function request(path, options = {}) {
  const token = localStorage.getItem('insurer_token');
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...options.headers,
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }
  
  return response.json();
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
export async function register(fullName, email, phone, password) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      email,
      phone_number: phone,
      password,
      full_name: fullName,
      role: 'INSURER',
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}

export async function login(email, password) {
  // Use OAuth2 Password Request flow (form urlencoded)
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);

  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Accept: 'application/json',
    },
    body: params.toString(),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }

  const tokenRes = await response.json();
  localStorage.setItem('insurer_token', tokenRes.access_token);

  // Fetch current user details
  const userDetails = await request('/auth/me');
  return {
    token: tokenRes.access_token,
    user: {
      name: userDetails.full_name,
      role: userDetails.role,
      email: userDetails.email,
    },
  };
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export async function getDashboardStats() {
  const shifts = await request('/shifts');
  const claims = await request('/claims');
  const incidents = await request('/incidents');
  
  return {
    activeShifts: shifts.filter(s => s.status === 'ACTIVE').length,
    activePolicies: shifts.filter(s => s.status === 'ACTIVE').length,
    totalClaims: claims.length,
    verifiedIncidents: incidents.length,
  };
}

// ─── Incidents ────────────────────────────────────────────────────────────────
export async function getIncidents() {
  const incidents = await request('/incidents');
  return incidents.map(i => ({
    id: i.id,
    shiftId: i.shift_id,
    riderId: i.rider_id,
    status: i.status,
    detectedAt: i.detected_at,
    peakGForce: Number(i.peak_g_force),
    confidenceScore: Number(i.confidence_score),
    latitude: Number(i.latitude),
    longitude: Number(i.longitude),
  }));
}

export async function getRecentClaims(limit = 3) {
  const claims = await request('/claims');
  // Sort claims by filed_at descending
  const sorted = [...claims].sort((a, b) => new Date(b.filed_at) - new Date(a.filed_at));
  
  return sorted.slice(0, limit).map(c => ({
    id: c.id,
    claimNumber: c.claim_number,
    shiftId: c.shift_id,
    status: c.status,
    claimedAmount: Number(c.claimed_amount),
    approvedAmount: c.approved_amount ? Number(c.approved_amount) : null,
    filedAt: c.filed_at,
    updatedAt: c.updated_at,
    rider: {
      fullName: 'Gig Rider', // Fallback or resolved name
      phone: 'N/A',
    },
  }));
}

// ─── Shifts ──────────────────────────────────────────────────────────────────
export async function getActiveShifts() {
  const shifts = await request('/shifts');
  return shifts.map(s => ({
    id: s.id,
    status: s.status,
    startedAt: s.start_time,
    endedAt: s.end_time,
    distanceKm: Number(s.distance_km),
    premiumPaidInr: Number(s.premium_amount),
    policyNumber: s.policy_number,
    rider: {
      fullName: 'Gig Rider',
    },
  }));
}

// ─── Claims ──────────────────────────────────────────────────────────────────
export async function getClaims() {
  const claims = await request('/claims');
  return claims.map(c => ({
    id: c.id,
    claimNumber: c.claim_number,
    shiftId: c.shift_id,
    status: c.status,
    claimedAmount: Number(c.claimed_amount),
    approvedAmount: c.approved_amount ? Number(c.approved_amount) : null,
    filedAt: c.filed_at,
    updatedAt: c.updated_at,
    rider: {
      fullName: 'Gig Rider',
    },
    shift: {
      policyNumber: 'N/A',
    },
  }));
}

export async function getClaimDetails(claimId) {
  const claim = await request(`/claims/${claimId}`);
  const incident = await request(`/incidents/${claim.incident_id}`);
  
  return {
    id: claim.id,
    claimNumber: claim.claim_number,
    shiftId: claim.shift_id,
    status: claim.status,
    claimedAmount: Number(claim.claimed_amount),
    approvedAmount: claim.approved_amount ? Number(claim.approved_amount) : null,
    filedAt: claim.filed_at,
    updatedAt: claim.updated_at,
    rejectionReason: claim.rejection_reason,
    rider: {
      fullName: 'Gig Rider',
      phone: 'N/A',
    },
    shift: {
      policyNumber: 'N/A',
      startedAt: incident.detected_at,
    },
    incident: {
      peakGForce: Number(incident.peak_g_force),
      confidenceScore: Number(incident.confidence_score),
      latitude: incident.latitude,
      detectedAt: incident.detected_at,
    },
    medicalReports: claim.medical_reports || [],
  };
}

export async function updateClaimStatus(claimId, status) {
  let endpoint = `/claims/${claimId}/reject?rejection_reason=Rejected%20by%20Insurer`;
  if (status === 'APPROVED') {
    // Get claim details to get claim amount for approval
    const claim = await request(`/claims/${claimId}`);
    endpoint = `/claims/${claimId}/approve?approved_amount=${claim.claimed_amount}`;
  }
  
  const updatedClaim = await request(endpoint, {
    method: 'POST',
  });
  
  return {
    claimId: updatedClaim.id,
    status: updatedClaim.status,
    updatedAt: updatedClaim.updated_at,
  };
}

export async function startClaimReview(claimId) {
  const updatedClaim = await request(`/claims/${claimId}/review`, {
    method: 'POST',
  });
  return {
    claimId: updatedClaim.id,
    status: updatedClaim.status,
    updatedAt: updatedClaim.updated_at,
  };
}

export async function uploadMedicalReport(claimId, file, documentType, notes) {
  const token = localStorage.getItem('insurer_token');
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);
  if (notes) formData.append('notes', notes);

  const response = await fetch(`${API_BASE_URL}/claims/${claimId}/reports`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}

export async function downloadMedicalReport(claimId, reportId) {
  const token = localStorage.getItem('insurer_token');
  const response = await fetch(`${API_BASE_URL}/claims/${claimId}/reports/${reportId}/download`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP Error ${response.status}`);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `medical_report_${reportId}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// ─── Policies ─────────────────────────────────────────────────────────────────
export async function getPolicies() {
  const shifts = await request('/shifts');
  return shifts.map(s => ({
    id: s.id,
    policyNumber: s.policy_number,
    status: s.status === 'ACTIVE' ? 'ACTIVE' : 'EXPIRED',
    premiumPaidInr: Number(s.premium_amount),
    startedAt: s.start_time,
    endedAt: s.end_time,
    rider: {
      fullName: 'Gig Rider',
    },
  }));
}

// ─── Analytics ───────────────────────────────────────────────────────────────
export async function getAnalytics() {
  const shifts = await request('/shifts');
  const claims = await request('/claims');
  
  return {
    totalShifts: shifts.length,
    activePolicies: shifts.filter(s => s.status === 'ACTIVE').length,
    claimsSubmitted: claims.length,
    payoutAmount: claims.reduce((acc, c) => acc + (c.approved_amount ? Number(c.approved_amount) : 0), 0),
  };
}

export async function getRiskDistribution() {
  const shifts = await request('/shifts');
  const total = shifts.length || 1;
  const activeCount = shifts.filter(s => s.status === 'ACTIVE').length;
  
  return {
    low: Math.round((activeCount / total) * 100),
    medium: Math.round(((shifts.length - activeCount) / total) * 100),
    high: 0,
  };
}
