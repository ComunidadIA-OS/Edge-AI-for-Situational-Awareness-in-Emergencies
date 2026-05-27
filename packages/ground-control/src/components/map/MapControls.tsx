"use client";

import { useState, useRef, useEffect } from "react";
import { Layers, Box, BookOpen, ChevronRight } from "lucide-react";
import { useMapStore } from "@/src/stores/map-store";
import { useUIStore } from "@/src/stores/ui-store";
import { BASEMAPS } from "@/src/types/map";
import { cn } from "@/src/lib/utils";

export function MapControls() {
  const { mapStyle, setMapStyle } = useMapStore();
  const { viewMode, setViewMode, legendVisible, toggleLegend, mapControlsOpen, toggleMapControls } = useUIStore();
  const [basemapOpen, setBasemapOpen] = useState(false);
  const basemapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!basemapOpen) return;
    const handler = (e: MouseEvent) => {
      if (basemapRef.current && !basemapRef.current.contains(e.target as Node)) {
        setBasemapOpen(false);
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [basemapOpen]);

  return (
    <div className="absolute bottom-8 right-4 z-10 flex flex-col gap-2 items-end">
      {/* Collapse toggle — always visible, collapses/expands the controls below */}
      <button
        onClick={toggleMapControls}
        className={cn(
          "flex items-center justify-center w-[44px] h-[44px] rounded-lg text-xs font-semibold border shadow-lg transition",
          "bg-zinc-900/90 border-zinc-700 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
        )}
        aria-label={mapControlsOpen ? "Collapse map controls" : "Expand map controls"}
        title={mapControlsOpen ? "Collapse controls" : "Expand controls"}
      >
        <ChevronRight className={cn("w-4 h-4 transition-transform", mapControlsOpen && "rotate-180")} />
      </button>

      {mapControlsOpen && (
        <>
          {/* Legend toggle */}
          <button
            onClick={toggleLegend}
            className={cn(
              "flex items-center justify-center w-[44px] h-[44px] rounded-lg text-xs font-semibold border shadow-lg transition",
              legendVisible
                ? "bg-sky-600/30 border-sky-500/50 text-sky-300"
                : "bg-zinc-900/90 border-zinc-700 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            )}
            aria-expanded={legendVisible}
            aria-controls="legend-panel"
            aria-label={legendVisible ? "Hide legend" : "Show legend"}
            title={`${legendVisible ? "Hide" : "Show"} map legend`}
          >
            <BookOpen className="w-4 h-4" />
          </button>

          {/* 2D / 3D toggle */}
          <button
            onClick={() => setViewMode(viewMode === "3d" ? "2d" : "3d")}
            className={cn(
              "flex items-center justify-center gap-1.5 min-w-[44px] min-h-[44px] px-3 py-1.5 rounded-lg text-xs font-semibold border shadow-lg transition",
              viewMode === "3d"
                ? "bg-sky-600 border-sky-500 text-white"
                : "bg-zinc-900/90 border-zinc-700 text-zinc-300 hover:bg-zinc-800"
            )}
            aria-label={`Switch to ${viewMode === "3d" ? "2D" : "3D"} map view`}
            title="Toggle between 2D and 3D map rendering"
          >
            <Box className="w-3.5 h-3.5" />
            {viewMode === "3d" ? "3D" : "2D"}
          </button>

          {/* Basemap picker — desktop (md+) */}
          <div
            className="hidden md:flex bg-zinc-900/90 backdrop-blur-sm border border-zinc-700 rounded-lg p-1.5 shadow-lg flex-col gap-1"
            role="group"
            aria-label="Basemap selector"
          >
            <div className="flex items-center gap-1 px-1 pb-1 border-b border-zinc-800">
              <Layers className="w-3 h-3 text-zinc-500" />
              <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wide">Mapa base</span>
            </div>
            {BASEMAPS.map((b) => (
              <button
                key={b.id}
                onClick={() => setMapStyle(b.id)}
                className={cn(
                  "text-left px-2 py-1 rounded text-xs transition min-w-[44px] min-h-[44px] flex items-center",
                  mapStyle === b.id
                    ? "bg-sky-600/30 text-sky-300 font-medium"
                    : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                )}
                aria-label={`Switch basemap to ${b.label}`}
                aria-pressed={mapStyle === b.id}
                title={`${b.label} basemap style`}
              >
                {b.label}
              </button>
            ))}
          </div>

          {/* Basemap picker — mobile FAB (below md) */}
          <div className="md:hidden relative" ref={basemapRef}>
            <button
              onClick={() => setBasemapOpen((prev) => !prev)}
              className={cn(
                "flex items-center justify-center w-[44px] h-[44px] rounded-lg text-xs font-semibold border shadow-lg transition",
                basemapOpen
                  ? "bg-sky-600 border-sky-500 text-white"
                  : "bg-zinc-900/90 border-zinc-700 text-zinc-300 hover:bg-zinc-800"
              )}
              aria-label="Toggle basemap selector"
              aria-expanded={basemapOpen}
              aria-haspopup="listbox"
              title="Change map style"
            >
              <Layers className="w-4 h-4" />
            </button>
            {basemapOpen && (
              <div
                className="absolute bottom-full right-0 mb-2 bg-zinc-900/90 backdrop-blur-sm border border-zinc-700 rounded-lg p-1.5 shadow-lg flex flex-col gap-1"
                role="group"
                aria-label="Basemap selector"
              >
                <div className="flex items-center gap-1 px-1 pb-1 border-b border-zinc-800">
                  <Layers className="w-3 h-3 text-zinc-500" />
                  <span className="text-[10px] font-medium text-zinc-500 uppercase tracking-wide">Mapa base</span>
                </div>
                {BASEMAPS.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => {
                      setMapStyle(b.id);
                      setBasemapOpen(false);
                    }}
                    className={cn(
                      "text-left px-2 py-1 rounded text-xs transition min-w-[44px] min-h-[44px] flex items-center",
                      mapStyle === b.id
                        ? "bg-sky-600/30 text-sky-300 font-medium"
                        : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
                    )}
                    aria-label={`Switch basemap to ${b.label}`}
                    aria-pressed={mapStyle === b.id}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
