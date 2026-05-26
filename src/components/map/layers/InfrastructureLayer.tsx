"use client";

import { useMemo } from "react";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";
import { useMeteoReport } from "@/src/api/meteo-report";
import { useLayerStore } from "@/src/stores/layer-store";
import type { InfrastructureAtRisk, RiskLevel } from "@/src/types/meteo-report";

const RISK_COLORS: Record<RiskLevel, [number, number, number, number]> = {
  low: [74, 222, 128, 220],
  moderate: [251, 191, 36, 220],
  high: [249, 115, 22, 220],
  extreme: [239, 68, 68, 220],
};

export function useInfrastructureLayer() {
  const { data: report } = useMeteoReport();
  const visible = useLayerStore((s) => s.infrastructure);

  return useMemo(() => {
    const infra = report?.situational_awareness?.infrastructure_at_risk;
    if (!visible || !infra?.length) return [];

    const dotsLayer = new ScatterplotLayer<InfrastructureAtRisk>({
      id: "infrastructure-dots",
      data: infra,
      getPosition: (d) => [d.location[0], d.location[1]],
      getFillColor: (d) => RISK_COLORS[d.risk_level],
      getRadius: 180,
      radiusUnits: "meters",
      radiusMinPixels: 6,
      stroked: true,
      getLineColor: [255, 255, 255, 200],
      getLineWidth: 2,
      lineWidthMinPixels: 1,
      pickable: true,
    });

    const labelsLayer = new TextLayer<InfrastructureAtRisk>({
      id: "infrastructure-labels",
      data: infra,
      getPosition: (d) => [d.location[0], d.location[1]],
      getText: (d) => d.name,
      getSize: 12,
      getColor: [255, 255, 255, 220],
      getPixelOffset: [0, -18],
      getTextAnchor: "middle",
      getAlignmentBaseline: "bottom",
      fontFamily: "sans-serif",
      pickable: false,
    });

    return [dotsLayer, labelsLayer];
  }, [visible, report]);
}
