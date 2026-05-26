"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { LayerVisibility } from "@/src/types";

type LayerStore = LayerVisibility & {
  toggle: (layer: keyof LayerVisibility) => void;
  setAll: (visible: boolean) => void;
};

const DEFAULTS: LayerVisibility = {
  riskBuffers: true,
  predictedPerimeters: true,
  currentPerimeter: true,
  windVector: true,
  spreadVector: true,
  hotspots: true,
  infrastructure: true,
  drone: true,
};

export const useLayerStore = create<LayerStore>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      toggle: (layer) => set((state) => ({ [layer]: !state[layer] })),
      setAll: (visible) => set(Object.fromEntries(Object.keys(DEFAULTS).map((k) => [k, visible]))),
    }),
    { name: "heimdall-layers" }
  )
);
