"use client";

import { ScatterplotLayer } from "@deck.gl/layers";
import { useFIRMSData } from "@/src/api/firms";
import { useLayerStore } from "@/src/stores/layer-store";
import { useMapStore } from "@/src/stores/map-store";
import type { BBox } from "@/src/types";

function viewStateToBbox(
  lon: number,
  lat: number,
  zoom: number
): BBox {
  const degPerPx = 360 / (256 * Math.pow(2, zoom));
  const w = degPerPx * 800; // ~1280px viewport half-width
  const h = degPerPx * 400;
  return [lon - w, lat - h, lon + w, lat + h];
}

export function useFIRMSLayer() {
  const visible = useLayerStore((s) => s.firms);
  const { longitude, latitude, zoom } = useMapStore((s) => s.viewState);
  const bbox = viewStateToBbox(longitude, latitude, zoom);
  const { data } = useFIRMSData(bbox);

  if (!visible || !data?.length) return [];

  return [
    new ScatterplotLayer({
      id: "firms-hotspots",
      data,
      getPosition: (d) => [d.longitude, d.latitude],
      getRadius: (d) => Math.max(8, Math.sqrt(d.frp) * 3),
      radiusMinPixels: 4,
      radiusMaxPixels: 20,
      getFillColor: [255, 100, 20, 200],
      getLineColor: [255, 200, 80, 255],
      stroked: true,
      lineWidthMinPixels: 1,
      pickable: true,
    }),
  ];
}
