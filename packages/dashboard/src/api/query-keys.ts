export const queryKeys = {
  jetson: {
    all: ["jetson"] as const,
    status: () => [...queryKeys.jetson.all, "status"] as const,
    telemetry: () => [...queryKeys.jetson.all, "telemetry"] as const,
    detections: () => [...queryKeys.jetson.all, "detections"] as const,
    mission: () => [...queryKeys.jetson.all, "mission"] as const,
  },
  firms: {
    all: ["firms"] as const,
    byBbox: (bbox: string) => [...queryKeys.firms.all, bbox] as const,
  },
  weather: {
    all: ["weather"] as const,
    byCoords: (lat: number, lon: number) =>
      [...queryKeys.weather.all, lat, lon] as const,
  },
} as const;
