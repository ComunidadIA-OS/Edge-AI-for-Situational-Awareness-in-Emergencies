"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useConnectionStore } from "@/src/stores/connection-store";
import { ConnectScreen } from "@/src/components/app/ConnectScreen";

export default function HomePage() {
  const router = useRouter();
  const droneUrl = useConnectionStore((s) => s.droneUrl);

  useEffect(() => {
    if (droneUrl) router.replace("/dashboard");
  }, [droneUrl, router]);

  return <ConnectScreen />;
}
