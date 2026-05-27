"use client";

import { AlertTriangle, RefreshCw, Loader2 } from "lucide-react";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useDroneUrl } from "@/src/hooks/useDroneUrl";

/**
 * Top-centered banner shown when the Jetson is unreachable. Surfaces the
 * failure reason and offers a working retry (re-fetches the current URL) plus
 * a way back to the connect screen. Hidden while online or connecting.
 */
export function ConnectionStatusBanner() {
  const connectionState = useConnectionStore((s) => s.connectionState);
  const lastError = useConnectionStore((s) => s.lastError);
  const { retry, disconnect } = useDroneUrl();

  if (connectionState !== "offline") return null;

  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-30 flex justify-center px-4">
      <div className="pointer-events-auto flex max-w-md items-start gap-3 rounded-xl border border-red-800/60 bg-red-950/90 px-4 py-3 shadow-2xl backdrop-blur-sm">
        <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400" />
        <div className="min-w-0">
          <p className="text-sm font-medium text-red-200">Lost connection to Jetson</p>
          <p className="mt-0.5 break-words text-xs text-red-300/80">
            {lastError ?? "The dashboard is not receiving data."}
          </p>
          <div className="mt-2 flex items-center gap-3">
            <button
              onClick={retry}
              className="inline-flex items-center gap-1.5 rounded-md bg-red-600 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-red-500"
            >
              <RefreshCw className="h-3 w-3" />
              Retry
            </button>
            <button
              onClick={disconnect}
              className="text-xs text-red-300/70 underline transition hover:text-red-200"
            >
              Change URL
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Lightweight inline indicator for the brief window after connecting while the
 * first fetch is in flight.
 */
export function ConnectingPill() {
  const connectionState = useConnectionStore((s) => s.connectionState);
  if (connectionState !== "connecting") return null;

  return (
    <div className="pointer-events-none absolute inset-x-0 top-3 z-30 flex justify-center px-4">
      <div className="flex items-center gap-2 rounded-full border border-sky-800/60 bg-sky-950/80 px-3 py-1.5 text-xs text-sky-200 shadow-lg backdrop-blur-sm">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Connecting to Jetson…
      </div>
    </div>
  );
}
