"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LayerVisibility } from "@/src/types";

type LayerStore = LayerVisibility & {
  toggle: (layer: keyof LayerVisibility) => void;
  setAll: (visible: boolean) => void;
};

export const useLayerStore = create<LayerStore>()(
  persist(
    (set) => ({
      detections: true,
      droneTrail: true,
      fovCone: true,
      firms: false,
      wind: false,
      missionArea: true,
      flightPlan: true,
      toggle: (layer) => set((state) => ({ [layer]: !state[layer] })),
      setAll: (visible) =>
        set({
          detections: visible,
          droneTrail: visible,
          fovCone: visible,
          firms: visible,
          wind: visible,
          missionArea: visible,
          flightPlan: visible,
        }),
    }),
    { name: "heimdall-layers" }
  )
);
