"use client";

import { useState, useRef } from "react";
import { Wifi, FlameKindling, AlertCircle, WifiOff } from "lucide-react";
import { useDroneUrl } from "@/src/hooks/useDroneUrl";
import { useSettingsStore } from "@/src/stores/settings-store";
import { useConnectionStore } from "@/src/stores/connection-store";
import { cn } from "@/src/lib/utils";

const DEMO_URL = "http://192.168.1.100:8000";

export function ConnectScreen() {
  const { connect } = useDroneUrl();
  const { setUseMockData, useMockData } = useSettingsStore();
  const connectionState = useConnectionStore((s) => s.connectionState);
  const [url, setUrl] = useState(DEMO_URL);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function validateUrl(raw: string): string | null {
    try {
      const u = new URL(raw);
      if (!["http:", "https:"].includes(u.protocol)) return "El protocolo debe ser http o https";
      return null;
    } catch {
      return "URL inválida — ej: http://192.168.1.100:8000";
    }
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const err = validateUrl(url.trim());
    if (err) {
      setError(err);
      inputRef.current?.focus();
      return;
    }
    setError(null);
    connect(url.trim());
  }

  function handleMockConnect() {
    setUseMockData(true);
    connect(DEMO_URL);
  }

  const isConnecting = connectionState === "connecting";

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6">
      {/* Header */}
      <div className="mb-10 text-center">
        <div className="flex items-center justify-center gap-3 mb-3">
          <FlameKindling className="text-orange-400 w-10 h-10" />
          <h1 className="text-3xl font-bold text-white tracking-tight">Heimdall</h1>
        </div>
        <p className="text-zinc-400 text-sm max-w-xs">
          Ground Control · Conciencia situacional de incendios en tiempo real
        </p>
      </div>

      {/* Connect card */}
      <div className="w-full max-w-md bg-zinc-900 rounded-2xl border border-zinc-800 p-8 shadow-2xl">
        <h2 className="text-base font-semibold text-zinc-100 mb-5 flex items-center gap-2">
          <Wifi className="w-4 h-4 text-sky-400" />
          Conectar al Jetson AGX
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs text-zinc-400 mb-1.5" htmlFor="drone-url">
              URL del Jetson
            </label>
            <input
              ref={inputRef}
              id="drone-url"
              type="url"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError(null);
              }}
              placeholder="http://192.168.1.100:8000"
              className={cn(
                "w-full bg-zinc-800 border rounded-lg px-3 py-2.5 text-sm text-white placeholder-zinc-500",
                "focus:outline-none focus:ring-2 focus:ring-sky-500 transition",
                error ? "border-red-500" : "border-zinc-700"
              )}
              disabled={isConnecting}
              autoComplete="off"
              spellCheck={false}
            />
            {error && (
              <p className="mt-1.5 text-xs text-red-400 flex items-center gap-1">
                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                {error}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isConnecting || !url.trim()}
            className={cn(
              "w-full py-2.5 rounded-lg font-medium text-sm transition-all",
              "bg-sky-600 hover:bg-sky-500 text-white",
              "disabled:opacity-50 disabled:cursor-not-allowed"
            )}
          >
            {isConnecting ? "Conectando…" : "Conectar"}
          </button>
        </form>

        <div className="relative my-5">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-zinc-800" />
          </div>
          <div className="relative flex justify-center">
            <span className="bg-zinc-900 px-3 text-xs text-zinc-500">o</span>
          </div>
        </div>

        {/* Mock data mode */}
        <button
          onClick={handleMockConnect}
          className={cn(
            "w-full py-2.5 rounded-lg font-medium text-sm transition-all flex items-center justify-center gap-2",
            useMockData
              ? "bg-orange-600/20 border border-orange-600/50 text-orange-300 hover:bg-orange-600/30"
              : "bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700"
          )}
        >
          <FlameKindling className="w-4 h-4" />
          Demo con datos simulados
        </button>

        <p className="mt-4 text-xs text-zinc-500 text-center">
          Los datos simulados generan detecciones, telemetría y estado realistas sin necesidad de hardware.
        </p>
      </div>

      {/* Footer */}
      <p className="mt-8 text-xs text-zinc-600 flex items-center gap-1.5">
        <WifiOff className="w-3 h-3" />
        Hackathon SEDIA · Reto IA Responsable · Mayo 2026 · MIT License
      </p>
    </div>
  );
}
