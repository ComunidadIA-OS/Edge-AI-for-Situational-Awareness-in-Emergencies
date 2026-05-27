"use client";

import { useLayerStore } from "@/src/stores/layer-store";
import type { LayerVisibility } from "@/src/types";

type LayerConfig = {
  key: keyof LayerVisibility;
  label: string;
  description: string;
  color: string;
};

const LAYERS: LayerConfig[] = [
  { key: "riskBuffers", label: "Risk buffers", description: "1/3/5 km zones around the perimeter", color: "bg-yellow-500" },
  { key: "predictedPerimeters", label: "24h forecast", description: "Hourly predicted fire progression", color: "bg-orange-400" },
  { key: "currentPerimeter", label: "Current perimeter", description: "Currently burned area + thermal hotspots", color: "bg-red-500" },
  { key: "windVector", label: "Wind", description: "Wind direction and speed (green)", color: "bg-emerald-400" },
  { key: "spreadVector", label: "Spread", description: "Fire-front propagation vector", color: "bg-orange-500" },
  { key: "hotspots", label: "Hotspots", description: "Highest surface-temperature points", color: "bg-red-400" },
  { key: "infrastructure", label: "Infrastructure", description: "Buildings and facilities at risk", color: "bg-amber-500" },
  { key: "drone", label: "Drone", description: "Live drone position and heading", color: "bg-sky-400" },
];

export function LayersPanel() {
  const { toggle } = useLayerStore();
  const layerState = useLayerStore();

  return (
    <div className="space-y-1.5">
      {LAYERS.map((layer) => {
        const enabled = layerState[layer.key];
        return (
          <button
            key={layer.key}
            onClick={() => toggle(layer.key)}
            className="w-full flex items-start gap-3 rounded-lg px-3 py-2.5 bg-zinc-800/60 hover:bg-zinc-700/60 transition text-left"
          >
            <div className="flex items-center gap-2 mt-0.5">
              <div
                className={`w-3 h-3 rounded-full flex-shrink-0 transition ${
                  enabled ? layer.color : "bg-zinc-600"
                }`}
              />
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-xs font-medium ${enabled ? "text-zinc-100" : "text-zinc-500"}`}>
                {layer.label}
              </p>
              <p className="text-xs text-zinc-500 truncate">{layer.description}</p>
            </div>
            <div
              className={`flex-shrink-0 w-8 h-4 rounded-full transition-colors ${
                enabled ? "bg-sky-600" : "bg-zinc-700"
              } relative mt-0.5`}
            >
              <div
                className={`absolute top-0.5 w-3 h-3 rounded-full bg-white shadow transition-transform ${
                  enabled ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
}
