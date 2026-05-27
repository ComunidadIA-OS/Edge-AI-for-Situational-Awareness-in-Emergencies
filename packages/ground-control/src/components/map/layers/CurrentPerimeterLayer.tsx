"use client";

import { useMemo } from "react";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";

function tempToColor(tempC: number): [number, number, number, number] {
  const t = Math.min(1, Math.max(0, (tempC - 200) / 700));
  return [255, Math.round(255 * (1 - t)), 0, 220];
}

export function useCurrentPerimeterLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.currentPerimeter);

  return useMemo(() => {
    if (!visible || !report?.fire_perimeter) return [];

    const { polygon, hotspots } = report.fire_perimeter;

    const perimeterLayer = new GeoJsonLayer({
      id: "current-perimeter-fill",
      data: { type: "FeatureCollection", features: [{ type: "Feature", geometry: polygon, properties: {} }] },
      filled: true,
      stroked: true,
      getFillColor: [239, 68, 68, 55],
      getLineColor: [239, 68, 68, 255],
      getLineWidth: 3,
      lineWidthMinPixels: 2,
      lineWidthUnits: "pixels",
      pickable: false,
    });

    const hotspotsLayer = new ScatterplotLayer({
      id: "current-perimeter-hotspots",
      data: hotspots,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: (d) => tempToColor(d.temperature_c),
      getRadius: (d) => 80 + d.confidence * 120,
      radiusUnits: "meters",
      radiusMinPixels: 4,
      pickable: true,
    });

    return [perimeterLayer, hotspotsLayer];
  }, [visible, report]);
}
