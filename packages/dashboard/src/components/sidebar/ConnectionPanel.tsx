"use client";

import {
  Wifi,
  WifiOff,
  Loader2,
  Cpu,
  Thermometer,
  Activity,
  Signal,
} from "lucide-react";
import { useJetsonStatus } from "@/src/api/jetson";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useDroneUrl } from "@/src/hooks/useDroneUrl";
import { Badge } from "@/src/components/ui/Badge";
import { cn } from "@/src/lib/utils";
import type { ConnectionState } from "@/src/types";

function connectionVariant(state: ConnectionState) {
  if (state === "online") return "success";
  if (state === "stale") return "warning";
  if (state === "offline") return "error";
  if (state === "connecting") return "info";
  return "default";
}

function connectionLabel(state: ConnectionState) {
  const labels: Record<ConnectionState, string> = {
    online: "En línea",
    stale: "Datos antiguos",
    offline: "Sin conexión",
    connecting: "Conectando",
    unconfigured: "Sin configurar",
  };
  return labels[state];
}

export function ConnectionPanel() {
  const { data: status } = useJetsonStatus();
  const connectionState = useConnectionStore((s) => s.connectionState);
  const latencyMs = useConnectionStore((s) => s.latencyMs);
  const { droneUrl, disconnect } = useDroneUrl();

  return (
    <div className="space-y-4">
      {/* Status header */}
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
            {connectionLabel(connectionState)}
          </Badge>
        </div>
        <button
          onClick={disconnect}
          className="text-xs text-zinc-500 hover:text-zinc-300 transition"
        >
          Desconectar
        </button>
      </div>

      {/* URL */}
      <div>
        <p className="text-xs text-zinc-500 mb-0.5">URL Jetson</p>
        <p className="text-xs text-zinc-300 font-mono truncate">{droneUrl || "—"}</p>
      </div>

      {/* Connectivity metrics */}
      {status && (
        <div className="grid grid-cols-2 gap-2">
          <Metric
            icon={<Signal className="w-3 h-3" />}
            label="Enlace"
            value={status.connectivity.link_type.toUpperCase()}
          />
          <Metric
            icon={<Activity className="w-3 h-3" />}
            label="Latencia"
            value={latencyMs ? `${latencyMs.toFixed(0)} ms` : "—"}
          />
          <Metric
            icon={<Cpu className="w-3 h-3" />}
            label="CPU"
            value={`${status.system.cpu_temp_c.toFixed(0)}°C`}
            warn={status.system.cpu_temp_c > 75}
          />
          <Metric
            icon={<Thermometer className="w-3 h-3" />}
            label="GPU"
            value={`${status.system.gpu_temp_c.toFixed(0)}°C`}
            warn={status.system.gpu_temp_c > 80}
          />
        </div>
      )}

      {/* Model status */}
      {status && (
        <div className="rounded-lg bg-zinc-800/60 px-3 py-2.5 space-y-1.5">
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-400">Modelo IA</p>
            <Badge
              variant={
                status.model.status === "running"
                  ? "success"
                  : status.model.status === "error"
                  ? "error"
                  : "warning"
              }
            >
              {status.model.status}
            </Badge>
          </div>
          <p className="text-xs font-mono text-zinc-300">{status.model.model_name}</p>
          <div className="flex items-center gap-3 text-xs text-zinc-400">
            <span>{status.model.fps.toFixed(1)} FPS</span>
            <span>{status.model.last_inference_ms.toFixed(0)} ms</span>
            {status.model.tensorrt_optimized && (
              <Badge variant="info">TensorRT</Badge>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({
  icon,
  label,
  value,
  warn = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div className="rounded-lg bg-zinc-800/60 px-2.5 py-2">
      <div className="flex items-center gap-1 text-zinc-400 mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className={cn("text-sm font-semibold", warn ? "text-amber-400" : "text-zinc-100")}>
        {value}
      </p>
    </div>
  );
}
