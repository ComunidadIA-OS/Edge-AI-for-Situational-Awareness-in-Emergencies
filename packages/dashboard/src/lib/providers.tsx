"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useRef, type ReactNode } from "react";
import { useSettingsStore } from "@/src/stores/settings-store";

function MSWProvider({ children }: { children: ReactNode }) {
  const initialized = useRef(false);
  const useMock = useSettingsStore((s) => s.useMockData);

  useEffect(() => {
    if (!useMock || initialized.current) return;
    initialized.current = true;

    import("@/src/mocks/browser").then(({ worker }) => {
      worker.start({
        onUnhandledRequest: "bypass",
        serviceWorker: { url: "/mockServiceWorker.js" },
      });
    });
  }, [useMock]);

  return <>{children}</>;
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        retry: 2,
        retryDelay: 500,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined;

function getQueryClient() {
  if (typeof window === "undefined") return makeQueryClient();
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

export function Providers({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <MSWProvider>{children}</MSWProvider>
    </QueryClientProvider>
  );
}
