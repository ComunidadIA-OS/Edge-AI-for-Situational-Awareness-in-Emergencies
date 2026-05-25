"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

type SettingsStore = {
  pollingIntervalMs: number;
  firmsPollingMs: number;
  weatherPollingMs: number;
  useMockData: boolean;
  setPollingInterval: (ms: number) => void;
  setFirmsPolling: (ms: number) => void;
  setWeatherPolling: (ms: number) => void;
  setUseMockData: (use: boolean) => void;
};

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      pollingIntervalMs: 2000,
      firmsPollingMs: 300_000,
      weatherPollingMs: 600_000,
      useMockData: true,
      setPollingInterval: (pollingIntervalMs) => set({ pollingIntervalMs }),
      setFirmsPolling: (firmsPollingMs) => set({ firmsPollingMs }),
      setWeatherPolling: (weatherPollingMs) => set({ weatherPollingMs }),
      setUseMockData: (useMockData) => set({ useMockData }),
    }),
    { name: "heimdall-settings" }
  )
);
