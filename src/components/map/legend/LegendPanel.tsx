"use client";

import type { ReactNode } from "react";
import { Flame, Zap, Wind, Navigation, X } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useUIStore } from "@/src/stores/ui-store";

type LegendItem = {
  swatch: ReactNode;
  label: string;
  /** Plain-language explanation shown on hover. */
  info: string;
};

type LegendSection = {
  title: string;
  icon: ReactNode;
  items: LegendItem[];
};

const arrowClip = "polygon(50% 0%,100% 50%,70% 50%,70% 100%,30% 100%,30% 50%,0% 50%)";

const SECTIONS: LegendSection[] = [
  {
    title: "Fire",
    icon: <Flame className="w-3 h-3 text-red-400" />,
    items: [
      {
        swatch: <div className="w-3 h-3 rounded-sm bg-red-600/40 flex-shrink-0 border border-red-500" />,
        label: "Current perimeter",
        info: "The area that is burning right now, detected from the drone's thermal and visual feed.",
      },
      {
        swatch: <div className="w-3 h-3 rounded-sm border border-dashed border-orange-400/70 flex-shrink-0" />,
        label: "24h forecast",
        info: "Where the model predicts the fire edge will be over the next 24 hours. Scrub the time slider to step through each hour.",
      },
      {
        swatch: <div className="w-3 h-3 rounded-full bg-gradient-to-r from-yellow-400 to-red-500 flex-shrink-0" />,
        label: "Hotspots (temp)",
        info: "Individual high-temperature points detected by the drone. Brighter / redder means hotter.",
      },
    ],
  },
  {
    title: "Risk buffers",
    icon: <Zap className="w-3 h-3 text-amber-400" />,
    items: [
      {
        swatch: <div className="w-3 h-3 rounded-sm bg-red-600/25 flex-shrink-0 border border-red-600/70" />,
        label: "1 km — critical",
        info: "Within 1 km of the fire: immediate danger zone. Evacuation and asset protection take priority here.",
      },
      {
        swatch: <div className="w-3 h-3 rounded-sm bg-orange-600/20 flex-shrink-0 border border-orange-500/70" />,
        label: "3 km — alert",
        info: "Within 3 km: prepare to act. Crews and residents should be on alert and ready to move.",
      },
      {
        swatch: <div className="w-3 h-3 rounded-sm bg-yellow-500/15 flex-shrink-0 border border-yellow-500/60" />,
        label: "5 km — watch",
        info: "Within 5 km: monitor the situation. Outer ring used for situational awareness and planning.",
      },
    ],
  },
  {
    title: "Vectors",
    icon: <Wind className="w-3 h-3 text-emerald-400" />,
    items: [
      {
        swatch: <div className="w-3 h-3 bg-emerald-300 flex-shrink-0" style={{ clipPath: arrowClip }} />,
        label: "Wind",
        info: "Current wind direction and strength. The arrow points the way the wind is blowing.",
      },
      {
        swatch: <div className="w-3 h-3 bg-orange-400 flex-shrink-0" style={{ clipPath: arrowClip }} />,
        label: "Spread",
        info: "The direction the fire front is actually advancing — driven by wind, slope and fuel.",
      },
    ],
  },
  {
    title: "Assets",
    icon: <Navigation className="w-3 h-3 text-sky-400" />,
    items: [
      {
        swatch: <div className="w-3 h-3 rounded-full bg-sky-400 flex-shrink-0" />,
        label: "Drone",
        info: "Live position of the surveillance drone feeding this dashboard.",
      },
      {
        swatch: <div className="w-3 h-3 rounded-full bg-orange-500 flex-shrink-0" />,
        label: "Infrastructure",
        info: "Buildings and facilities at risk (substations, roads, settlements). See the Situation tab for distances and ETAs.",
      },
    ],
  },
];

function LegendRow({ item }: { item: LegendItem }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <div className="flex items-center gap-2 rounded-md px-1 py-0.5 -mx-1 cursor-help hover:bg-zinc-800/70 transition-colors">
          {item.swatch}
          <span className="text-xs text-zinc-400">{item.label}</span>
        </div>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="right"
          align="center"
          sideOffset={8}
          collisionPadding={8}
          className="max-w-[220px] rounded-md bg-zinc-800 border border-zinc-700 px-2.5 py-1.5 text-[11px] leading-snug text-zinc-200 shadow-xl animate-in fade-in-0 zoom-in-95 z-50"
        >
          {item.info}
          <Tooltip.Arrow className="fill-zinc-800" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export function LegendPanel() {
  const legendVisible = useUIStore((s) => s.legendVisible);
  const toggleLegend = useUIStore((s) => s.toggleLegend);

  if (!legendVisible) return null;

  return (
    <Tooltip.Provider delayDuration={200} skipDelayDuration={300}>
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

        <p className="text-[10px] text-zinc-500 leading-tight hidden md:block">
          Hover any item for a quick explanation.
        </p>

        {SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="flex items-center gap-1.5 mb-1.5">
              {section.icon}
              <p className="text-xs font-medium text-zinc-300">{section.title}</p>
            </div>
            <div className="space-y-0.5">
              {section.items.map((item) => (
                <LegendRow key={item.label} item={item} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </Tooltip.Provider>
  );
}
