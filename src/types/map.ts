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
    label: "Satellite",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  },
  {
    id: "terrain",
    label: "Terrain",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  },
  {
    id: "topo",
    label: "Topographic",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json",
  },
];

export type LayerVisibility = {
  riskBuffers: boolean;
  predictedPerimeters: boolean;
  currentPerimeter: boolean;
  windVector: boolean;
  spreadVector: boolean;
  hotspots: boolean;
  infrastructure: boolean;
  drone: boolean;
};
