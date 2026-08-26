// ============================================================
// RideShield — UUID Utility
// ============================================================
// Minimal RFC4122 v4 generator. Used only as a client-side correlation
// ID (client_incident_id) — collision resistance, not cryptographic
// security, is what matters here, so Math.random is sufficient and
// avoids pulling in expo-crypto as a new native dependency for one ID.

export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
