"use client";

import { create } from "zustand";
import type { ViewState, MapStyle } from "@/src/types";

type MapStore = {
  viewState: ViewState;
  mapStyle: MapStyle;
  playbackHour: number | null;
  setViewState: (vs: Partial<ViewState>) => void;
  setMapStyle: (style: MapStyle) => void;
  setPlaybackHour: (hour: number | null) => void;
  flyTo: (lat: number, lon: number, zoom?: number) => void;
};

export const useMapStore = create<MapStore>()((set) => ({
  viewState: {
    longitude: -3.7025,
    latitude: 40.4168,
    zoom: 13,
    pitch: 45,
    bearing: 0,
  },
  mapStyle: "osm",
  playbackHour: null,
  setViewState: (vs) =>
    set((state) => ({ viewState: { ...state.viewState, ...vs } })),
  setMapStyle: (mapStyle) => set({ mapStyle }),
  setPlaybackHour: (playbackHour) => set({ playbackHour }),
  flyTo: (lat, lon, zoom = 15) =>
    set((state) => ({
      viewState: { ...state.viewState, latitude: lat, longitude: lon, zoom },
    })),
}));
