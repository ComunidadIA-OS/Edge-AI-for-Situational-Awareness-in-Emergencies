import { z } from "zod";

export const JetsonStatusSchema = z.object({
  timestamp: z.string().datetime(),
  system: z.object({
    cpu_temp_c: z.number().min(-40).max(125),
    gpu_temp_c: z.number().min(-40).max(125),
    memory_used_pct: z.number().min(0).max(100),
    storage_used_pct: z.number().min(0).max(100),
    uptime_seconds: z.number().min(0),
    power_mode: z.enum(["MAXN", "MAXQ", "15W", "10W"]),
  }),
  model: z.object({
    status: z.enum(["running", "loading", "error", "idle"]),
    fps: z.number().min(0),
    model_name: z.string(),
    last_inference_ms: z.number().min(0),
    tensorrt_optimized: z.boolean(),
  }),
  connectivity: z.object({
    link_type: z.enum(["starlink", "4g", "5g", "ethernet", "none"]),
    signal_strength_dbm: z.number(),
    latency_ms: z.number().min(0),
    bandwidth_mbps: z.number().min(0),
  }),
});

export const DroneTelemetrySchema = z.object({
  timestamp: z.string().datetime(),
  position: z.object({
    lat: z.number().min(-90).max(90),
    lon: z.number().min(-180).max(180),
    altitude_m: z.number(),
  }),
  attitude: z.object({
    roll_deg: z.number().min(-180).max(180),
    pitch_deg: z.number().min(-90).max(90),
    yaw_deg: z.number().min(0).max(360),
  }),
  speed_ms: z.number().min(0),
  heading_deg: z.number().min(0).max(360),
  altitude_m: z.number(),
  gps_fix: z.enum(["none", "2d", "3d", "rtk_float", "rtk_fixed"]),
  satellites: z.number().int().min(0).max(32),
  battery_pct: z.number().min(0).max(100),
  flight_mode: z.enum(["manual", "loiter", "auto", "rtl", "guided"]),
});

const FireDetectionSchema = z.object({
  id: z.string().uuid(),
  geometry: z.object({
    type: z.literal("Polygon"),
    coordinates: z.array(z.array(z.array(z.number()))),
  }),
  centroid: z.object({ lat: z.number(), lon: z.number() }),
  confidence: z.number().min(0).max(1),
  size_estimate_m2: z.number().min(0),
  detected_at: z.string().datetime(),
  thermal_intensity: z.number().min(0).max(1),
  classification_hint: z.enum(["flame", "smoke", "ember", "unknown"]),
  track_id: z.string().nullable(),
});

export const DetectionResponseSchema = z.object({
  timestamp: z.string().datetime(),
  detections: z.array(FireDetectionSchema),
  meta: z.object({
    total_detections: z.number().int().min(0),
    inference_time_ms: z.number().min(0),
    frame_id: z.string(),
    camera: z
      .object({
        fov_horizontal_deg: z.number(),
        fov_vertical_deg: z.number(),
        resolution: z.object({ width: z.number().int(), height: z.number().int() }),
      })
      .optional(),
    georef_error_m: z.number(),
  }),
});

export const MissionInfoSchema = z.object({
  mission_id: z.string(),
  status: z.enum(["preflight", "in_progress", "paused", "completed", "aborted"]),
  started_at: z.string().datetime(),
  area_of_interest: z
    .object({
      type: z.literal("Polygon"),
      coordinates: z.array(z.array(z.array(z.number()))),
    })
    .optional(),
  flight_plan: z
    .object({
      waypoints: z.array(
        z.object({
          lat: z.number(),
          lon: z.number(),
          altitude_m: z.number(),
          index: z.number().int(),
        })
      ),
      grid_pattern: z.enum(["lawnmower", "spiral", "crosshatch", "custom"]),
    })
    .optional(),
  operator: z.string().optional(),
  notes: z.string().optional(),
});
