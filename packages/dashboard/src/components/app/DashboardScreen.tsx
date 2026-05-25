"use client";

import dynamic from "next/dynamic";
import { TopBar } from "./TopBar";
import { Sidebar } from "@/src/components/sidebar/Sidebar";
import { LegendPanel } from "@/src/components/map/legend/LegendPanel";
import { useConnectionStatus } from "@/src/hooks/useConnectionStatus";

// MapLibreMap uses browser-only APIs — must be dynamically imported
const MapLibreMap = dynamic(
  () => import("@/src/components/map/MapLibreMap").then((m) => m.MapLibreMap),
  { ssr: false, loading: () => <div className="w-full h-full bg-zinc-950" /> }
);

export function DashboardScreen() {
  // Keeps connection store in sync with polling results
  useConnectionStatus();

  return (
    <div className="flex flex-col h-screen bg-zinc-950 overflow-hidden">
      <TopBar />
      <main className="flex-1 relative mt-14 overflow-hidden">
        <MapLibreMap />
        <LegendPanel />
        <Sidebar />
      </main>
    </div>
  );
}
