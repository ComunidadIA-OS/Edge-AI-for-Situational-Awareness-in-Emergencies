"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

type SettingsStore = {
  pollingIntervalMs: number;
  setPollingInterval: (ms: number) => void;
};

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      pollingIntervalMs: 2000,
      setPollingInterval: (pollingIntervalMs) => set({ pollingIntervalMs }),
    }),
    { name: "heimdall-settings" }
  )
);
