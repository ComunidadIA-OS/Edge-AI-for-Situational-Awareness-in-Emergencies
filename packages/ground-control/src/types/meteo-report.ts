export type FireTrend = "growing" | "stable" | "shrinking" | "extinguishing";
export type FireIntensity = "low" | "moderate" | "high" | "extreme";
export type RiskLevel = FireIntensity;
export type GeoJSONPolygon = { type: "Polygon"; coordinates: number[][][] };
export type LonLat = [number, number];

export interface MeteoReportMetadata {
  generated_at: string;
  model_version: string;
  location: LonLat;
  forecast_hours: number;
  data_sources: string[];
}

export interface CurrentWeather {
  timestamp: string;
  temperature_c: number;
  relative_humidity_pct: number;
  wind_speed_kmh: number;
  wind_direction_deg: number;
  wind_gusts_kmh: number;
  precipitation_mm: number;
  cloud_cover_pct: number;
  soil_temperature_c: number;
  soil_moisture_pct: number;
}

export interface Hotspot {
  lat: number;
  lon: number;
  temperature_c: number;
  confidence: number;
}

export interface FirePerimeter {
  polygon: GeoJSONPolygon;
  area_ha: number;
  centroid: LonLat;
  detected_at: string;
  confidence: number;
  front_depth_m: number;
  flame_height_m: number;
  hotspots: Hotspot[];
}

export interface HourlyPrediction {
  hour_offset: number;
  timestamp: string;
  temperature_c: number;
  wind_speed_kmh: number;
  wind_direction_deg: number;
  normal_wind_kmh: number;
  precipitation_mm: number;
  fire_intensity: FireIntensity;
  spread_rate_mh: number;
  spread_direction_deg: number;
  predicted_area_ha: number;
  predicted_perimeter: GeoJSONPolygon;
  risk_level: RiskLevel;
  extinguishing_probability: number;
  flame_height_m: number;
}

export interface Prediction {
  trend: FireTrend;
  confidence: number;
  spread_direction_deg: number;
  spread_rate_mh: number;
  current_area_ha: number;
  predicted_area_24h_ha: number;
  fire_weather_index: number;
  fuel_moisture_pct: number;
  fuel_type_id: number;
  fuel_model_name: string;
  growth_rate_m2_s: number | null;
  acceleration_m2_s2: number | null;
  hourly: HourlyPrediction[];
}

export interface InfrastructureAtRisk {
  name: string;
  category: string;
  location: LonLat;
  distance_km: number;
  eta_hours: number;
  risk_level: RiskLevel;
}

export interface SituationalAwareness {
  summary: string;
  fire_behavior: string;
  weather_summary: string;
  warnings: string[];
  recommended_actions: string[];
  infrastructure_at_risk: InfrastructureAtRisk[];
}

export interface RiskBuffer {
  distance_km: number;
  geometry: GeoJSONPolygon;
}

export interface DroneTelemetry {
  lat: number;
  lon: number;
  altitud_m: number;
  heading_deg: number;
  speed_kmh: number;
  timestamp: string;
}

export interface MeteoReport {
  metadata: MeteoReportMetadata;
  current_weather: CurrentWeather;
  fire_perimeter: FirePerimeter;
  prediction: Prediction;
  situational_awareness: SituationalAwareness;
  risk_buffers: RiskBuffer[];
  drone_telemetry: DroneTelemetry | null;
}
