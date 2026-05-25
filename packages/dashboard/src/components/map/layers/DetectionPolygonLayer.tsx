"use client";

import { GeoJsonLayer } from "@deck.gl/layers";
import { useJetsonDetections } from "@/src/api/jetson";
import { useLayerStore } from "@/src/stores/layer-store";
import { useUIStore } from "@/src/stores/ui-store";
import { confidenceColor } from "@/src/lib/utils";
import type { FireDetection } from "@/src/types";

export function useDetectionLayers() {
  const { data } = useJetsonDetections();
  const visible = useLayerStore((s) => s.detections);
  const selectedId = useUIStore((s) => s.selectedDetectionId);
  const selectDetection = useUIStore((s) => s.selectDetection);

  if (!visible || !data?.detections.length) return [];

  const geojson = {
    type: "FeatureCollection" as const,
    features: data.detections.map((d: FireDetection) => ({
      type: "Feature" as const,
      geometry: d.geometry,
      properties: {
        id: d.id,
        confidence: d.confidence,
        thermal_intensity: d.thermal_intensity,
        classification_hint: d.classification_hint,
        size_estimate_m2: d.size_estimate_m2,
        detected_at: d.detected_at,
        selected: d.id === selectedId,
      },
    })),
  };

  return [
    new GeoJsonLayer({
      id: "detection-fills",
      data: geojson,
      stroked: true,
      filled: true,
      getFillColor: (f) => {
        const c = f.properties?.confidence ?? 0;
        const [r, g, b] = confidenceColor(c);
        return [r, g, b, f.properties?.selected ? 220 : 140];
      },
      getLineColor: (f) => {
        const c = f.properties?.confidence ?? 0;
        const [r, g, b] = confidenceColor(c);
        return [r, g, b, 255];
      },
      lineWidthMinPixels: 1,
      lineWidthMaxPixels: 3,
      getLineWidth: 2,
      pickable: true,
      autoHighlight: true,
      highlightColor: [255, 255, 255, 60],
      onClick: (info) => {
        if (info.object?.properties?.id) {
          selectDetection(info.object.properties.id);
        }
      },
      updateTriggers: {
        getFillColor: [selectedId, data.timestamp],
        getLineColor: [data.timestamp],
      },
    }),
  ];
}
