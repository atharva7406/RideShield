// ============================================================
// RideShield — Environment Configuration
// ============================================================
// Change API_BASE_URL and SOCKET_URL when pointing to a real backend.
// On physical device, replace with your machine's local IP.
// e.g. http://192.168.1.100:4000


// src/constants/config.ts
const DEV_IP = '10.205.6.188'; // <-- Updated to your new hotspot IP

export const Config = {
  // Main's teammate had this pointed at a personal localtunnel URL
  // (ephemeral, tied to their machine's tunnel session) — reverted to
  // DEV_IP-based so it works for whoever's running the backend locally.
  API_BASE_URL: `http://${DEV_IP}:8000`,
  SOCKET_URL: `http://${DEV_IP}:8000`,

  // Feature flags
  USE_MOCK_AUTH: false,        // set false when real auth backend is ready
  USE_MOCK_PAYMENT: false,     // set false when UPI provider is integrated
  USE_MOCK_RIDES: false,       // set false when rides API is ready
  ENABLE_DEV_CRASH_TRIGGER: true, // dev-only: simulate CRASH_DETECTED event

  // Telemetry
  TELEMETRY_EMIT_INTERVAL_MS: 1000, // how often to emit telemetry to backend
  TELEMETRY_SENSOR_INTERVAL_MS: 200, // how often sensors update internally

  // Shift premium
  DAILY_PREMIUM_INR: 5,

  // Shift premium tiers
  PREMIUM_TIERS: [
    { premium: 3, coverage: 10000, label: 'Starter' },
    { premium: 5, coverage: 25000, label: 'Standard' },
    { premium: 7, coverage: 50000, label: 'Plus' },
    { premium: 10, coverage: 100000, label: 'Premium' },
  ],

  // WhatsApp Bot number (E.164 format without '+' or spaces for wa.me URL compatibility)
  WHATSAPP_BOT_PHONE_NUMBER: '15550101234',
};
