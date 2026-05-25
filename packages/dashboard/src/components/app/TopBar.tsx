"use client";

import { FlameKindling, Clock, Wifi, WifiOff, PanelRightOpen } from "lucide-react";
import { useMissionInfo } from "@/src/api/jetson";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useUIStore } from "@/src/stores/ui-store";
import { Badge } from "@/src/components/ui/Badge";
import { formatElapsed, cn } from "@/src/lib/utils";
import type { ConnectionState } from "@/src/types";

function connectionDot(state: ConnectionState) {
  if (state === "online") return "bg-emerald-400 animate-pulse";
  if (state === "stale") return "bg-amber-400";
  if (state === "offline") return "bg-red-500";
  if (state === "connecting") return "bg-sky-400 animate-pulse";
  return "bg-zinc-600";
}

export function TopBar() {
  const { data: mission } = useMissionInfo();
  const connectionState = useConnectionStore((s) => s.connectionState);
  const { toggleSidebar } = useUIStore();

  return (
    <header className="fixed top-0 left-0 right-0 z-40 h-14 bg-zinc-950/90 backdrop-blur-sm border-b border-zinc-800 flex items-center px-4 gap-4">
      {/* Brand */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <FlameKindling className="w-5 h-5 text-orange-400" />
        <span className="font-bold text-white text-sm tracking-tight">Heimdall</span>
        <span className="text-zinc-600 text-xs hidden sm:block">Ground Control</span>
      </div>

      {/* Mission info */}
      {mission && (
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-4 w-px bg-zinc-700" />
          <div className="min-w-0">
            <p className="text-xs text-zinc-300 font-medium truncate">
              {mission.mission_id}
            </p>
          </div>
          <Badge
            variant={
              mission.status === "in_progress"
                ? "success"
                : mission.status === "aborted"
                ? "error"
                : "default"
            }
          >
            {mission.status}
          </Badge>
          <div className="hidden sm:flex items-center gap-1 text-zinc-400 text-xs">
            <Clock className="w-3 h-3 flex-shrink-0" />
            <span>{formatElapsed(mission.started_at)}</span>
          </div>
        </div>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Connection dot */}
      <div className="flex items-center gap-2">
        <div className={cn("w-2 h-2 rounded-full", connectionDot(connectionState))} />
        {connectionState === "online" ? (
          <Wifi className="w-4 h-4 text-zinc-400" />
        ) : (
          <WifiOff className="w-4 h-4 text-zinc-600" />
        )}
      </div>

      {/* Sidebar toggle */}
      <button
        onClick={toggleSidebar}
        className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition"
        aria-label="Toggle sidebar"
      >
        <PanelRightOpen className="w-4 h-4" />
      </button>
    </header>
  );
}
