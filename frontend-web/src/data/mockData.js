// ─────────────────────────────────────────────────────────────────────────────
// RideShield Insurer Dashboard — Mock Data
// Single source of truth. All pages reference this data.
// Replace with real API calls via services/api.js when backend is ready.
// ─────────────────────────────────────────────────────────────────────────────

export const RIDERS = [
  { id: 'RDR-1029', name: 'Rahul Sharma',   initials: 'RS', phone: '+91 98201 34567', vehicle: 'Honda Activa 6G', city: 'Mumbai' },
  { id: 'RDR-4421', name: 'Priya Nair',     initials: 'PN', phone: '+91 97301 88234', vehicle: 'TVS Jupiter',     city: 'Bangalore' },
  { id: 'RDR-0092', name: 'Aditya Verma',   initials: 'AV', phone: '+91 99100 56781', vehicle: 'Bajaj Pulsar 150',city: 'Delhi' },
  { id: 'RDR-5531', name: 'Kavita Joshi',   initials: 'KJ', phone: '+91 93456 12390', vehicle: 'Hero Splendor+',  city: 'Pune' },
  { id: 'RDR-2287', name: 'Deepak Singh',   initials: 'DS', phone: '+91 87654 09123', vehicle: 'Suzuki Access',   city: 'Hyderabad' },
];

export const SHIFTS = [
  { id: 'SHF-8811', riderId: 'RDR-1029', start: '2026-08-22T08:14:00', end: '2026-08-22T14:32:05', duration: '6h 18m', distance: '84.3 km', riskScore: 78, riskLevel: 'HIGH',   premium: 18.50, status: 'ENDED',  coverageStatus: 'EXPIRED' },
  { id: 'SHF-8812', riderId: 'RDR-4421', start: '2026-08-22T09:00:00', end: null,                   duration: '3h 23m', distance: '41.2 km', riskScore: 45, riskLevel: 'MEDIUM', premium: 12.00, status: 'ACTIVE', coverageStatus: 'ACTIVE'  },
  { id: 'SHF-8813', riderId: 'RDR-0092', start: '2026-08-22T07:30:00', end: '2026-08-22T13:45:00', duration: '6h 15m', distance: '72.1 km', riskScore: 22, riskLevel: 'LOW',    premium: 9.50,  status: 'ENDED',  coverageStatus: 'EXPIRED' },
  { id: 'SHF-8814', riderId: 'RDR-5531', start: '2026-08-22T10:15:00', end: null,                   duration: '2h 08m', distance: '28.7 km', riskScore: 61, riskLevel: 'MEDIUM', premium: 14.00, status: 'ACTIVE', coverageStatus: 'ACTIVE'  },
  { id: 'SHF-8815', riderId: 'RDR-2287', start: '2026-08-22T11:00:00', end: null,                   duration: '1h 23m', distance: '19.4 km', riskScore: 15, riskLevel: 'LOW',    premium: 8.00,  status: 'ACTIVE', coverageStatus: 'ACTIVE'  },
  { id: 'SHF-8816', riderId: 'RDR-1029', start: '2026-08-21T08:00:00', end: '2026-08-21T15:10:00', duration: '7h 10m', distance: '91.2 km', riskScore: 81, riskLevel: 'HIGH',   premium: 20.00, status: 'ENDED',  coverageStatus: 'EXPIRED' },
];

export const POLICIES = [
  { id: 'POL-5001', riderId: 'RDR-1029', type: 'Shift-Based Micro', shiftCount: 48, premiumPaid: 892.50,  status: 'ACTIVE',   startDate: '2026-06-01', endDate: '2026-12-31' },
  { id: 'POL-5002', riderId: 'RDR-4421', type: 'Shift-Based Micro', shiftCount: 31, premiumPaid: 372.00,  status: 'ACTIVE',   startDate: '2026-07-01', endDate: '2026-12-31' },
  { id: 'POL-5003', riderId: 'RDR-0092', type: 'Shift-Based Micro', shiftCount: 62, premiumPaid: 589.00,  status: 'ACTIVE',   startDate: '2026-05-15', endDate: '2026-11-15' },
  { id: 'POL-5004', riderId: 'RDR-5531', type: 'Shift-Based Micro', shiftCount: 19, premiumPaid: 266.00,  status: 'ACTIVE',   startDate: '2026-08-01', endDate: '2027-01-31' },
  { id: 'POL-5005', riderId: 'RDR-2287', type: 'Shift-Based Micro', shiftCount: 7,  premiumPaid: 56.00,   status: 'ACTIVE',   startDate: '2026-08-15', endDate: '2027-02-15' },
];

// ─── Sensor telemetry data for charts ──────────────────────────────────────
// 30 data points at ~1s intervals. Crash event at index 20.
function generateTelemetry(crashAt = 20) {
  return Array.from({ length: 30 }, (_, i) => {
    const isCrash = i === crashAt;
    const isPostCrash = i > crashAt && i < crashAt + 4;
    const accel = isCrash
      ? 8.7 + Math.random() * 0.5
      : isPostCrash
      ? 0.2 + Math.random() * 0.3
      : 0.8 + Math.random() * 0.6;
    const gyro = isCrash
      ? 5.2 + Math.random() * 0.4
      : isPostCrash
      ? 0.1 + Math.random() * 0.2
      : 0.3 + Math.random() * 0.4;
    return {
      t: i,
      label: `${String(9).padStart(2,'0')}:43:${String(i).padStart(2,'0')}`,
      accel: parseFloat(accel.toFixed(2)),
      gyro: parseFloat(gyro.toFixed(2)),
      baseline: 0.95,
      threshold: 4.5,
    };
  });
}

// ─── Incident timelines ─────────────────────────────────────────────────────
const TIMELINE_001 = [
  { time: '09:41:02', event: 'Normal telemetry',         type: 'normal' },
  { time: '09:41:17', event: 'Hard braking detected',    type: 'warning' },
  { time: '09:42:03', event: 'Normal telemetry',         type: 'normal' },
  { time: '09:43:11', event: 'Crash candidate detected', type: 'alert' },
  { time: '09:43:12', event: 'L1 alert triggered',       type: 'alert' },
  { time: '09:43:27', event: 'No rider response',        type: 'warning' },
  { time: '09:43:29', event: 'L2 escalation initiated',  type: 'escalation' },
  { time: '09:43:42', event: 'Sensor fusion passed',     type: 'verified' },
  { time: '09:43:45', event: 'Claim auto-generated',     type: 'claim' },
];

const TIMELINE_002 = [
  { time: '11:12:05', event: 'Normal telemetry',          type: 'normal' },
  { time: '11:14:22', event: 'Speed anomaly: 68 km/h',    type: 'warning' },
  { time: '11:15:01', event: 'Crash candidate detected',  type: 'alert' },
  { time: '11:15:02', event: 'L1 alert triggered',        type: 'alert' },
  { time: '11:15:14', event: 'Rider responded: "I\'m OK"',type: 'safe' },
  { time: '11:15:17', event: 'Incident dismissed (L1)',   type: 'normal' },
  { time: '11:17:42', event: 'Crash candidate detected',  type: 'alert' },
  { time: '11:17:43', event: 'L1 alert triggered',        type: 'alert' },
  { time: '11:17:58', event: 'No rider response',         type: 'warning' },
  { time: '11:18:00', event: 'L2 escalation initiated',   type: 'escalation' },
  { time: '11:18:15', event: 'L3 sensor fusion passed',   type: 'verified' },
  { time: '11:18:18', event: 'Claim auto-generated',      type: 'claim' },
];

// ─── Main claims data ───────────────────────────────────────────────────────
export const CLAIMS = [
  {
    id: 'CLM-001',
    riderId: 'RDR-1029',
    shiftId: 'SHF-8811',
    timestamp: '2026-08-22T09:43:45',
    dateDisplay: 'Aug 22, 2026',
    timeDisplay: '09:43:45 IST',
    location: 'Worli Naka, Mumbai',
    locationDetails: 'Near Worli Sea Link toll',
    lat: 19.0178,
    lng: 72.8178,
    riskLevel: 'HIGH',
    status: 'UNDER_REVIEW',
    severity: 'Severe Impact',
    crashConfidence: 94,
    riskScore: 78,
    timeline: TIMELINE_001,
    telemetry: generateTelemetry(20),
    escalation: [
      { level: 'L1', label: 'On-Device Alert',  time: '09:43:12', status: 'NO_RESPONSE', note: '15-second countdown. No response.' },
      { level: 'L2', label: 'Multi-Channel',    time: '09:43:29', status: 'TRIGGERED',   note: 'SMS + WhatsApp + IVR sent via Twilio.' },
      { level: 'L3', label: 'Sensor Fusion',    time: '09:43:42', status: 'VERIFIED',    note: 'GPS + Motion + Stillness fusion passed.' },
    ],
    evidence: {
      gps: { lat: 19.0178, lng: 72.8178, accuracy: '4m' },
      peakAccel: '8.7g',
      gyroVariance: '5.2',
      jerk: '12.4 m/s³',
      postEventStillness: '18s',
      rollingBaseline: '0.95g',
      classifierScore: 0.94,
      verificationMethod: 'Sensor Fusion (L3)',
    },
  },
  {
    id: 'CLM-002',
    riderId: 'RDR-4421',
    shiftId: 'SHF-8812',
    timestamp: '2026-08-22T11:18:18',
    dateDisplay: 'Aug 22, 2026',
    timeDisplay: '11:18:18 IST',
    location: 'Koramangala, Bangalore',
    locationDetails: 'Near Koramangala 6th Block',
    lat: 12.9352,
    lng: 77.6245,
    riskLevel: 'MEDIUM',
    status: 'PENDING',
    severity: 'Minor Scrape',
    crashConfidence: 71,
    riskScore: 45,
    timeline: TIMELINE_002,
    telemetry: generateTelemetry(22),
    escalation: [
      { level: 'L1', label: 'On-Device Alert',  time: '11:17:43', status: 'NO_RESPONSE', note: '15-second countdown. No response.' },
      { level: 'L2', label: 'Multi-Channel',    time: '11:18:00', status: 'TRIGGERED',   note: 'SMS + WhatsApp sent.' },
      { level: 'L3', label: 'Sensor Fusion',    time: '11:18:15', status: 'VERIFIED',    note: 'Fusion passed with moderate confidence.' },
    ],
    evidence: {
      gps: { lat: 12.9352, lng: 77.6245, accuracy: '6m' },
      peakAccel: '5.1g',
      gyroVariance: '3.8',
      jerk: '7.2 m/s³',
      postEventStillness: '9s',
      rollingBaseline: '0.88g',
      classifierScore: 0.71,
      verificationMethod: 'Sensor Fusion (L3)',
    },
  },
  {
    id: 'CLM-003',
    riderId: 'RDR-0092',
    shiftId: 'SHF-8813',
    timestamp: '2026-08-22T13:02:30',
    dateDisplay: 'Aug 22, 2026',
    timeDisplay: '13:02:30 IST',
    location: 'Connaught Place, Delhi',
    locationDetails: 'Near Rajiv Chowk Metro',
    lat: 28.6315,
    lng: 77.2167,
    riskLevel: 'LOW',
    status: 'APPROVED',
    severity: 'Equipment Damage',
    crashConfidence: 88,
    riskScore: 22,
    timeline: [
      { time: '13:00:11', event: 'Normal telemetry',         type: 'normal' },
      { time: '13:02:14', event: 'Crash candidate detected', type: 'alert' },
      { time: '13:02:15', event: 'L1 alert triggered',       type: 'alert' },
      { time: '13:02:30', event: 'No rider response',        type: 'warning' },
      { time: '13:02:32', event: 'L2 escalation initiated',  type: 'escalation' },
      { time: '13:02:44', event: 'Sensor fusion passed',     type: 'verified' },
      { time: '13:02:47', event: 'Claim auto-generated',     type: 'claim' },
    ],
    telemetry: generateTelemetry(18),
    escalation: [
      { level: 'L1', label: 'On-Device Alert', time: '13:02:15', status: 'NO_RESPONSE', note: 'No response in 15s.' },
      { level: 'L2', label: 'Multi-Channel',   time: '13:02:32', status: 'TRIGGERED',   note: 'Twilio SMS sent.' },
      { level: 'L3', label: 'Sensor Fusion',   time: '13:02:44', status: 'VERIFIED',    note: 'All signals verified.' },
    ],
    evidence: {
      gps: { lat: 28.6315, lng: 77.2167, accuracy: '5m' },
      peakAccel: '7.2g',
      gyroVariance: '4.1',
      jerk: '9.8 m/s³',
      postEventStillness: '22s',
      rollingBaseline: '0.91g',
      classifierScore: 0.88,
      verificationMethod: 'Sensor Fusion (L3)',
    },
  },
  {
    id: 'CLM-004',
    riderId: 'RDR-5531',
    shiftId: 'SHF-8814',
    timestamp: '2026-08-22T12:55:00',
    dateDisplay: 'Aug 22, 2026',
    timeDisplay: '12:55:00 IST',
    location: 'Shivajinagar, Pune',
    locationDetails: 'FC Road Junction',
    lat: 18.5311,
    lng: 73.8467,
    riskLevel: 'MEDIUM',
    status: 'PENDING',
    severity: 'Minor Impact',
    crashConfidence: 62,
    riskScore: 61,
    timeline: [
      { time: '12:53:00', event: 'Normal telemetry',         type: 'normal' },
      { time: '12:55:00', event: 'Crash candidate detected', type: 'alert' },
      { time: '12:55:01', event: 'L1 alert triggered',       type: 'alert' },
      { time: '12:55:16', event: 'No rider response',        type: 'warning' },
      { time: '12:55:18', event: 'L2 escalation initiated',  type: 'escalation' },
      { time: '12:55:28', event: 'Sensor fusion — partial',  type: 'warning' },
      { time: '12:55:31', event: 'Claim auto-generated',     type: 'claim' },
    ],
    telemetry: generateTelemetry(19),
    escalation: [
      { level: 'L1', label: 'On-Device Alert', time: '12:55:01', status: 'NO_RESPONSE', note: 'No response in 15s.' },
      { level: 'L2', label: 'Multi-Channel',   time: '12:55:18', status: 'TRIGGERED',   note: 'Twilio SMS + WhatsApp sent.' },
      { level: 'L3', label: 'Sensor Fusion',   time: '12:55:28', status: 'PARTIAL',     note: 'Partial confidence — under review.' },
    ],
    evidence: {
      gps: { lat: 18.5311, lng: 73.8467, accuracy: '8m' },
      peakAccel: '4.8g',
      gyroVariance: '2.9',
      jerk: '6.1 m/s³',
      postEventStillness: '7s',
      rollingBaseline: '0.92g',
      classifierScore: 0.62,
      verificationMethod: 'Sensor Fusion (L3 — Partial)',
    },
  },
  {
    id: 'CLM-005',
    riderId: 'RDR-2287',
    shiftId: 'SHF-8815',
    timestamp: '2026-08-21T16:22:10',
    dateDisplay: 'Aug 21, 2026',
    timeDisplay: '16:22:10 IST',
    location: 'Banjara Hills, Hyderabad',
    locationDetails: 'Road No. 12',
    lat: 17.4156,
    lng: 78.4347,
    riskLevel: 'HIGH',
    status: 'REJECTED',
    severity: 'Severe Impact',
    crashConfidence: 91,
    riskScore: 83,
    timeline: [
      { time: '16:20:00', event: 'Normal telemetry',         type: 'normal' },
      { time: '16:22:05', event: 'Crash candidate detected', type: 'alert' },
      { time: '16:22:06', event: 'L1 alert triggered',       type: 'alert' },
      { time: '16:22:21', event: 'No rider response',        type: 'warning' },
      { time: '16:22:23', event: 'L2 escalation initiated',  type: 'escalation' },
      { time: '16:22:35', event: 'Sensor fusion passed',     type: 'verified' },
      { time: '16:22:38', event: 'Claim auto-generated',     type: 'claim' },
      { time: '16:45:00', event: 'Claim rejected — duplicate',type: 'warning' },
    ],
    telemetry: generateTelemetry(16),
    escalation: [
      { level: 'L1', label: 'On-Device Alert', time: '16:22:06', status: 'NO_RESPONSE', note: 'No response in 15s.' },
      { level: 'L2', label: 'Multi-Channel',   time: '16:22:23', status: 'TRIGGERED',   note: 'All channels triggered.' },
      { level: 'L3', label: 'Sensor Fusion',   time: '16:22:35', status: 'VERIFIED',    note: 'All signals verified.' },
    ],
    evidence: {
      gps: { lat: 17.4156, lng: 78.4347, accuracy: '3m' },
      peakAccel: '9.1g',
      gyroVariance: '6.3',
      jerk: '14.2 m/s³',
      postEventStillness: '28s',
      rollingBaseline: '0.89g',
      classifierScore: 0.91,
      verificationMethod: 'Sensor Fusion (L3)',
    },
  },
  {
    id: 'CLM-006',
    riderId: 'RDR-1029',
    shiftId: 'SHF-8816',
    timestamp: '2026-08-21T14:15:00',
    dateDisplay: 'Aug 21, 2026',
    timeDisplay: '14:15:00 IST',
    location: 'Bandra West, Mumbai',
    locationDetails: 'Carter Road Junction',
    lat: 19.0596,
    lng: 72.8295,
    riskLevel: 'HIGH',
    status: 'APPROVED',
    severity: 'Severe Impact',
    crashConfidence: 97,
    riskScore: 81,
    timeline: [
      { time: '14:13:00', event: 'Normal telemetry',         type: 'normal' },
      { time: '14:15:00', event: 'Crash candidate detected', type: 'alert' },
      { time: '14:15:01', event: 'L1 alert triggered',       type: 'alert' },
      { time: '14:15:16', event: 'No rider response',        type: 'warning' },
      { time: '14:15:18', event: 'L2 escalation initiated',  type: 'escalation' },
      { time: '14:15:29', event: 'Sensor fusion passed',     type: 'verified' },
      { time: '14:15:32', event: 'Claim auto-generated',     type: 'claim' },
    ],
    telemetry: generateTelemetry(21),
    escalation: [
      { level: 'L1', label: 'On-Device Alert', time: '14:15:01', status: 'NO_RESPONSE', note: 'No response in 15s.' },
      { level: 'L2', label: 'Multi-Channel',   time: '14:15:18', status: 'TRIGGERED',   note: 'All channels triggered.' },
      { level: 'L3', label: 'Sensor Fusion',   time: '14:15:29', status: 'VERIFIED',    note: 'Highest confidence verified.' },
    ],
    evidence: {
      gps: { lat: 19.0596, lng: 72.8295, accuracy: '2m' },
      peakAccel: '10.2g',
      gyroVariance: '7.1',
      jerk: '16.8 m/s³',
      postEventStillness: '35s',
      rollingBaseline: '0.87g',
      classifierScore: 0.97,
      verificationMethod: 'Sensor Fusion (L3)',
    },
  },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────
export function getRiderById(id) {
  return RIDERS.find(r => r.id === id);
}

export function getShiftById(id) {
  return SHIFTS.find(s => s.id === id);
}

export function getClaimById(id) {
  return CLAIMS.find(c => c.id === id);
}

export const ANALYTICS = {
  totalShifts: 342,
  activeShifts: 3,
  totalPolicies: 5,
  totalClaims: CLAIMS.length,
  verifiedIncidents: 5,
  approvedClaims: 2,
  rejectedClaims: 1,
  pendingClaims: 2,
  underReviewClaims: 1,
  avgResponseTime: '23s',
  riskDistribution: { low: 75, medium: 20, high: 5 },
  claimsByWeek: [
    { week: 'Week 1', claims: 1 },
    { week: 'Week 2', claims: 3 },
    { week: 'Week 3', claims: 2 },
    { week: 'Week 4', claims: 6 },
  ],
};
