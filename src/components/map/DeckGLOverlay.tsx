"use client";

import { useEffect, useRef } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import type maplibregl from "maplibre-gl";
import { useRiskBuffersLayer } from "./layers/RiskBuffersLayer";
import { usePredictedPerimeterLayer } from "./layers/PredictedPerimeterLayer";
import { useCurrentPerimeterLayer } from "./layers/CurrentPerimeterLayer";
import { useWindVectorLayer } from "./layers/WindVectorLayer";
import { useSpreadVectorLayer } from "./layers/SpreadVectorLayer";
import { useHotspotsLayer } from "./layers/HotspotsLayer";
import { useInfrastructureLayer } from "./layers/InfrastructureLayer";
import { useDroneLayer } from "./layers/DroneLayer";

type Props = { map: maplibregl.Map };

export function DeckGLOverlay({ map }: Props) {
  const overlayRef = useRef<InstanceType<typeof MapboxOverlay> | null>(null);

  const riskBuffers = useRiskBuffersLayer();
  const predictedPerimeters = usePredictedPerimeterLayer();
  const currentPerimeter = useCurrentPerimeterLayer();
  const windVector = useWindVectorLayer();
  const spreadVector = useSpreadVectorLayer();
  const hotspots = useHotspotsLayer();
  const infrastructure = useInfrastructureLayer();
  const drone = useDroneLayer();

  useEffect(() => {
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    (map as unknown as { addControl: (ctrl: unknown) => void }).addControl(overlay);
    overlayRef.current = overlay;
    return () => {
      (map as unknown as { removeControl: (ctrl: unknown) => void }).removeControl(overlay);
      overlayRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    overlayRef.current?.setProps({
      layers: [
        ...riskBuffers,         // z=0
        ...predictedPerimeters, // z=1
        ...currentPerimeter,    // z=2
        ...windVector,          // z=3
        ...spreadVector,        // z=3
        ...hotspots,            // z=4
        ...infrastructure,      // z=5
        ...drone,               // z=6
      ],
    });
  }, [riskBuffers, predictedPerimeters, currentPerimeter, windVector, spreadVector, hotspots, infrastructure, drone]);

  return null;
}
