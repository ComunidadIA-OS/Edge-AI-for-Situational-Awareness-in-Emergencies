"use client";

import { Wifi, Flame, Cloud, Layers, ChevronRight } from "lucide-react";
import { useUIStore } from "@/src/stores/ui-store";
import { ConnectionPanel } from "./ConnectionPanel";
import { DetectionsPanel } from "./DetectionsPanel";
import { WeatherPanel } from "./WeatherPanel";
import { LayersPanel } from "./LayersPanel";
import { cn } from "@/src/lib/utils";
import type { SidebarTab } from "@/src/types";

type TabConfig = {
  id: SidebarTab;
  label: string;
  icon: React.ReactNode;
};

const TABS: TabConfig[] = [
  { id: "status", label: "Estado", icon: <Wifi className="w-4 h-4" /> },
  { id: "detections", label: "Fuegos", icon: <Flame className="w-4 h-4" /> },
  { id: "weather", label: "Meteo", icon: <Cloud className="w-4 h-4" /> },
  { id: "layers", label: "Capas", icon: <Layers className="w-4 h-4" /> },
];

export function Sidebar() {
  const { sidebarOpen, activeTab, setActiveTab, toggleSidebar } = useUIStore();

  return (
    <>
      {/* Sidebar panel */}
      <aside
        className={cn(
          "fixed top-14 right-0 bottom-0 z-20",
          "bg-zinc-900/95 backdrop-blur-sm border-l border-zinc-800",
          "flex flex-col transition-all duration-300",
          sidebarOpen ? "w-72" : "w-0 overflow-hidden"
        )}
      >
        {/* Tab bar */}
        <div className="flex border-b border-zinc-800 shrink-0">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "flex-1 flex flex-col items-center gap-0.5 py-2.5 px-1 text-xs transition",
                activeTab === tab.id
                  ? "text-sky-400 border-b-2 border-sky-400"
                  : "text-zinc-500 hover:text-zinc-300 border-b-2 border-transparent"
              )}
            >
              {tab.icon}
              <span className="leading-none">{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Panel content */}
        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-zinc-700">
          {activeTab === "status" && <ConnectionPanel />}
          {activeTab === "detections" && <DetectionsPanel />}
          {activeTab === "weather" && <WeatherPanel />}
          {activeTab === "layers" && <LayersPanel />}
        </div>
      </aside>

      {/* Toggle button */}
      <button
        onClick={toggleSidebar}
        className={cn(
          "fixed top-1/2 -translate-y-1/2 z-30",
          "bg-zinc-800 hover:bg-zinc-700 border border-zinc-700",
          "rounded-l-lg p-1.5 transition",
          sidebarOpen ? "right-72" : "right-0"
        )}
        aria-label={sidebarOpen ? "Cerrar sidebar" : "Abrir sidebar"}
      >
        <ChevronRight
          className={cn(
            "w-4 h-4 text-zinc-400 transition-transform",
            sidebarOpen && "rotate-180"
          )}
        />
      </button>
    </>
  );
}
