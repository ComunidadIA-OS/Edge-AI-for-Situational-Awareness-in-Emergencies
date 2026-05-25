"use client";

import { Flame } from "lucide-react";
import { cn } from "@/src/lib/utils";

const CONFIDENCE_SCALE = [
  { label: "85–100%", color: "bg-red-500", text: "Alta" },
  { label: "70–84%", color: "bg-orange-500", text: "Media-alta" },
  { label: "55–69%", color: "bg-yellow-500", text: "Media" },
  { label: "<55%", color: "bg-lime-400", text: "Baja" },
];

export function LegendPanel() {
  return (
    <div className="absolute bottom-8 left-4 z-10 bg-zinc-900/90 backdrop-blur-sm border border-zinc-800 rounded-xl p-3 w-44 space-y-3 shadow-xl">
      {/* Detection confidence */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Flame className="w-3 h-3 text-orange-400" />
          <p className="text-xs font-medium text-zinc-300">Confianza detección</p>
        </div>
        <div className="space-y-1">
          {CONFIDENCE_SCALE.map((item) => (
            <div key={item.label} className="flex items-center gap-2">
              <div className={cn("w-3 h-3 rounded-sm flex-shrink-0", item.color)} />
              <span className="text-xs text-zinc-400">
                {item.text} <span className="text-zinc-600">({item.label})</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Drone */}
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-sky-400 flex-shrink-0" />
        <span className="text-xs text-zinc-400">Posición dron</span>
      </div>

      {/* FIRMS */}
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-orange-500 flex-shrink-0" />
        <span className="text-xs text-zinc-400">Hotspot satélite</span>
      </div>
    </div>
  );
}
