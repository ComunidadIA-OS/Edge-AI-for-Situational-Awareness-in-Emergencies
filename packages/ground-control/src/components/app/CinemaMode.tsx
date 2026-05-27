"use client";

import { useEffect, useRef } from "react";
import { Clapperboard, X } from "lucide-react";
import { useMapStore } from "@/src/stores/map-store";
import { useUIStore } from "@/src/stores/ui-store";

export function CinemaModeButton() {
  const { cinemaMode, toggleCinemaMode } = useUIStore();

  return (
    <button
      onClick={toggleCinemaMode}
      className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition"
      aria-label="Modo cine"
    >
      <Clapperboard className="w-4 h-4" />
    </button>
  );
}

export function CinemaModeOverlay() {
  const { cinemaMode, toggleCinemaMode } = useUIStore();
  const { setViewState } = useMapStore();
  const rafRef = useRef<number | null>(null);
  const bearingRef = useRef(0);

  useEffect(() => {
    if (!cinemaMode) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }

    let last = performance.now();

    function tick(now: number) {
      const dt = now - last;
      last = now;
      bearingRef.current = (bearingRef.current + dt * 0.01) % 360;
      setViewState({ bearing: bearingRef.current });
      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [cinemaMode, setViewState]);

  if (!cinemaMode) return null;

  return (
    <button
      onClick={toggleCinemaMode}
      className="fixed top-4 right-4 z-50 flex items-center gap-2 px-3 py-2 rounded-xl bg-zinc-900/80 backdrop-blur-sm border border-zinc-700 text-zinc-300 hover:text-white text-xs font-medium transition shadow-xl"
    >
      <X className="w-3.5 h-3.5" />
      Salir del modo cine
    </button>
  );
}
