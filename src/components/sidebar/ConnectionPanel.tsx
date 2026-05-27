"use client";

import { useState } from "react";
import { Wifi, WifiOff, Loader2, Activity, Clock, Code2, Thermometer, Droplets, Wind } from "lucide-react";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useSettingsStore } from "@/src/stores/settings-store";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useDroneUrl } from "@/src/hooks/useDroneUrl";
import { Badge } from "@/src/components/ui/Badge";
import { JsonModal } from "@/src/components/ui/JsonModal";
import { cn } from "@/src/lib/utils";
import type { ConnectionState } from "@/src/types";

/** Approximate payload size of a JSON value, formatted as B / KB. */
function formatBytes(value: unknown): string {
  const bytes = new Blob([JSON.stringify(value)]).size;
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KB`;
}

function connectionVariant(state: ConnectionState) {
  if (state === "online") return "success" as const;
  if (state === "stale") return "warning" as const;
  if (state === "offline") return "error" as const;
  if (state === "connecting") return "info" as const;
  return "default" as const;
}

const CONNECTION_LABEL: Record<ConnectionState, string> = {
  online: "Online",
  stale: "Stale data",
  offline: "Offline",
  connecting: "Connecting…",
  unconfigured: "Not configured",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-zinc-800 last:border-0">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className="text-xs text-zinc-300 font-mono text-right truncate max-w-[140px]">{value}</span>
    </div>
  );
}

export function ConnectionPanel() {
  const { data: report } = useMeteoReport();
  const connectionState = useConnectionStore((s) => s.connectionState);
  const lastSeenAt = useConnectionStore((s) => s.lastSeenAt);
  const latencyMs = useConnectionStore((s) => s.latencyMs);
  const lastError = useConnectionStore((s) => s.lastError);
  const pollingIntervalMs = useSettingsStore((s) => s.pollingIntervalMs);
  const { droneUrl, disconnect } = useDroneUrl();
  const [jsonOpen, setJsonOpen] = useState(false);

  const lastSeenLabel = lastSeenAt
    ? new Date(lastSeenAt).toLocaleTimeString()
    : "—";

  const weather = report?.current_weather;

  return (
    <div className="space-y-4">
      {/* Status row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {connectionState === "connecting" ? (
            <Loader2 className="w-4 h-4 text-sky-400 animate-spin" />
          ) : connectionState === "online" ? (
            <Wifi className="w-4 h-4 text-emerald-400" />
          ) : (
            <WifiOff className="w-4 h-4 text-zinc-500" />
          )}
          <Badge variant={connectionVariant(connectionState)}>
            {CONNECTION_LABEL[connectionState]}
          </Badge>
        </div>
        <button
          onClick={disconnect}
          className="text-xs text-zinc-500 hover:text-zinc-300 transition"
        >
          Disconnect
        </button>
      </div>

      {/* Last error surface */}
      {lastError && (connectionState === "offline" || connectionState === "stale") && (
        <div className="rounded-lg bg-red-950/30 border border-red-800/40 px-3 py-2">
          <p className="text-xs text-red-300/80 truncate" title={lastError}>
            {lastError.length > 80 ? `${lastError.slice(0, 80)}…` : lastError}
          </p>
        </div>
      )}

      {/* Connection details */}
      <div className="rounded-lg bg-zinc-800/40 px-3 divide-y divide-zinc-800">
        <Row label="Jetson URL" value={droneUrl || "—"} />
        <Row label="Latency" value={latencyMs ? `${latencyMs.toFixed(0)} ms` : "—"} />
        <Row label="Polling every" value={`${(pollingIntervalMs / 1000).toFixed(1)} s`} />
        <Row
          label="Last response"
          value={
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {lastSeenLabel}
            </span>
          }
        />
      </div>

      {/* MeteoReport metadata */}
      {report && (
        <div>
          <p className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Activity className="w-3 h-3" /> Latest report
          </p>
          <div className="rounded-lg bg-zinc-800/40 px-3 divide-y divide-zinc-800">
            <Row label="Generated" value={new Date(report.metadata.generated_at).toLocaleTimeString()} />
            <Row label="Model" value={`v${report.metadata.model_version}`} />
            <Row label="Horizon" value={`${report.metadata.forecast_hours}h`} />
            <Row label="Forecast steps" value={`${report.prediction?.hourly?.length ?? 0}`} />
            <Row label="Hotspots" value={`${report.fire_perimeter?.hotspots?.length ?? 0}`} />
            <Row label="Payload" value={formatBytes(report)} />
            <Row
              label="Sources"
              value={
                <span className="text-zinc-400 text-[10px]">
                  {report.metadata.data_sources.join(", ")}
                </span>
              }
            />
          </div>
        </div>
      )}

      {/* Live weather snapshot from the payload */}
      {weather && (
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-lg bg-zinc-800/40 p-2 flex flex-col items-center gap-0.5">
            <Thermometer className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-sm font-semibold text-zinc-200">{Math.round(weather.temperature_c)}°</span>
            <span className="text-[9px] text-zinc-500 uppercase">Temp</span>
          </div>
          <div className="rounded-lg bg-zinc-800/40 p-2 flex flex-col items-center gap-0.5">
            <Droplets className="w-3.5 h-3.5 text-sky-400" />
            <span className="text-sm font-semibold text-zinc-200">{Math.round(weather.relative_humidity_pct)}%</span>
            <span className="text-[9px] text-zinc-500 uppercase">Humidity</span>
          </div>
          <div className="rounded-lg bg-zinc-800/40 p-2 flex flex-col items-center gap-0.5">
            <Wind className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-sm font-semibold text-zinc-200">{Math.round(weather.wind_speed_kmh)}</span>
            <span className="text-[9px] text-zinc-500 uppercase">km/h</span>
          </div>
        </div>
      )}

      {/* Raw payload inspector */}
      {report && (
        <button
          type="button"
          onClick={() => setJsonOpen(true)}
          className="w-full flex items-center justify-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800/40 px-3 py-2 text-xs font-medium text-zinc-300 hover:bg-zinc-700/60 hover:text-zinc-100 transition"
        >
          <Code2 className="w-3.5 h-3.5" />
          View live JSON
        </button>
      )}

      {jsonOpen && (
        <JsonModal
          title="MeteoReport — raw payload"
          data={report}
          live={connectionState === "online"}
          onClose={() => setJsonOpen(false)}
        />
      )}
    </div>
  );
}
