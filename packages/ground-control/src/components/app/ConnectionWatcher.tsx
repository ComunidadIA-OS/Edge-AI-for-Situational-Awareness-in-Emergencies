"use client";

import { useEffect } from "react";
import { useConnectionStore } from "@/src/stores/connection-store";

const STALE_MS = 10_000;
const OFFLINE_MS = 30_000;

export function ConnectionWatcher() {
  useEffect(() => {
    const id = setInterval(() => {
      const { lastSeenAt, connectionState, setConnectionState, droneUrl } =
        useConnectionStore.getState();

      if (!droneUrl || connectionState === "unconfigured" || connectionState === "connecting") return;

      const age = lastSeenAt ? Date.now() - lastSeenAt : Infinity;

      if (age >= OFFLINE_MS && connectionState !== "offline") {
        setConnectionState("offline");
      } else if (age >= STALE_MS && age < OFFLINE_MS && connectionState !== "stale") {
        setConnectionState("stale");
      }
    }, 1_000);

    return () => clearInterval(id);
  }, []);

  return null;
}
