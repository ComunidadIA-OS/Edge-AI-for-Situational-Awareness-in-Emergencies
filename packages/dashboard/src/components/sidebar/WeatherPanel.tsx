"use client";

import { Wind, Thermometer, Droplets, Navigation } from "lucide-react";
import { useWeatherData } from "@/src/api/weather";
import { useJetsonTelemetry } from "@/src/api/jetson";
import { windDirectionLabel } from "@/src/lib/utils";

export function WeatherPanel() {
  const { data: telem } = useJetsonTelemetry();
  const lat = telem?.position.lat ?? 0;
  const lon = telem?.position.lon ?? 0;

  const { data: weather, isLoading, isError } = useWeatherData(lat, lon);

  if (!lat || !lon) {
    return <p className="text-xs text-zinc-500 py-4 text-center">Sin posición GPS del dron</p>;
  }

  if (isLoading && !weather) {
    return <p className="text-xs text-zinc-500 py-4 text-center">Cargando datos meteorológicos…</p>;
  }

  if (isError || !weather) {
    return <p className="text-xs text-red-400 py-4 text-center">Error al obtener datos</p>;
  }

  const c = weather.current;
  const windDir = windDirectionLabel(c.wind_direction_10m);

  return (
    <div className="space-y-3">
      <p className="text-xs text-zinc-500">
        Open-Meteo · {lat.toFixed(3)}, {lon.toFixed(3)}
      </p>

      <div className="grid grid-cols-2 gap-2">
        <WeatherCard
          icon={<Thermometer className="w-4 h-4 text-amber-400" />}
          label="Temperatura"
          value={`${c.temperature_2m.toFixed(1)}°C`}
        />
        <WeatherCard
          icon={<Droplets className="w-4 h-4 text-sky-400" />}
          label="Humedad"
          value={`${c.relative_humidity_2m.toFixed(0)}%`}
        />
        <WeatherCard
          icon={<Wind className="w-4 h-4 text-zinc-300" />}
          label="Viento"
          value={`${c.wind_speed_10m.toFixed(1)} m/s`}
        />
        <WeatherCard
          icon={<Navigation className="w-4 h-4 text-violet-400" />}
          label="Dirección"
          value={`${windDir} (${c.wind_direction_10m.toFixed(0)}°)`}
        />
      </div>

      {c.wind_gusts_10m > c.wind_speed_10m * 1.5 && (
        <div className="rounded-lg bg-amber-900/30 border border-amber-700/40 px-3 py-2">
          <p className="text-xs text-amber-300">
            Ráfagas hasta {c.wind_gusts_10m.toFixed(1)} m/s — riesgo de propagación
          </p>
        </div>
      )}
    </div>
  );
}

function WeatherCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-lg bg-zinc-800/60 px-2.5 py-2">
      <div className="flex items-center gap-1 text-zinc-400 mb-1">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <p className="text-sm font-semibold text-zinc-100">{value}</p>
    </div>
  );
}
