// ============================================================
// RideShield — Socket.IO Service
// ============================================================
// Handles real-time bidirectional communication with backend.
// Frontend DOES NOT detect crashes — it only listens for CRASH_DETECTED.

import { io, Socket } from 'socket.io-client';
import { Config } from '../constants/config';
import type { TelemetryPayload } from '../types/telemetry';
import type { CrashEvent } from '../types/claim';

// Socket events
export const SocketEvents = {
  // Outgoing (client → server)
  JOIN_SHIFT: 'join_shift',
  LEAVE_SHIFT: 'leave_shift',
  TELEMETRY: 'telemetry',
  RIDER_OKAY: 'rider_okay',
  RIDER_NEEDS_HELP: 'rider_needs_help',
  SOS_TRIGGERED: 'sos_triggered',

  // Incoming (server → client)
  CRASH_DETECTED: 'crash_detected',
  SHIFT_ENDED: 'shift_ended',
  ERROR: 'error',
} as const;

type CrashDetectedCallback = (event: CrashEvent) => void;
type ConnectCallback = () => void;
type DisconnectCallback = (reason: string) => void;

class SocketService {
  private socket: Socket | null = null;
  private isConnected = false;
  private crashCallbacks: Set<CrashDetectedCallback> = new Set();
  private connectCallbacks: Set<ConnectCallback> = new Set();
  private disconnectCallbacks: Set<DisconnectCallback> = new Set();

  connect(): void {
    if (this.isConnected || this.socket?.connected) return;

    if (true) {
      this.isConnected = true;
      this.connectCallbacks.forEach(cb => cb());
      return;
    }

    try {
      const socket = io(Config.SOCKET_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 3,
        reconnectionDelay: 3000,
        timeout: 5000,
        autoConnect: true,
      });
      
      this.socket = socket;

      socket.on('connect', () => {
        this.isConnected = true;
        this.connectCallbacks.forEach(cb => cb());
      });

      socket.on('disconnect', (reason) => {
        this.isConnected = false;
        this.disconnectCallbacks.forEach(cb => cb(reason));
      });

      socket.on('connect_error', () => {
        this.isConnected = false;
        // Suppress unhandled websocket error log when backend is offline
      });

      socket.on(SocketEvents.CRASH_DETECTED, (event: CrashEvent) => {
        this.crashCallbacks.forEach(cb => cb(event));
      });
    } catch {
      this.isConnected = false;
    }
  }

  disconnect(): void {
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
    this.isConnected = false;
    this.disconnectCallbacks.forEach(cb => cb('manual_disconnect'));
  }

  joinShift(shiftId: string): void {
    this.socket?.emit(SocketEvents.JOIN_SHIFT, { shiftId });
  }

  leaveShift(shiftId: string): void {
    this.socket?.emit(SocketEvents.LEAVE_SHIFT, { shiftId });
  }

  emitTelemetry(payload: TelemetryPayload): void {
    if (!this.socket?.connected) return;
    this.socket.emit(SocketEvents.TELEMETRY, payload);
  }

  emitRiderOkay(shiftId: string): void {
    this.socket?.emit(SocketEvents.RIDER_OKAY, { shiftId });
  }

  emitRiderNeedsHelp(shiftId: string, crashEvent: CrashEvent): void {
    this.socket?.emit(SocketEvents.RIDER_NEEDS_HELP, { shiftId, crashEvent });
  }

  emitSOS(shiftId: string, latitude: number, longitude: number): void {
    this.socket?.emit(SocketEvents.SOS_TRIGGERED, {
      shiftId,
      latitude,
      longitude,
      timestamp: Date.now(),
    });
  }

  // Helper for dev mock crash triggers
  triggerMockCrash(crashEvent: CrashEvent): void {
    this.crashCallbacks.forEach(cb => cb(crashEvent));
  }

  onCrashDetected(callback: CrashDetectedCallback): () => void {
    this.crashCallbacks.add(callback);
    if (this.socket) {
      this.socket.on(SocketEvents.CRASH_DETECTED, callback);
    }
    return () => {
      this.crashCallbacks.delete(callback);
      this.socket?.off(SocketEvents.CRASH_DETECTED, callback);
    };
  }

  onConnect(callback: ConnectCallback): () => void {
    this.connectCallbacks.add(callback);
    if (this.socket) {
      this.socket.on('connect', callback);
    }
    return () => {
      this.connectCallbacks.delete(callback);
      this.socket?.off('connect', callback);
    };
  }

  onDisconnect(callback: DisconnectCallback): () => void {
    this.disconnectCallbacks.add(callback);
    if (this.socket) {
      this.socket.on('disconnect', callback);
    }
    return () => {
      this.disconnectCallbacks.delete(callback);
      this.socket?.off('disconnect', callback);
    };
  }

  getIsConnected(): boolean {
    return this.isConnected || (this.socket?.connected ?? false);
  }
}

// Singleton instance
export const socketService = new SocketService();
