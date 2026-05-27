"use client";

import { useMemo } from "react";
import { IconLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";

function arrowSvg(color: string): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg width="36" height="54" xmlns="http://www.w3.org/2000/svg"><polygon points="18,0 36,27 23,27 23,54 13,54 13,27 0,27" fill="${color}" stroke="white" stroke-width="1.5"/></svg>`
  )}`;
}

const SPREAD_ICON = arrowSvg("#f97316");

export function useSpreadVectorLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.spreadVector);

  return useMemo(() => {
    if (!visible || !report) return [];

    const { spread_direction_deg, spread_rate_mh } = report.prediction;
    const [lon, lat] = report.fire_perimeter.centroid;
    const size = Math.min(90, 36 + (spread_rate_mh / 600) * 54);

    return [
      new IconLayer({
        id: "spread-vector",
        data: [{ position: [lon, lat] }],
        getIcon: () => ({ url: SPREAD_ICON, width: 36, height: 54, anchorY: 27 }),
        getPosition: (d) => d.position,
        getSize: size,
        getAngle: () => -spread_direction_deg,
        sizeScale: 1,
        sizeMinPixels: 28,
        sizeMaxPixels: 90,
        pickable: false,
      }),
    ];
  }, [visible, report]);
}
