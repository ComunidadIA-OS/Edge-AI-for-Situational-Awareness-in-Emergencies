import type { Feature, FeatureCollection, Polygon, Point, LineString, GeoJsonProperties } from "geojson";

export type LatLon = { lat: number; lon: number };

export type BBox = [west: number, south: number, east: number, north: number];

export type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
};

export type GeoPolygon = Feature<Polygon, GeoJsonProperties>;
export type GeoPoint = Feature<Point, GeoJsonProperties>;
export type GeoLine = Feature<LineString, GeoJsonProperties>;
export type GeoFeatureCollection = FeatureCollection<Polygon | Point | LineString, GeoJsonProperties>;
