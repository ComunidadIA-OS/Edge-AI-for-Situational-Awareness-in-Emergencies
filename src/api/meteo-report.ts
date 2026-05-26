"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ZodError } from "zod";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useSettingsStore } from "@/src/stores/settings-store";
import { createJetsonClient } from "./client";
import { MeteoReportSchema } from "@/src/schemas/meteo-report.schema";
import { SchemaValidationError } from "./SchemaValidationError";
import { queryKeys } from "./query-keys";
import type { MeteoReport } from "@/src/types/meteo-report";

export function useMeteoReport(): ReturnType<typeof useQuery<MeteoReport>> {
  const droneUrl = useConnectionStore((s) => s.droneUrl);
  const pollingIntervalMs = useSettingsStore((s) => s.pollingIntervalMs);

  return useQuery({
    queryKey: queryKeys.meteoReport.latest(droneUrl),
    queryFn: async () => {
      const t0 = Date.now();
      const client = createJetsonClient(droneUrl);
      const raw = await client.get("latest").json();
      const store = useConnectionStore.getState();
      const latency = Date.now() - t0;
      try {
        const report = MeteoReportSchema.parse(raw) as MeteoReport;
        store.setLastSeen(Date.now());
        store.setLatency(latency);
        store.setConnectionState("online");
        store.setLastError(null);
        return report;
      } catch (e) {
        store.setLastSeen(Date.now());
        store.setLatency(latency);
        store.setConnectionState("online");
        if (e instanceof ZodError) {
          const details = e.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
          store.setLastError(`Schema mismatch: ${details}`);
          throw new SchemaValidationError(`Payload validation failed: ${details}`);
        }
        store.setLastError(e instanceof Error ? e.message : "Unknown parsing error");
        throw e;
      }
    },
    enabled: Boolean(droneUrl),
    refetchInterval: pollingIntervalMs,
    retry: (count, err) => !(err instanceof SchemaValidationError) && count < 3,
    retryDelay: (attempt) => Math.min(1_000 * 2 ** attempt, 10_000),
    staleTime: pollingIntervalMs / 2,
  });
}

export function useInvalidateMeteoReport() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.meteoReport.all });
}
