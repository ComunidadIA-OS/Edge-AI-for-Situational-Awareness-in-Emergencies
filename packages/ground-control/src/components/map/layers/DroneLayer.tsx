"use client";

import { useMemo } from "react";
import { IconLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";

const DRONE_ICON = `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg width="40" height="40" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
    <circle cx="20" cy="20" r="4" fill="#38bdf8" stroke="white" stroke-width="1.5"/>
    <line x1="20" y1="16" x2="20" y2="4" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <line x1="20" y1="24" x2="20" y2="36" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <line x1="16" y1="20" x2="4" y2="20" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <line x1="24" y1="20" x2="36" y2="20" stroke="white" stroke-width="2" stroke-linecap="round"/>
    <circle cx="20" cy="4" r="4" fill="#38bdf8" stroke="white" stroke-width="1"/>
    <circle cx="20" cy="36" r="4" fill="#38bdf8" stroke="white" stroke-width="1"/>
    <circle cx="4" cy="20" r="4" fill="#38bdf8" stroke="white" stroke-width="1"/>
    <circle cx="36" cy="20" r="4" fill="#38bdf8" stroke="white" stroke-width="1"/>
  </svg>`
)}`;

export function useDroneLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.drone);

  return useMemo(() => {
    const tel = report?.drone_telemetry;
    if (!visible || !tel) return [];

    return [
      new IconLayer({
        id: "drone",
        data: [tel],
        getIcon: () => ({ url: DRONE_ICON, width: 40, height: 40, anchorX: 20, anchorY: 20 }),
        getPosition: (d) => [d.lon, d.lat],
        getSize: 40,
        getAngle: (d) => -d.heading_deg,
        sizeScale: 1,
        sizeMinPixels: 24,
        sizeMaxPixels: 60,
        pickable: true,
      }),
    ];
  }, [visible, report]);
}
