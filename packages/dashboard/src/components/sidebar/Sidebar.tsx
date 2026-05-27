"use client";

import { useState } from "react";
import { Wifi, TrendingUp, Layers, ChevronRight } from "lucide-react";
import { useUIStore, SIDEBAR_DEFAULT_W } from "@/src/stores/ui-store";
import { ConnectionPanel } from "./ConnectionPanel";
import { SituationalPanel } from "./SituationalPanel";
import { LayersPanel } from "./LayersPanel";
import { ErrorBoundary } from "@/src/components/ui/ErrorBoundary";
import { cn } from "@/src/lib/utils";
import type { SidebarTab } from "@/src/types";

type TabConfig = {
  id: SidebarTab;
  label: string;
  icon: React.ReactNode;
};

const TABS: TabConfig[] = [
  { id: "status", label: "Status", icon: <Wifi className="w-4 h-4" /> },
  { id: "situacion", label: "Situation", icon: <TrendingUp className="w-4 h-4" /> },
  { id: "layers", label: "Layers", icon: <Layers className="w-4 h-4" /> },
];

export function Sidebar() {
  const {
    sidebarOpen, sidebarWidth, setSidebarWidth,
    activeTab, setActiveTab, toggleSidebar,
  } = useUIStore();
  const [resizing, setResizing] = useState(false);

  const startResize = (e: React.PointerEvent) => {
    e.preventDefault();
    setResizing(true);
    const startX = e.clientX;
    const startW = useUIStore.getState().sidebarWidth;
    const onMove = (ev: PointerEvent) =>
      setSidebarWidth(startW + (startX - ev.clientX));
    const onUp = () => {
      setResizing(false);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  return (
    <>
      {/* Backdrop overlay — mobile only */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-15 bg-black/50 md:hidden"
          onClick={toggleSidebar}
        />
      )}

      <aside
        className={cn(
          // Base (mobile): bottom sheet
          "fixed inset-x-0 bottom-0 z-20 max-h-[60vh] rounded-t-2xl",
          "bg-zinc-900/95 backdrop-blur-sm border-t border-zinc-800",
          "flex flex-col",
          sidebarOpen ? "translate-y-0" : "translate-y-full",
          // Tablet+: right sidebar with dynamic width
          "md:top-14 md:bottom-0 md:inset-x-auto md:right-0",
          "md:max-h-none md:rounded-none md:border-t-0 md:border-l md:border-zinc-800",
          "md:translate-y-0",
          !resizing && "transition-all duration-300",
          sidebarOpen ? "md:overflow-visible" : "md:w-0 md:overflow-hidden"
        )}
        style={sidebarOpen ? { width: `${sidebarWidth}px` } : undefined}
      >
        {/* Drag handle — mobile visual indicator */}
        <div className="w-10 h-1 bg-zinc-600 rounded-full mx-auto my-2 md:hidden" />

        {/* Resize grip — desktop, on the left edge of the sidebar */}
        <div
          className={cn(
            "absolute top-0 left-0 bottom-0 w-1.5 z-10 hidden md:block",
            "cursor-ew-resize touch-none",
            "hover:bg-sky-500/40 transition-colors",
            resizing && "bg-sky-500/40"
          )}
          onPointerDown={startResize}
          onDoubleClick={() => setSidebarWidth(SIDEBAR_DEFAULT_W)}
          title="Drag to resize · double-click to reset"
        />

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
          <ErrorBoundary>
            {activeTab === "status" && <ConnectionPanel />}
            {activeTab === "situacion" && <SituationalPanel />}
            {activeTab === "layers" && <LayersPanel />}
          </ErrorBoundary>
        </div>
      </aside>

      {/* Toggle button — hidden on mobile, visible on tablet+ */}
      <button
        onClick={toggleSidebar}
        className={cn(
          "hidden md:flex",
          "fixed top-1/2 -translate-y-1/2 z-30",
          "bg-zinc-800 hover:bg-zinc-700 border border-zinc-700",
          "rounded-l-lg p-1.5",
          !resizing && "transition-all duration-300"
        )}
        style={{ right: sidebarOpen ? `${sidebarWidth}px` : 0 }}
        aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
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
