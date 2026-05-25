"use client";

import { ScatterplotLayer, PathLayer, IconLayer } from "@deck.gl/layers";
import { useJetsonTelemetry } from "@/src/api/jetson";
import { useLayerStore } from "@/src/stores/layer-store";
import { useRef } from "react";
import type { DroneTelemetry } from "@/src/types";

const MAX_TRAIL_POINTS = 120;

export function useDroneTrailLayer() {
  const { data } = useJetsonTelemetry();
  const visible = useLayerStore((s) => s.droneTrail);
  const trailRef = useRef<Array<[number, number]>>([]);

  if (!visible || !data) return [];

  const { lon, lat } = data.position;

  // Maintain ring buffer of trail positions
  trailRef.current.push([lon, lat]);
  if (trailRef.current.length > MAX_TRAIL_POINTS) {
    trailRef.current = trailRef.current.slice(-MAX_TRAIL_POINTS);
  }

  const trail = trailRef.current;

  return [
    // Trail path
    new PathLayer({
      id: "drone-trail",
      data: [{ path: trail }],
      getPath: (d) => d.path,
      getColor: [56, 189, 248, 180],
      getWidth: 2,
      widthMinPixels: 1,
      widthMaxPixels: 4,
    }),

    // Drone marker (dot)
    new ScatterplotLayer({
      id: "drone-position",
      data: [data],
      getPosition: (d: DroneTelemetry) => [d.position.lon, d.position.lat],
      getRadius: 8,
      radiusMinPixels: 6,
      radiusMaxPixels: 14,
      getFillColor: [56, 189, 248, 255],
      getLineColor: [255, 255, 255, 200],
      stroked: true,
      lineWidthMinPixels: 2,
    }),
  ];
}
