export type MapStyle = "osm" | "satellite" | "terrain" | "topo";

export type BasemapConfig = {
  id: MapStyle;
  label: string;
  styleUrl: string;
};

export const BASEMAPS: BasemapConfig[] = [
  {
    id: "osm",
    label: "OpenStreetMap",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  },
  {
    id: "satellite",
    label: "Satélite",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  },
  {
    id: "terrain",
    label: "Terreno",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  },
  {
    id: "topo",
    label: "Topográfico",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json",
  },
];

export type LayerVisibility = {
  detections: boolean;
  droneTrail: boolean;
  fovCone: boolean;
  firms: boolean;
  wind: boolean;
  missionArea: boolean;
  flightPlan: boolean;
};
