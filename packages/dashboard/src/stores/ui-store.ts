"use client";

import { create } from "zustand";
import type { SidebarTab, ViewMode } from "@/src/types";

export const SIDEBAR_MIN_W = 200;
export const SIDEBAR_MAX_W = 520;
export const SIDEBAR_DEFAULT_W = 272; // ~lg:w-72

const clamp = (n: number, min: number, max: number) => Math.min(Math.max(n, min), max);

type UIStore = {
  sidebarOpen: boolean;
  sidebarWidth: number;
  activeTab: SidebarTab;
  viewMode: ViewMode;
  cinemaMode: boolean;
  legendVisible: boolean;
  mapControlsOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  setSidebarWidth: (w: number) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: SidebarTab) => void;
  setViewMode: (mode: ViewMode) => void;
  toggleCinemaMode: () => void;
  toggleLegend: () => void;
  toggleMapControls: () => void;
};

export const useUIStore = create<UIStore>()((set) => ({
  sidebarOpen: true,
  sidebarWidth: SIDEBAR_DEFAULT_W,
  activeTab: "status",
  viewMode: "2d",
  cinemaMode: false,
  legendVisible: true,
  mapControlsOpen: true,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  setSidebarWidth: (w) => set({ sidebarWidth: clamp(w, SIDEBAR_MIN_W, SIDEBAR_MAX_W) }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setActiveTab: (activeTab) => set({ activeTab }),
  setViewMode: (viewMode) => set({ viewMode }),
  toggleCinemaMode: () =>
    set((state) => ({
      cinemaMode: !state.cinemaMode,
      sidebarOpen: state.cinemaMode ? true : false,
    })),
  toggleLegend: () => set((state) => ({ legendVisible: !state.legendVisible })),
  toggleMapControls: () => set((state) => ({ mapControlsOpen: !state.mapControlsOpen })),
}));
