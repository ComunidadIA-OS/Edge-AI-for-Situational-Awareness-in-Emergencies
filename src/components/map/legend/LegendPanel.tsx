"use client";

import { Flame, Zap, Wind, Navigation, X } from "lucide-react";
import { useUIStore } from "@/src/stores/ui-store";

export function LegendPanel() {
  const legendVisible = useUIStore((s) => s.legendVisible);
  const toggleLegend = useUIStore((s) => s.toggleLegend);

  if (!legendVisible) return null;

  return (
    <div
      id="legend-panel"
      role="complementary"
      aria-label="Map legend"
      className="absolute bottom-8 left-4 z-10 bg-zinc-900/90 backdrop-blur-sm border border-zinc-800 rounded-xl p-3 w-44 space-y-3 shadow-xl"
    >
      <button
        type="button"
        onClick={toggleLegend}
        className="md:hidden absolute top-2 right-2 z-20 p-2 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/60 transition-colors"
        aria-label="Close legend"
      >
        <X className="w-4 h-4" />
      </button>
      <div>
        <div className="flex items-center gap-1.5 mb-1.5">
          <Flame className="w-3 h-3 text-red-400" />
          <p className="text-xs font-medium text-zinc-300">Fire</p>
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-red-600/40 flex-shrink-0 border border-red-500" />
            <span className="text-xs text-zinc-400">Current perimeter</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm border border-dashed border-orange-400/70 flex-shrink-0" />
            <span className="text-xs text-zinc-400">24h forecast</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-gradient-to-r from-yellow-400 to-red-500 flex-shrink-0" />
            <span className="text-xs text-zinc-400">Hotspots (temp)</span>
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-1.5 mb-1.5">
          <Zap className="w-3 h-3 text-amber-400" />
          <p className="text-xs font-medium text-zinc-300">Risk buffers</p>
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-red-600/25 flex-shrink-0 border border-red-600/70" />
            <span className="text-xs text-zinc-400">1 km — critical</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-orange-600/20 flex-shrink-0 border border-orange-500/70" />
            <span className="text-xs text-zinc-400">3 km — alert</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-sm bg-yellow-500/15 flex-shrink-0 border border-yellow-500/60" />
            <span className="text-xs text-zinc-400">5 km — watch</span>
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-1.5 mb-1.5">
          <Wind className="w-3 h-3 text-emerald-400" />
          <p className="text-xs font-medium text-zinc-300">Vectors</p>
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-emerald-300 flex-shrink-0" style={{ clipPath: "polygon(50% 0%,100% 50%,70% 50%,70% 100%,30% 100%,30% 50%,0% 50%)" }} />
            <span className="text-xs text-zinc-400">Wind</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-orange-400 flex-shrink-0" style={{ clipPath: "polygon(50% 0%,100% 50%,70% 50%,70% 100%,30% 100%,30% 50%,0% 50%)" }} />
            <span className="text-xs text-zinc-400">Spread</span>
          </div>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-1.5 mb-1.5">
          <Navigation className="w-3 h-3 text-sky-400" />
          <p className="text-xs font-medium text-zinc-300">Assets</p>
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-sky-400 flex-shrink-0" />
            <span className="text-xs text-zinc-400">Drone</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500 flex-shrink-0" />
            <span className="text-xs text-zinc-400">Infrastructure</span>
          </div>
        </div>
      </div>
    </div>
  );
}
