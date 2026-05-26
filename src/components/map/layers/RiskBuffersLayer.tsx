"use client";

import { useMemo } from "react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { PolygonLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";
import { useUIStore } from "@/src/stores/ui-store";

const FILL_COLORS: Record<number, [number, number, number, number]> = {
  5: [251, 191, 36, 55],
  3: [249, 115, 22, 75],
  1: [239, 68, 68, 95],
};

const LINE_COLORS: Record<number, [number, number, number, number]> = {
  5: [251, 191, 36, 160],
  3: [249, 115, 22, 180],
  1: [239, 68, 68, 220],
};

const EXTRUDE_HEIGHT: Record<number, number> = {
  5: 80,
  3: 180,
  1: 320,
};

export function useRiskBuffersLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.riskBuffers);
  const viewMode = useUIStore((s) => s.viewMode);

  return useMemo(() => {
    if (!visible || !report?.risk_buffers?.length) return [];

    if (viewMode === "3d") {
      return report.risk_buffers.map((buffer) => {
        const coords = buffer.geometry.coordinates;
        return new PolygonLayer({
          id: `risk-buffer-3d-${buffer.distance_km}km`,
          data: [{ contour: coords[0] }],
          getPolygon: (d: { contour: number[][] }) => d.contour,
          filled: true,
          extruded: true,
          getElevation: EXTRUDE_HEIGHT[buffer.distance_km] ?? 100,
          getFillColor: FILL_COLORS[buffer.distance_km] ?? [200, 200, 0, 55],
          getLineColor: LINE_COLORS[buffer.distance_km] ?? [200, 200, 0, 180],
          stroked: true,
          lineWidthMinPixels: 1,
          pickable: false,
          wireframe: false,
        });
      });
    }

    return report.risk_buffers.map(
      (buffer) =>
        new GeoJsonLayer({
          id: `risk-buffer-${buffer.distance_km}km`,
          data: { type: "FeatureCollection", features: [{ type: "Feature", geometry: buffer.geometry, properties: {} }] },
          filled: true,
          stroked: true,
          getFillColor: FILL_COLORS[buffer.distance_km] ?? [200, 200, 0, 55],
          getLineColor: LINE_COLORS[buffer.distance_km] ?? [200, 200, 0, 180],
          getLineWidth: 2,
          lineWidthMinPixels: 1,
          lineWidthUnits: "pixels",
          pickable: false,
        })
    );
  }, [visible, report, viewMode]);
}
