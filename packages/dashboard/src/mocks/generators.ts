import type {
  JetsonStatus,
  DroneTelemetry,
  DetectionResponse,
  MissionInfo,
  FireDetection,
} from "@/src/types";

// Base area of interest: near Madrid for demo purposes
const BASE_LAT = 40.4168;
const BASE_LON = -3.7025;
const AREA_RADIUS = 0.03; // ~3km

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function randInt(min: number, max: number) {
  return Math.floor(rand(min, max + 1));
}

function uuid() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

let _droneAngle = 0;
let _droneSegment = 0;
const LAWNMOWER_ROWS = 8;
const LAWNMOWER_STEP = AREA_RADIUS / LAWNMOWER_ROWS;

function nextDronePosition(): { lat: number; lon: number } {
  _droneAngle += 0.02;
  const row = _droneSegment % LAWNMOWER_ROWS;
  const lat = BASE_LAT - AREA_RADIUS / 2 + row * LAWNMOWER_STEP;
  const direction = row % 2 === 0 ? 1 : -1;
  const lon = BASE_LON + direction * ((_droneAngle % 1) - 0.5) * AREA_RADIUS;
  if (_droneAngle % 1 < 0.02) _droneSegment++;
  return { lat, lon };
}

export function generateMockStatus(): JetsonStatus {
  const healthy = Math.random() > 0.05;
  return {
    timestamp: new Date().toISOString(),
    system: {
      cpu_temp_c: rand(45, healthy ? 65 : 85),
      gpu_temp_c: rand(50, healthy ? 70 : 90),
      memory_used_pct: rand(40, healthy ? 65 : 90),
      storage_used_pct: rand(20, 60),
      uptime_seconds: Date.now() / 1000 - 1_700_000_000,
      power_mode: "MAXN",
    },
    model: {
      status: healthy ? "running" : "error",
      fps: healthy ? rand(25, 32) : 0,
      model_name: "yolov9m-26m-trt",
      last_inference_ms: healthy ? rand(18, 28) : 0,
      tensorrt_optimized: true,
    },
    connectivity: {
      link_type: "starlink",
      signal_strength_dbm: rand(-70, -45),
      latency_ms: rand(30, 120),
      bandwidth_mbps: rand(50, 200),
    },
  };
}

export function generateMockTelemetry(): DroneTelemetry {
  const pos = nextDronePosition();
  return {
    timestamp: new Date().toISOString(),
    position: { lat: pos.lat, lon: pos.lon, altitude_m: rand(80, 150) },
    attitude: {
      roll_deg: rand(-5, 5),
      pitch_deg: rand(-8, 8),
      yaw_deg: rand(0, 360),
    },
    speed_ms: rand(6, 12),
    heading_deg: rand(0, 360),
    altitude_m: rand(80, 150),
    gps_fix: "rtk_float",
    satellites: randInt(14, 22),
    battery_pct: rand(40, 95),
    flight_mode: "auto",
  };
}

function makeDetectionPolygon(
  centerLat: number,
  centerLon: number,
  sizeM: number
): number[][][] {
  const degPerMeter = 1 / 111_320;
  const halfDeg = (sizeM / 2) * degPerMeter;
  return [
    [
      [centerLon - halfDeg, centerLat - halfDeg],
      [centerLon + halfDeg, centerLat - halfDeg],
      [centerLon + halfDeg, centerLat + halfDeg],
      [centerLon - halfDeg, centerLat + halfDeg],
      [centerLon - halfDeg, centerLat - halfDeg],
    ],
  ];
}

const TRACK_IDS = ["track_0042", "track_0043", "track_0044", null, null];

export function generateMockDetections(): DetectionResponse {
  const pos = { lat: BASE_LAT + rand(-0.02, 0.02), lon: BASE_LON + rand(-0.02, 0.02) };
  const count = Math.random() < 0.15 ? 0 : randInt(1, 4);

  const detections: FireDetection[] = Array.from({ length: count }, (_, i) => {
    const lat = pos.lat + rand(-0.005, 0.005);
    const lon = pos.lon + rand(-0.005, 0.005);
    const sizeM = rand(10, 350);
    const confidence = rand(0.6, 0.97);
    return {
      id: uuid(),
      geometry: { type: "Polygon", coordinates: makeDetectionPolygon(lat, lon, sizeM) },
      centroid: { lat, lon },
      confidence,
      size_estimate_m2: sizeM * sizeM,
      detected_at: new Date().toISOString(),
      thermal_intensity: confidence * rand(0.7, 1.0),
      classification_hint: confidence > 0.8 ? "flame" : confidence > 0.65 ? "smoke" : "ember",
      track_id: TRACK_IDS[i % TRACK_IDS.length],
    };
  });

  return {
    timestamp: new Date().toISOString(),
    detections,
    meta: {
      total_detections: count,
      inference_time_ms: rand(18, 32),
      frame_id: `frame_${Date.now()}`,
      camera: {
        fov_horizontal_deg: 84,
        fov_vertical_deg: 53,
        resolution: { width: 1920, height: 1080 },
      },
      georef_error_m: rand(1, 5),
    },
  };
}

const FIXED_WAYPOINTS = Array.from({ length: 16 }, (_, i) => {
  const row = Math.floor(i / 2);
  const col = i % 2;
  return {
    lat: BASE_LAT - AREA_RADIUS / 2 + row * LAWNMOWER_STEP * 2,
    lon: BASE_LON + (col === 0 ? -AREA_RADIUS / 2 : AREA_RADIUS / 2),
    altitude_m: 120,
    index: i,
  };
});

export function generateMockMission(): MissionInfo {
  return {
    mission_id: "mission-hackathon-2026",
    status: "in_progress",
    started_at: new Date(Date.now() - 1800_000).toISOString(),
    area_of_interest: {
      type: "Polygon",
      coordinates: [
        [
          [BASE_LON - AREA_RADIUS, BASE_LAT - AREA_RADIUS],
          [BASE_LON + AREA_RADIUS, BASE_LAT - AREA_RADIUS],
          [BASE_LON + AREA_RADIUS, BASE_LAT + AREA_RADIUS],
          [BASE_LON - AREA_RADIUS, BASE_LAT + AREA_RADIUS],
          [BASE_LON - AREA_RADIUS, BASE_LAT - AREA_RADIUS],
        ],
      ],
    },
    flight_plan: {
      waypoints: FIXED_WAYPOINTS,
      grid_pattern: "lawnmower",
    },
    operator: "Ground Control",
    notes: "Heimdall hackathon demo mission — wildfire detection",
  };
}
