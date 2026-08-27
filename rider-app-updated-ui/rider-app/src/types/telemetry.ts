// ============================================================
// RideShield — Telemetry Types
// ============================================================

export interface LocationData {
  latitude: number;
  longitude: number;
  speed: number | null;       // m/s from GPS
  speedKmh: number | null;    // converted to km/h
  heading: number | null;     // degrees 0-360
  accuracy: number | null;    // meters
  altitude: number | null;
  timestamp: number;
}

export interface AccelerometerData {
  x: number;
  y: number;
  z: number;
  magnitude: number;  // sqrt(x²+y²+z²)
  gForce: number;     // magnitude / 9.81
  timestamp: number;
}

export interface GyroscopeData {
  x: number;
  y: number;
  z: number;
  magnitude: number;  // degrees/s combined
  timestamp: number;
}

export interface TelemetryData {
  location: LocationData | null;
  speed: number;          // km/h
  acceleration: AccelerometerData | null;
  gForce: number;         // G
  gyroscope: GyroscopeData | null;
  timestamp: number;
  connectionStatus: TelemetryConnectionStatus;
  isSimulated: boolean;
}

export interface TelemetryConnectionStatus {
  gps: 'connected' | 'connecting' | 'disconnected';
  motion: 'connected' | 'connecting' | 'disconnected';
  backend: 'connected' | 'connecting' | 'disconnected';
}

// Payload sent to backend via Socket.IO
export interface TelemetryPayload {
  shiftId: string;
  timestamp: number;
  latitude: number;
  longitude: number;
  speed: number;
  heading: number | null;
  acceleration: {
    x: number;
    y: number;
    z: number;
    magnitude: number;
  };
  gyroscope: {
    x: number;
    y: number;
    z: number;
    magnitude: number;
  };
}
