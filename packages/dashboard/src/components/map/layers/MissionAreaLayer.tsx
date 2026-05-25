"use client";

import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { useMissionInfo } from "@/src/api/jetson";
import { useLayerStore } from "@/src/stores/layer-store";

export function useMissionAreaLayer() {
  const { data } = useMissionInfo();
  const showArea = useLayerStore((s) => s.missionArea);
  const showPlan = useLayerStore((s) => s.flightPlan);

  const layers = [];

  if (showArea && data?.area_of_interest) {
    layers.push(
      new GeoJsonLayer({
        id: "mission-area",
        data: {
          type: "FeatureCollection",
          features: [
            {
              type: "Feature",
              geometry: data.area_of_interest,
              properties: {},
            },
          ],
        },
        stroked: true,
        filled: true,
        getFillColor: [99, 102, 241, 20],
        getLineColor: [99, 102, 241, 160],
        getLineWidth: 2,
        lineWidthMinPixels: 1,
        lineDashArray: [6, 4],
      })
    );
  }

  if (showPlan && data?.flight_plan?.waypoints.length) {
    layers.push(
      new ScatterplotLayer({
        id: "flight-waypoints",
        data: data.flight_plan.waypoints,
        getPosition: (d) => [d.lon, d.lat],
        getRadius: 4,
        radiusMinPixels: 3,
        radiusMaxPixels: 8,
        getFillColor: [139, 92, 246, 180],
        getLineColor: [139, 92, 246, 255],
        stroked: true,
        lineWidthMinPixels: 1,
      })
    );
  }

  return layers;
}
