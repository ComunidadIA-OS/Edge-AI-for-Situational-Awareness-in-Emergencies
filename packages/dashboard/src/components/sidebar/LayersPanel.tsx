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
  { key: "detections", label: "Detecciones", description: "Polígonos de fuego/humo del modelo YOLOv9", color: "bg-red-500" },
  { key: "droneTrail", label: "Trayectoria", description: "Ruta del dron + posición actual", color: "bg-sky-400" },
  { key: "fovCone", label: "FOV Cámara", description: "Campo de visión de la cámara", color: "bg-yellow-400" },
  { key: "missionArea", label: "Área misión", description: "Perímetro del área de interés", color: "bg-indigo-500" },
  { key: "flightPlan", label: "Plan de vuelo", description: "Waypoints del plan lawnmower", color: "bg-violet-500" },
  { key: "firms", label: "NASA FIRMS", description: "Focos activos de satélite (VIIRS)", color: "bg-orange-500" },
  { key: "wind", label: "Viento", description: "Partículas de viento animadas", color: "bg-zinc-300" },
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
            {/* Color dot + toggle state */}
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
            {/* Toggle pill */}
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
