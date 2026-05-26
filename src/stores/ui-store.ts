"use client";

import { create } from "zustand";
import type { SidebarTab, ViewMode } from "@/src/types";

type UIStore = {
  sidebarOpen: boolean;
  activeTab: SidebarTab;
  viewMode: ViewMode;
  cinemaMode: boolean;
  legendVisible: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: SidebarTab) => void;
  setViewMode: (mode: ViewMode) => void;
  toggleCinemaMode: () => void;
  toggleLegend: () => void;
};

export const useUIStore = create<UIStore>()((set) => ({
  sidebarOpen: true,
  activeTab: "status",
  viewMode: "2d",
  cinemaMode: false,
  legendVisible: true,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setActiveTab: (activeTab) => set({ activeTab }),
  setViewMode: (viewMode) => set({ viewMode }),
  toggleCinemaMode: () =>
    set((state) => ({
      cinemaMode: !state.cinemaMode,
      sidebarOpen: state.cinemaMode ? true : false,
    })),
  toggleLegend: () => set((state) => ({ legendVisible: !state.legendVisible })),
}));
