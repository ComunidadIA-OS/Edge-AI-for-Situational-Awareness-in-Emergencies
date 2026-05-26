"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useConnectionStore } from "@/src/stores/connection-store";
import { DashboardScreen } from "@/src/components/app/DashboardScreen";

export default function DashboardPage() {
  const router = useRouter();
  const droneUrl = useConnectionStore((s) => s.droneUrl);

  useEffect(() => {
    if (!droneUrl) router.replace("/");
  }, [droneUrl, router]);

  if (!droneUrl) return null;
  return <DashboardScreen />;
}
