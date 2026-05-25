"use client";

import { useQuery } from "@tanstack/react-query";
import { firmsClient } from "./client";
import { queryKeys } from "./query-keys";
import { useSettingsStore } from "@/src/stores/settings-store";
import { useLayerStore } from "@/src/stores/layer-store";
import type { BBox, FIRMSResponse } from "@/src/types";

// Uses the FIRMS CSV-to-JSON endpoint (public, no key required for basic access)
export function useFIRMSData(bbox: BBox) {
  const refetchInterval = useSettingsStore((s) => s.firmsPollingMs);
  const enabled = useLayerStore((s) => s.firms);

  const bboxStr = bbox.join(",");

  return useQuery<FIRMSResponse>({
    queryKey: queryKeys.firms.byBbox(bboxStr),
    queryFn: async () => {
      // FIRMS NRT (Near Real-Time) MODIS/VIIRS active fire data
      const url = `api/area/csv/VIIRS_SNPP_NRT/World/1/${bboxStr}`;
      const text = await firmsClient.get(url).text();
      return parseFirmsCSV(text);
    },
    enabled,
    refetchInterval,
    staleTime: refetchInterval,
    retry: 1,
  });
}

function parseFirmsCSV(csv: string): FIRMSResponse {
  const lines = csv.trim().split("\n");
  if (lines.length < 2) return [];
  const headers = lines[0].split(",");

  return lines.slice(1).map((line) => {
    const values = line.split(",");
    const row: Record<string, string> = {};
    headers.forEach((h, i) => {
      row[h.trim()] = values[i]?.trim() ?? "";
    });
    return {
      latitude: parseFloat(row.latitude),
      longitude: parseFloat(row.longitude),
      brightness: parseFloat(row.bright_ti4 ?? row.brightness ?? "0"),
      scan: parseFloat(row.scan ?? "1"),
      track: parseFloat(row.track ?? "1"),
      acq_date: row.acq_date ?? "",
      acq_time: row.acq_time ?? "",
      satellite: row.satellite ?? "N/A",
      confidence: row.confidence ?? "nominal",
      frp: parseFloat(row.frp ?? "0"),
      daynight: (row.daynight as "D" | "N") ?? "D",
    };
  });
}
