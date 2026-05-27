export type MapStyle = "osm" | "streets" | "satellite" | "terrain" | "topo";

export type BasemapConfig = {
  id: MapStyle;
  label: string;
  styleUrl: string;
};

export const BASEMAPS: BasemapConfig[] = [
  {
    id: "osm",
    label: "Dark",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  },
  {
    // OpenFreeMap — fully open-source OSM vector tiles, no API key, no usage
    // limits. Its "Liberty" style carries the rich street + POI/establishment
    // labels (shops, schools, hospitals…) the dark Carto basemap omits.
    id: "streets",
    label: "Streets + POIs",
    styleUrl: "https://tiles.openfreemap.org/styles/liberty",
  },
  {
    id: "satellite",
    label: "Voyager",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  },
  {
    id: "terrain",
    label: "Light",
    styleUrl:
      "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  },
  {
    id: "topo",
    label: "Minimal",
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
