"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMapStore } from "@/src/stores/map-store";
import { BASEMAPS } from "@/src/types/map";
import { DeckGLOverlay } from "./DeckGLOverlay";

export function MapLibreMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const { viewState, mapStyle, setViewState } = useMapStore();

  const currentStyle = BASEMAPS.find((b) => b.id === mapStyle)?.styleUrl ?? BASEMAPS[0].styleUrl;

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: currentStyle,
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      pitch: viewState.pitch,
      bearing: viewState.bearing,
      canvasContextAttributes: { antialias: true },
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    map.on("move", () => {
      const center = map.getCenter();
      setViewState({
        longitude: center.lng,
        latitude: center.lat,
        zoom: map.getZoom(),
        pitch: map.getPitch(),
        bearing: map.getBearing(),
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Swap basemap style
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setStyle(currentStyle);
  }, [currentStyle]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full" />
      {mapRef.current && <DeckGLOverlay map={mapRef.current} />}
    </div>
  );
}
