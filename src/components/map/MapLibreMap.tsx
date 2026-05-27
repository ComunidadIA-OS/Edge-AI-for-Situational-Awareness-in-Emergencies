"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useMapStore } from "@/src/stores/map-store";
import { useUIStore } from "@/src/stores/ui-store";
import { BASEMAPS } from "@/src/types/map";
import { DeckGLOverlay } from "./DeckGLOverlay";

const TERRAIN_SOURCE_ID = "terrarium-dem";
const TERRAIN_TILES = ["https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"];
const TERRAIN_EXAGGERATION = 1.3;

function ensureTerrainSource(map: maplibregl.Map) {
  if (map.getSource(TERRAIN_SOURCE_ID)) return;
  map.addSource(TERRAIN_SOURCE_ID, {
    type: "raster-dem",
    tiles: TERRAIN_TILES,
    tileSize: 256,
    encoding: "terrarium",
    maxzoom: 15,
    attribution:
      'Elevation: <a href="https://registry.opendata.aws/terrain-tiles/">AWS Open Terrain Tiles</a>',
  });
}

function applyTerrain(map: maplibregl.Map, enabled: boolean) {
  // setTerrain/addSource throw "Style is not done loading" if called before the
  // style is ready (e.g. on first mount, before the basemap tiles resolve, or
  // right after a basemap swap). Defer until the style finishes loading.
  if (!map.isStyleLoaded()) {
    map.once("style.load", () => applyTerrain(map, enabled));
    return;
  }
  if (!enabled) {
    map.setTerrain(null);
    return;
  }
  ensureTerrainSource(map);
  map.setTerrain({ source: TERRAIN_SOURCE_ID, exaggeration: TERRAIN_EXAGGERATION });
}

export function MapLibreMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const { viewState, mapStyle, setViewState } = useMapStore();
  const viewMode = useUIStore((s) => s.viewMode);
  const viewModeRef = useRef(viewMode);
  viewModeRef.current = viewMode;

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
      maxPitch: 75,
      canvasContextAttributes: { antialias: true },
    });

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
      "top-right",
    );
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    // Re-apply terrain after every style load (initial mount + basemap swaps wipe sources).
    map.on("style.load", () => {
      applyTerrain(map, viewModeRef.current === "3d");
    });

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

  // Sync 2D/3D: toggle terrain + tilt camera together
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    applyTerrain(map, viewMode === "3d");
    map.easeTo({ pitch: viewMode === "3d" ? 60 : 0, duration: 600 });
  }, [viewMode]);

  return (
    <div className="relative w-full h-full">
      <div ref={mapContainer} className="w-full h-full" />
      {mapRef.current && <DeckGLOverlay map={mapRef.current} />}
    </div>
  );
}
