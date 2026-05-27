"use client";

import dynamic from "next/dynamic";
import { TopBar } from "./TopBar";
import { Sidebar } from "@/src/components/sidebar/Sidebar";
import { LegendPanel } from "@/src/components/map/legend/LegendPanel";
import { MapControls } from "@/src/components/map/MapControls";
import { TimeSlider } from "@/src/components/map/TimeSlider";
import { ConnectionWatcher } from "./ConnectionWatcher";
import { ConnectionStatusBanner, ConnectingPill } from "./ConnectionStatusBanner";
import { CinemaModeOverlay } from "./CinemaMode";
import { OnboardingHint } from "./OnboardingHint";
import { useUIStore } from "@/src/stores/ui-store";

const MapLibreMap = dynamic(
  () => import("@/src/components/map/MapLibreMap").then((m) => m.MapLibreMap),
  { ssr: false, loading: () => <div className="w-full h-full bg-zinc-950" /> }
);

export function DashboardScreen() {
  const cinemaMode = useUIStore((s) => s.cinemaMode);

  return (
    <div className="flex flex-col h-screen bg-zinc-950 overflow-hidden">
      <ConnectionWatcher />
      {!cinemaMode && <TopBar />}
      <main className={`flex-1 relative overflow-hidden ${cinemaMode ? "" : "mt-14"}`}>
        <MapLibreMap />
        <ConnectionStatusBanner />
        <ConnectingPill />
        {!cinemaMode && <OnboardingHint />}
        {!cinemaMode && <LegendPanel />}
        {!cinemaMode && <MapControls />}
        {!cinemaMode && <TimeSlider />}
        {!cinemaMode && <Sidebar />}
        <CinemaModeOverlay />
      </main>
    </div>
  );
}
