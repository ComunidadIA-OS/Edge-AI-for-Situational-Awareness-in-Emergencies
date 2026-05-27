"use client";

import { useMemo } from "react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";

// Rings only — no fill so the basemap stays readable inside the hazard zones.
// Solid innermost ring (critical) and progressively lighter outward.
const LINE_COLORS: Record<number, [number, number, number, number]> = {
  1: [239, 68, 68, 240],   // red    — 1 km critical
  3: [249, 115, 22, 200],  // orange — 3 km alert
  5: [251, 191, 36, 160],  // yellow — 5 km watch
};

const LINE_WIDTHS_PX: Record<number, number> = {
  1: 3,
  3: 2,
  5: 1.5,
};

export function useRiskBuffersLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.riskBuffers);

  return useMemo(() => {
    if (!visible || !report?.risk_buffers?.length) return [];

    return report.risk_buffers.map(
      (buffer) =>
        new GeoJsonLayer({
          id: `risk-buffer-${buffer.distance_km}km`,
          data: {
            type: "FeatureCollection",
            features: [{ type: "Feature", geometry: buffer.geometry, properties: {} }],
          },
          filled: false,
          stroked: true,
          getLineColor: LINE_COLORS[buffer.distance_km] ?? [200, 200, 0, 180],
          getLineWidth: LINE_WIDTHS_PX[buffer.distance_km] ?? 2,
          lineWidthMinPixels: LINE_WIDTHS_PX[buffer.distance_km] ?? 2,
          lineWidthUnits: "pixels",
          pickable: false,
        })
    );
  }, [visible, report]);
}
