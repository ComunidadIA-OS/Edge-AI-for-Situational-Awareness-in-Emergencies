"use client";

import { useMemo } from "react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";
import { useMapStore } from "@/src/stores/map-store";

const MAX_HOURLY = 24;

export function usePredictedPerimeterLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.predictedPerimeters);
  const playbackHour = useMapStore((s) => s.playbackHour);

  return useMemo(() => {
    if (!visible || !report?.prediction?.hourly?.length) return [];

    const hourly = report.prediction.hourly.slice(0, MAX_HOURLY);

    if (playbackHour !== null) {
      const h = hourly.find((x) => x.hour_offset === playbackHour);
      if (!h) return [];
      return [
        new GeoJsonLayer({
          id: `predicted-perimeter-playback`,
          data: {
            type: "FeatureCollection",
            features: [{ type: "Feature", geometry: h.predicted_perimeter, properties: {} }],
          },
          filled: true,
          getFillColor: [251, 146, 60, 40],
          stroked: true,
          getLineColor: [251, 146, 60, 220],
          getLineWidth: 3,
          lineWidthMinPixels: 2,
          lineWidthUnits: "pixels",
          pickable: false,
        }),
      ];
    }

    return hourly.map((h) => {
      const opacity = Math.max(20, 110 - h.hour_offset * 3);
      return new GeoJsonLayer({
        id: `predicted-perimeter-h${h.hour_offset}`,
        data: {
          type: "FeatureCollection",
          features: [{ type: "Feature", geometry: h.predicted_perimeter, properties: {} }],
        },
        filled: false,
        stroked: true,
        getLineColor: [251, 146, 60, opacity],
        getLineWidth: h.hour_offset <= 6 ? 2 : 1,
        lineWidthMinPixels: 1,
        lineWidthUnits: "pixels",
        getDashArray: [4, 4],
        dashJustified: true,
        extensions: [],
        pickable: false,
      });
    });
  }, [visible, report, playbackHour]);
}
