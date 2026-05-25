"use client";

import { useEffect } from "react";
import { useJetsonStatus } from "@/src/api/jetson";
import { useConnectionStore } from "@/src/stores/connection-store";

export function useConnectionStatus() {
  const { data, isError, isFetching, dataUpdatedAt } = useJetsonStatus();
  const { setConnectionState, setLastSeen, setLatency } = useConnectionStore();
  const droneUrl = useConnectionStore((s) => s.droneUrl);

  useEffect(() => {
    if (!droneUrl) {
      setConnectionState("unconfigured");
      return;
    }

    if (isError) {
      const lastSeen = useConnectionStore.getState().lastSeenAt;
      const staleMs = Date.now() - (lastSeen ?? 0);
      setConnectionState(staleMs > 10_000 ? "offline" : "stale");
      return;
    }

    if (data) {
      setConnectionState("online");
      setLastSeen(Date.now());
      setLatency(data.connectivity.latency_ms);
    } else if (isFetching) {
      setConnectionState("connecting");
    }
  }, [data, isError, isFetching, droneUrl, setConnectionState, setLastSeen, setLatency]);

  return useConnectionStore((s) => s.connectionState);
}
