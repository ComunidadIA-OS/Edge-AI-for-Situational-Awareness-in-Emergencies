"use client";

import { FlameKindling, Menu, X, Wifi, WifiOff, PanelRightOpen, AlertTriangle } from "lucide-react";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useUIStore } from "@/src/stores/ui-store";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useDroneUrl } from "@/src/hooks/useDroneUrl";
import { Badge } from "@/src/components/ui/Badge";
import { CinemaModeButton } from "./CinemaMode";
import { cn } from "@/src/lib/utils";
import type { ConnectionState } from "@/src/types";

function connectionDot(state: ConnectionState) {
  if (state === "online") return "bg-emerald-400 animate-pulse";
  if (state === "stale") return "bg-amber-400";
  if (state === "offline") return "bg-red-500";
  if (state === "connecting") return "bg-sky-400 animate-pulse";
  return "bg-zinc-600";
}

export function TopBar() {
  const { data: report } = useMeteoReport();
  const connectionState = useConnectionStore((s) => s.connectionState);
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { disconnect } = useDroneUrl();

  const fwi = report?.prediction?.fire_weather_index;
  const fwiCritical = fwi !== undefined && fwi >= 70;

  return (
    <header className="fixed top-0 left-0 right-0 z-40 h-14 bg-zinc-950/90 backdrop-blur-sm border-b border-zinc-800 flex items-center px-4 gap-4">
      {/* Hamburger — mobile only */}
      <button
        onClick={toggleSidebar}
        className="md:hidden p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 min-w-[44px] min-h-[44px]"
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
      >
        {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Brand */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <FlameKindling className="w-5 h-5 text-orange-400" />
        <span className="font-bold text-white text-sm tracking-tight">Heimdall</span>
        <span className="text-zinc-600 text-xs hidden md:block">Ground Control</span>
      </div>

      {/* Active fire summary from MeteoReport */}
      {report && (
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-4 w-px bg-zinc-700" />
          <span className="text-xs text-zinc-300 font-medium truncate">
            {Math.round(report.fire_perimeter.area_ha)} ha
          </span>
          {fwi !== undefined && (
            <Badge variant={fwiCritical ? "error" : fwi >= 50 ? "warning" : "default"}>
              FWI {Math.round(fwi)}
            </Badge>
          )}
          <span className="text-xs text-zinc-600 hidden md:block font-mono">
            v{report.metadata.model_version}
          </span>
        </div>
      )}

      <div className="flex-1" />

      {/* Connection indicator */}
      <div className="flex items-center gap-2">
        <div className={cn("w-2 h-2 rounded-full", connectionDot(connectionState))} />
        {connectionState === "online" ? (
          <Wifi className="w-4 h-4 text-zinc-400" />
        ) : (
          <WifiOff className="w-4 h-4 text-zinc-600" />
        )}
      </div>

      {/* Staleness banner */}
      {(connectionState === "stale" || connectionState === "offline") && (
        <div className={cn(
          "flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold border",
          connectionState === "offline"
            ? "bg-red-900/60 border-red-700/60 text-red-300"
            : "bg-amber-900/60 border-amber-700/60 text-amber-300"
        )}>
          <AlertTriangle className="w-3 h-3" />
          <span className="hidden sm:inline">
            {connectionState === "offline" ? "No Jetson signal" : "Stale data"}
          </span>
        </div>
      )}

      {/* Escape hatch — return to the connect screen to enter a different URL.
          Always reachable while connecting or offline, so a bad URL never traps
          the user on the dashboard. */}

      {/* Cinema mode */}
      <CinemaModeButton />

      {/* Sidebar toggle */}
      <button
        onClick={toggleSidebar}
        className="hidden md:block p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition min-w-[44px] min-h-[44px]"
        aria-label="Toggle sidebar"
      >
        <PanelRightOpen className="w-4 h-4" />
      </button>
    </header>
  );
}
