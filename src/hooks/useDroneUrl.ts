"use client";

import { useCallback } from "react";
import { useConnectionStore } from "@/src/stores/connection-store";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/src/api/query-keys";

export function useDroneUrl() {
  const queryClient = useQueryClient();
  const { droneUrl, setDroneUrl, reset } = useConnectionStore();

  const connect = useCallback(
    (url: string) => {
      const normalized = url.replace(/\/$/, "");
      setDroneUrl(normalized);
      // Invalidate all Jetson queries so they re-fire against new URL
      queryClient.invalidateQueries({ queryKey: queryKeys.meteoReport.all });
    },
    [setDroneUrl, queryClient]
  );

  const disconnect = useCallback(() => {
    reset();
    queryClient.removeQueries({ queryKey: queryKeys.meteoReport.all });
  }, [reset, queryClient]);

  // Re-attempt the current Jetson URL after a failure: clear the error, flip
  // back to "connecting", and force a fresh fetch.
  const retry = useCallback(() => {
    const { droneUrl: url, setConnectionState, setLastError } =
      useConnectionStore.getState();
    if (!url) return;
    setLastError(null);
    setConnectionState("connecting");
    queryClient.refetchQueries({ queryKey: queryKeys.meteoReport.all });
  }, [queryClient]);

  return { droneUrl, connect, disconnect, retry };
}
