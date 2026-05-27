import { z } from "zod";

export const GeoJSONPolygonSchema = z.object({
  type: z.literal("Polygon"),
  coordinates: z.array(z.array(z.array(z.number()))),
});

export const LonLatSchema = z.tuple([z.number(), z.number()]);

export const FireTrendSchema = z.enum(["growing", "stable", "shrinking", "extinguishing"]);
export const FireIntensitySchema = z.enum(["low", "moderate", "high", "extreme"]);
export const RiskLevelSchema = FireIntensitySchema;

export const MeteoReportMetadataSchema = z.object({
  generated_at: z.string(),
  model_version: z.string(),
  location: LonLatSchema,
  forecast_hours: z.number(),
  data_sources: z.array(z.string()),
});

export const CurrentWeatherSchema = z.object({
  timestamp: z.string(),
  temperature_c: z.number(),
  relative_humidity_pct: z.number(),
  wind_speed_kmh: z.number(),
  wind_direction_deg: z.number(),
  wind_gusts_kmh: z.number(),
  precipitation_mm: z.number(),
  cloud_cover_pct: z.number(),
  soil_temperature_c: z.number(),
  soil_moisture_pct: z.number(),
});

export const HotspotSchema = z.object({
  lat: z.number(),
  lon: z.number(),
  temperature_c: z.number(),
  confidence: z.number(),
});

export const FirePerimeterSchema = z.object({
  polygon: GeoJSONPolygonSchema,
  area_ha: z.number(),
  centroid: LonLatSchema,
  detected_at: z.string(),
  confidence: z.number(),
  front_depth_m: z.number(),
  flame_height_m: z.number(),
  hotspots: z.array(HotspotSchema),
});

export const HourlyPredictionSchema = z.object({
  hour_offset: z.number(),
  timestamp: z.string(),
  temperature_c: z.number(),
  wind_speed_kmh: z.number(),
  wind_direction_deg: z.number(),
  normal_wind_kmh: z.number(),
  precipitation_mm: z.number(),
  fire_intensity: FireIntensitySchema,
  spread_rate_mh: z.number(),
  spread_direction_deg: z.number(),
  predicted_area_ha: z.number(),
  predicted_perimeter: GeoJSONPolygonSchema,
  risk_level: RiskLevelSchema,
  extinguishing_probability: z.number(),
  flame_height_m: z.number(),
});

export const PredictionSchema = z.object({
  trend: FireTrendSchema,
  confidence: z.number(),
  spread_direction_deg: z.number(),
  spread_rate_mh: z.number(),
  current_area_ha: z.number(),
  predicted_area_24h_ha: z.number(),
  fire_weather_index: z.number(),
  fuel_moisture_pct: z.number(),
  fuel_type_id: z.number(),
  fuel_model_name: z.string(),
  growth_rate_m2_s: z.number().nullable(),
  acceleration_m2_s2: z.number().nullable(),
  hourly: z.array(HourlyPredictionSchema),
});

export const InfrastructureAtRiskSchema = z.object({
  name: z.string(),
  category: z.string(),
  location: LonLatSchema,
  distance_km: z.number(),
  eta_hours: z.number(),
  risk_level: RiskLevelSchema,
});

export const SituationalAwarenessSchema = z.object({
  summary: z.string(),
  fire_behavior: z.string(),
  weather_summary: z.string(),
  warnings: z.array(z.string()),
  recommended_actions: z.array(z.string()),
  infrastructure_at_risk: z.array(InfrastructureAtRiskSchema),
});

export const RiskBufferSchema = z.object({
  distance_km: z.number(),
  geometry: GeoJSONPolygonSchema,
});

export const DroneTelemetrySchema = z.object({
  lat: z.number(),
  lon: z.number(),
  altitud_m: z.number(),
  heading_deg: z.number(),
  speed_kmh: z.number(),
  timestamp: z.string(),
});

export const MeteoReportSchema = z.object({
  metadata: MeteoReportMetadataSchema,
  current_weather: CurrentWeatherSchema,
  fire_perimeter: FirePerimeterSchema,
  prediction: PredictionSchema,
  situational_awareness: SituationalAwarenessSchema,
  risk_buffers: z.array(RiskBufferSchema),
  drone_telemetry: DroneTelemetrySchema.nullable(),
});
