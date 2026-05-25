"use client";

import { useEffect, useRef } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import type maplibregl from "maplibre-gl";
import { useDetectionLayers } from "./layers/DetectionPolygonLayer";
import { useDroneTrailLayer } from "./layers/DroneTrailLayer";
import { useMissionAreaLayer } from "./layers/MissionAreaLayer";
import { useFIRMSLayer } from "./layers/FIRMSHotspotLayer";

type Props = {
  map: maplibregl.Map;
};

export function DeckGLOverlay({ map }: Props) {
  const overlayRef = useRef<InstanceType<typeof MapboxOverlay> | null>(null);

  const detectionLayers = useDetectionLayers();
  const droneLayer = useDroneTrailLayer();
  const missionLayer = useMissionAreaLayer();
  const firmsLayer = useFIRMSLayer();

  // Mount overlay once when map is ready
  useEffect(() => {
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    // MapboxOverlay implements IControl and works with maplibre-gl via the mapbox-gl alias
    (map as unknown as { addControl: (ctrl: unknown) => void }).addControl(overlay);
    overlayRef.current = overlay;

    return () => {
      (map as unknown as { removeControl: (ctrl: unknown) => void }).removeControl(overlay);
      overlayRef.current = null;
    };
  }, [map]);

  // Push updated layers on each render
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    overlay.setProps({
      layers: [...detectionLayers, ...droneLayer, ...missionLayer, ...firmsLayer],
    });
  }, [detectionLayers, droneLayer, missionLayer, firmsLayer]);

  return null;
}
