"use client";

import { useEffect, useRef, useState } from "react";
import { Play, Pause, SkipBack } from "lucide-react";
import { useMapStore } from "@/src/stores/map-store";
import { useMeteoReport } from "@/src/api/meteo-report";
import { cn } from "@/src/lib/utils";

export function TimeSlider() {
  const { data: report } = useMeteoReport();
  const { playbackHour, setPlaybackHour } = useMapStore();
  const [playing, setPlaying] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const maxHour = (report?.prediction?.hourly?.length ?? 1) - 1;

  useEffect(() => {
    if (!playing) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(() => {
      const prev = useMapStore.getState().playbackHour;
      const next = (prev ?? -1) + 1;
      if (next > maxHour) {
        setPlaying(false);
        setPlaybackHour(maxHour);
      } else {
        setPlaybackHour(next);
      }
    }, 600);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [playing, maxHour, setPlaybackHour]);

  const currentHour = playbackHour ?? 0;

  if (!report?.prediction?.hourly?.length) return null;

  return (
    <div className="absolute bottom-2 left-2 z-10 bg-zinc-900/90 backdrop-blur-sm border border-zinc-700 rounded-xl px-4 py-2.5 shadow-xl flex items-center gap-3 w-[calc(100%-1rem)] md:w-80 md:left-1/2 md:-translate-x-1/2 md:bottom-8">
      {/* Controls */}
      <button
        onClick={() => { setPlaybackHour(0); setPlaying(false); }}
        className="text-zinc-400 hover:text-zinc-200 transition flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center"
        aria-label="Restart"
      >
        <SkipBack className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => {
          if (playbackHour === null) setPlaybackHour(0);
          setPlaying((p) => !p);
        }}
        className="text-sky-400 hover:text-sky-200 transition flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center"
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
      </button>

      {/* Slider */}
      <input
        type="range"
        min={0}
        max={maxHour}
        value={currentHour}
        onChange={(e) => {
          setPlaying(false);
          setPlaybackHour(Number(e.target.value));
        }}
        className="flex-1 accent-sky-500 touch-slider md:h-1"
      />

      {/* Compact label (mobile) */}
      <span className={cn("text-xs font-mono font-semibold flex-shrink-0 w-8 text-right md:hidden", playbackHour !== null ? "text-orange-300" : "text-zinc-500")}>
        {playbackHour !== null ? `H+${playbackHour}` : "—"}
      </span>

      {/* Full label (tablet+) */}
      <span className={cn("text-xs font-mono font-semibold flex-shrink-0 w-10 text-right hidden md:inline", playbackHour !== null ? "text-orange-300" : "text-zinc-500")}>
        {playbackHour !== null ? `T+${playbackHour}h` : "—"}
      </span>

      {/* Reset to live */}
      {playbackHour !== null && (
        <>
          <button
            onClick={() => { setPlaying(false); setPlaybackHour(null); }}
            className="text-[10px] text-zinc-500 hover:text-zinc-300 transition flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center md:hidden"
          >
            L
          </button>
          <button
            onClick={() => { setPlaying(false); setPlaybackHour(null); }}
            className="text-[10px] text-zinc-500 hover:text-zinc-300 transition flex-shrink-0 min-w-[44px] min-h-[44px] flex items-center justify-center hidden md:inline-flex"
          >
            LIVE
          </button>
        </>
      )}
    </div>
  );
}
