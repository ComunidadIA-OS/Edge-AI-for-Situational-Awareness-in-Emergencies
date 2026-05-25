"use client";

import { create } from "zustand";
import type { SidebarTab, ViewMode } from "@/src/types";

type UIStore = {
  sidebarOpen: boolean;
  activeTab: SidebarTab;
  viewMode: ViewMode;
  selectedDetectionId: string | null;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: SidebarTab) => void;
  setViewMode: (mode: ViewMode) => void;
  selectDetection: (id: string | null) => void;
};

export const useUIStore = create<UIStore>()((set) => ({
  sidebarOpen: true,
  activeTab: "status",
  viewMode: "2d",
  selectedDetectionId: null,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setActiveTab: (activeTab) => set({ activeTab }),
  setViewMode: (viewMode) => set({ viewMode }),
  selectDetection: (selectedDetectionId) => set({ selectedDetectionId }),
}));
