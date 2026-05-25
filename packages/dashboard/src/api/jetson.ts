"use client";

import { useQuery } from "@tanstack/react-query";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useSettingsStore } from "@/src/stores/settings-store";
import { createJetsonClient } from "./client";
import { queryKeys } from "./query-keys";
import {
  JetsonStatusSchema,
  DroneTelemetrySchema,
  DetectionResponseSchema,
  MissionInfoSchema,
} from "@/src/schemas/jetson.schemas";
import type {
  JetsonStatus,
  DroneTelemetry,
  DetectionResponse,
  MissionInfo,
} from "@/src/types";

function useJetsonClient() {
  const droneUrl = useConnectionStore((s) => s.droneUrl);
  return createJetsonClient(droneUrl);
}

export function useJetsonStatus() {
  const client = useJetsonClient();
  const enabled = useConnectionStore((s) => s.connectionState !== "unconfigured");
  const refetchInterval = useSettingsStore((s) => s.pollingIntervalMs) * 2.5;

  return useQuery<JetsonStatus>({
    queryKey: queryKeys.jetson.status(),
    queryFn: async () => {
      const data = await client.get("api/status").json();
      return JetsonStatusSchema.parse(data);
    },
    enabled,
    refetchInterval,
    staleTime: refetchInterval * 0.5,
    retry: 2,
  });
}

export function useJetsonTelemetry() {
  const client = useJetsonClient();
  const enabled = useConnectionStore((s) => s.connectionState !== "unconfigured");
  const refetchInterval = useSettingsStore((s) => s.pollingIntervalMs);

  return useQuery<DroneTelemetry>({
    queryKey: queryKeys.jetson.telemetry(),
    queryFn: async () => {
      const data = await client.get("api/telemetry").json();
      return DroneTelemetrySchema.parse(data);
    },
    enabled,
    refetchInterval,
    staleTime: refetchInterval * 0.5,
    retry: 2,
  });
}

export function useJetsonDetections() {
  const client = useJetsonClient();
  const enabled = useConnectionStore((s) => s.connectionState !== "unconfigured");
  const refetchInterval = useSettingsStore((s) => s.pollingIntervalMs);

  return useQuery<DetectionResponse>({
    queryKey: queryKeys.jetson.detections(),
    queryFn: async () => {
      const data = await client.get("api/detections").json();
      return DetectionResponseSchema.parse(data);
    },
    enabled,
    refetchInterval,
    staleTime: refetchInterval * 0.5,
    retry: 2,
  });
}

export function useMissionInfo() {
  const client = useJetsonClient();
  const enabled = useConnectionStore((s) => s.connectionState !== "unconfigured");

  return useQuery<MissionInfo>({
    queryKey: queryKeys.jetson.mission(),
    queryFn: async () => {
      const data = await client.get("api/mission").json();
      return MissionInfoSchema.parse(data);
    },
    enabled,
    staleTime: Infinity,
    retry: 2,
  });
}
