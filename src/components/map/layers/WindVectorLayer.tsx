"use client";

import { useMemo } from "react";
import { IconLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";

function arrowSvg(color: string): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg width="32" height="48" xmlns="http://www.w3.org/2000/svg"><polygon points="16,0 32,24 20,24 20,48 12,48 12,24 0,24" fill="${color}" stroke="white" stroke-width="1"/></svg>`
  )}`;
}

const WIND_ICON = arrowSvg("#6ee7b7");

export function useWindVectorLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.windVector);

  return useMemo(() => {
    if (!visible || !report) return [];

    const { wind_direction_deg, wind_speed_kmh } = report.current_weather;
    const [lon, lat] = report.metadata.location;
    const size = Math.min(80, 28 + (wind_speed_kmh / 80) * 52);

    return [
      new IconLayer({
        id: "wind-vector",
        data: [{ position: [lon, lat] }],
        getIcon: () => ({ url: WIND_ICON, width: 32, height: 48, anchorY: 24 }),
        getPosition: (d) => d.position,
        getSize: size,
        getAngle: () => -wind_direction_deg,
        sizeScale: 1,
        sizeMinPixels: 24,
        sizeMaxPixels: 80,
        pickable: false,
      }),
    ];
  }, [visible, report]);
}
