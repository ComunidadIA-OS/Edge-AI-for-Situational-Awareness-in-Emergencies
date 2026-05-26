"use client";

import { useMemo } from "react";
import { ScatterplotLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";
import type { Hotspot } from "@/src/types/meteo-report";

function tempToColor(tempC: number): [number, number, number, number] {
  const t = Math.min(1, Math.max(0, (tempC - 200) / 700));
  return [255, Math.round(200 * (1 - t)), 0, 230];
}

export function useHotspotsLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.hotspots);

  return useMemo(() => {
    if (!visible || !report?.fire_perimeter?.hotspots?.length) return [];

    return [
      new ScatterplotLayer<Hotspot>({
        id: "hotspots",
        data: report.fire_perimeter.hotspots,
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: (d) => tempToColor(d.temperature_c),
        getRadius: (d) => 60 + d.confidence * 100,
        radiusUnits: "meters",
        radiusMinPixels: 5,
        stroked: true,
        getLineColor: [255, 255, 255, 180],
        getLineWidth: 1,
        lineWidthMinPixels: 1,
        pickable: true,
      }),
    ];
  }, [visible, report]);
}
