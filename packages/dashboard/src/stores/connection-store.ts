"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ConnectionState } from "@/src/types";

type ConnectionStore = {
  droneUrl: string;
  connectionState: ConnectionState;
  lastSeenAt: number | null;
  latencyMs: number | null;
  lastError: string | null;
  setDroneUrl: (url: string) => void;
  setConnectionState: (state: ConnectionState) => void;
  setLastSeen: (ts: number) => void;
  setLatency: (ms: number) => void;
  setLastError: (error: string | null) => void;
  reset: () => void;
};

export const useConnectionStore = create<ConnectionStore>()(
  persist(
    (set) => ({
      droneUrl: "",
      connectionState: "unconfigured",
      lastSeenAt: null,
      latencyMs: null,
      lastError: null,
      setDroneUrl: (url) => set({ droneUrl: url, connectionState: "connecting", lastError: null }),
      setConnectionState: (state) => set({ connectionState: state }),
      setLastSeen: (ts) => set({ lastSeenAt: ts }),
      setLatency: (ms) => set({ latencyMs: ms }),
      setLastError: (error) => set({ lastError: error }),
      reset: () =>
        set({
          droneUrl: "",
          connectionState: "unconfigured",
          lastSeenAt: null,
          latencyMs: null,
          lastError: null,
        }),
    }),
    {
      name: "heimdall-connection",
      partialize: (state) => ({ droneUrl: state.droneUrl }),
    }
  )
);
