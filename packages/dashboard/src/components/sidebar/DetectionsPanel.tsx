"use client";

import { Flame, AlertTriangle, Wind, HelpCircle } from "lucide-react";
import { useJetsonDetections } from "@/src/api/jetson";
import { useUIStore } from "@/src/stores/ui-store";
import { useMapStore } from "@/src/stores/map-store";
import { Badge } from "@/src/components/ui/Badge";
import { cn, confidenceColor } from "@/src/lib/utils";
import type { FireDetection } from "@/src/types";

const HINT_ICONS = {
  flame: <Flame className="w-3 h-3 text-red-400" />,
  smoke: <Wind className="w-3 h-3 text-zinc-300" />,
  ember: <AlertTriangle className="w-3 h-3 text-amber-400" />,
  unknown: <HelpCircle className="w-3 h-3 text-zinc-400" />,
};

function confidenceBadgeVariant(c: number) {
  if (c >= 0.85) return "error";
  if (c >= 0.7) return "warning";
  return "default";
}

export function DetectionsPanel() {
  const { data, isLoading } = useJetsonDetections();
  const selectedId = useUIStore((s) => s.selectedDetectionId);
  const selectDetection = useUIStore((s) => s.selectDetection);
  const flyTo = useMapStore((s) => s.flyTo);

  const detections = data?.detections ?? [];

  if (isLoading && !data) {
    return <p className="text-xs text-zinc-500 py-4 text-center">Esperando detecciones…</p>;
  }

  if (!detections.length) {
    return (
      <div className="text-center py-6">
        <Flame className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
        <p className="text-xs text-zinc-500">Sin detecciones activas</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-zinc-400">
          {detections.length} detección{detections.length !== 1 ? "es" : ""}
        </p>
        {data?.meta && (
          <p className="text-xs text-zinc-500">{data.meta.inference_time_ms.toFixed(0)} ms/frame</p>
        )}
      </div>

      <div className="space-y-2">
        {detections.map((d: FireDetection) => (
          <button
            key={d.id}
            onClick={() => {
              selectDetection(d.id);
              flyTo(d.centroid.lat, d.centroid.lon, 17);
            }}
            className={cn(
              "w-full text-left rounded-lg px-3 py-2.5 transition",
              "border",
              selectedId === d.id
                ? "bg-zinc-700/80 border-zinc-500"
                : "bg-zinc-800/60 border-transparent hover:bg-zinc-700/50"
            )}
          >
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-1.5">
                {HINT_ICONS[d.classification_hint]}
                <span className="text-xs text-zinc-200 capitalize">{d.classification_hint}</span>
              </div>
              <Badge variant={confidenceBadgeVariant(d.confidence)}>
                {(d.confidence * 100).toFixed(0)}%
              </Badge>
            </div>
            <div className="flex items-center gap-3 text-xs text-zinc-400">
              <span>{d.size_estimate_m2.toFixed(0)} m²</span>
              <span>T: {(d.thermal_intensity * 100).toFixed(0)}%</span>
              {d.track_id && (
                <span className="font-mono text-violet-400 truncate">{d.track_id}</span>
              )}
            </div>

            {/* Confidence bar */}
            <div className="mt-2 h-1 rounded-full bg-zinc-700">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${d.confidence * 100}%`,
                  backgroundColor: `rgba(${confidenceColor(d.confidence).slice(0, 3).join(",")},0.9)`,
                }}
              />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
