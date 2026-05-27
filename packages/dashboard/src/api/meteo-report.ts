"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ZodError } from "zod";
import { HTTPError, TimeoutError } from "ky";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useSettingsStore } from "@/src/stores/settings-store";
import { createJetsonClient, parseJsonResilient } from "./client";
import { MeteoReportSchema } from "@/src/schemas/meteo-report.schema";
import { SchemaValidationError } from "./SchemaValidationError";
import { queryKeys } from "./query-keys";
import type { MeteoReport } from "@/src/types/meteo-report";

/** Human-readable reason for a failed request to the Jetson. */
function describeFetchError(error: unknown): string {
  if (error instanceof HTTPError) {
    const { status, statusText } = error.response;
    return `Jetson responded ${status}${statusText ? ` ${statusText}` : ""}`;
  }
  if (error instanceof TimeoutError) {
    return "Jetson did not respond in time (timeout)";
  }
  // ky surfaces network-level failures (DNS, connection refused, CORS) as TypeError.
  if (error instanceof TypeError) {
    return "Cannot reach Jetson — check the URL and that it is on the network";
  }
  return error instanceof Error ? error.message : "Unknown connection error";
}

export function useMeteoReport(): ReturnType<typeof useQuery<MeteoReport>> {
  const droneUrl = useConnectionStore((s) => s.droneUrl);
  const pollingIntervalMs = useSettingsStore((s) => s.pollingIntervalMs);

  return useQuery({
    queryKey: queryKeys.meteoReport.latest(droneUrl),
    queryFn: async () => {
      const store = useConnectionStore.getState();
      const t0 = Date.now();
      const client = createJetsonClient(droneUrl);
      let raw: unknown;
      try {
        // Await the Response (ky throws HTTPError/TimeoutError here on failure),
        // then decode tolerantly so non-UTF-8 accents survive (see client.ts).
        const response = await client.get("latest");
        raw = await parseJsonResilient(response);
      } catch (e) {
        // Network failure / timeout / non-2xx — the Jetson is unreachable.
        // Surface it as an offline connection with a readable reason so the UI
        // can stop spinning on "Connecting…" and offer a retry. Latency is left
        // untouched (time-to-failure isn't a meaningful round-trip).
        store.setConnectionState("offline");
        store.setLastError(describeFetchError(e));
        throw e instanceof Error ? e : new Error("Connection failed");
      }

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
