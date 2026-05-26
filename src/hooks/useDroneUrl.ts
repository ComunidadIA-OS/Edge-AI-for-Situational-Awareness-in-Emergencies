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

  return { droneUrl, connect, disconnect };
}
