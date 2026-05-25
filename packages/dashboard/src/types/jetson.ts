export type JetsonStatus = {
  timestamp: string;
  system: {
    cpu_temp_c: number;
    gpu_temp_c: number;
    memory_used_pct: number;
    storage_used_pct: number;
    uptime_seconds: number;
    power_mode: "MAXN" | "MAXQ" | "15W" | "10W";
  };
  model: {
    status: "running" | "loading" | "error" | "idle";
    fps: number;
    model_name: string;
    last_inference_ms: number;
    tensorrt_optimized: boolean;
  };
  connectivity: {
    link_type: "starlink" | "4g" | "5g" | "ethernet" | "none";
    signal_strength_dbm: number;
    latency_ms: number;
    bandwidth_mbps: number;
  };
};

export type DroneTelemetry = {
  timestamp: string;
  position: {
    lat: number;
    lon: number;
    altitude_m: number;
  };
  attitude: {
    roll_deg: number;
    pitch_deg: number;
    yaw_deg: number;
  };
  speed_ms: number;
  heading_deg: number;
  altitude_m: number;
  gps_fix: "none" | "2d" | "3d" | "rtk_float" | "rtk_fixed";
  satellites: number;
  battery_pct: number;
  flight_mode: "manual" | "loiter" | "auto" | "rtl" | "guided";
};

export type FireDetection = {
  id: string;
  geometry: {
    type: "Polygon";
    coordinates: number[][][];
  };
  centroid: { lat: number; lon: number };
  confidence: number;
  size_estimate_m2: number;
  detected_at: string;
  thermal_intensity: number;
  classification_hint: "flame" | "smoke" | "ember" | "unknown";
  track_id: string | null;
};

export type DetectionResponse = {
  timestamp: string;
  detections: FireDetection[];
  meta: {
    total_detections: number;
    inference_time_ms: number;
    frame_id: string;
    camera?: {
      fov_horizontal_deg: number;
      fov_vertical_deg: number;
      resolution: { width: number; height: number };
    };
    georef_error_m: number;
  };
};

export type MissionInfo = {
  mission_id: string;
  status: "preflight" | "in_progress" | "paused" | "completed" | "aborted";
  started_at: string;
  area_of_interest?: {
    type: "Polygon";
    coordinates: number[][][];
  };
  flight_plan?: {
    waypoints: Array<{ lat: number; lon: number; altitude_m: number; index: number }>;
    grid_pattern: "lawnmower" | "spiral" | "crosshatch" | "custom";
  };
  operator?: string;
  notes?: string;
};
