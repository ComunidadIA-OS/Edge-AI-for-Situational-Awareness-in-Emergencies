"use client";

import { useQuery } from "@tanstack/react-query";
import { weatherClient } from "./client";
import { queryKeys } from "./query-keys";
import { useSettingsStore } from "@/src/stores/settings-store";
import type { WeatherResponse } from "@/src/types";

export function useWeatherData(lat: number, lon: number) {
  const refetchInterval = useSettingsStore((s) => s.weatherPollingMs);
  const enabled = lat !== 0 && lon !== 0;

  return useQuery<WeatherResponse>({
    queryKey: queryKeys.weather.byCoords(lat, lon),
    queryFn: async () => {
      const params = new URLSearchParams({
        latitude: lat.toFixed(4),
        longitude: lon.toFixed(4),
        current:
          "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,weather_code",
        wind_speed_unit: "ms",
        timezone: "auto",
      });
      return weatherClient
        .get(`v1/forecast?${params}`)
        .json<WeatherResponse>();
    },
    enabled,
    refetchInterval,
    staleTime: refetchInterval,
    retry: 1,
  });
}
