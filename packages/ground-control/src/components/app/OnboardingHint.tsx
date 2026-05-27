"use client";

import { useEffect, useState } from "react";
import { FlameKindling, X } from "lucide-react";
import { useConnectionStore } from "@/src/stores/connection-store";

const STORAGE_KEY = "heimdall:onboarded:v1";

export function OnboardingHint() {
  const connectionState = useConnectionStore((s) => s.connectionState);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const dismissed = localStorage.getItem(STORAGE_KEY);
    if (dismissed === "true") {
      setVisible(false);
    }
  }, []);

  if (connectionState !== "online" || !visible) return null;

  const handleDismiss = () => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(STORAGE_KEY, "true");
      } catch {
        /* localStorage write failed — dismiss anyway (fail-safe) */
      }
    }
    setVisible(false);
  };

  return (
    <div className="fixed top-14 left-0 right-0 z-25 bg-sky-950/90 backdrop-blur-sm border-b border-sky-800/60 text-sky-200">
      <div className="flex items-center justify-between px-4 py-2 text-xs sm:text-sm">
        <div className="flex items-center gap-2 min-w-0">
          <FlameKindling className="w-4 h-4 text-sky-400 shrink-0" />
          <span className="text-sky-100 truncate">
            Drag the time slider to scrub the 24h forecast · Toggle map layers from the right sidebar
          </span>
        </div>
        <button
          onClick={handleDismiss}
          className="ml-3 px-3 py-1.5 rounded-lg bg-sky-800/50 hover:bg-sky-700/50 text-sky-300 hover:text-white transition min-w-[44px] min-h-[44px] flex items-center gap-1.5 shrink-0"
          aria-label="Dismiss onboarding hint"
        >
          <span className="text-sm">Got it</span>
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
