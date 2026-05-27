import type {
  MeteoReport,
  FireTrend,
  FireIntensity,
} from "@/src/types/meteo-report";

// Demo fire: Sierra Norte de Madrid — realistic wildfire risk zone
const BASE_LON = -3.68;
const BASE_LAT = 40.88;

let _tick = 0;
let _windDir = 310;
let _areaHa = 52;
let _droneAngle = 0;

function rand(min: number, max: number) {
  return min + Math.random() * (max - min);
}

function randInt(min: number, max: number) {
  return Math.floor(rand(min, max + 1));
}

function ellipsePolygon(
  cLon: number,
  cLat: number,
  semiMajorKm: number,
  semiMinorKm: number,
  rotationDeg: number,
  n = 32
): number[][][] {
  const dLat = 1 / 111.32;
  const dLon = 1 / (111.32 * Math.cos((cLat * Math.PI) / 180));
  const rotRad = (rotationDeg * Math.PI) / 180;
  const pts: number[][] = [];
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * 2 * Math.PI;
    const x = semiMajorKm * Math.cos(a);
    const y = semiMinorKm * Math.sin(a);
    const rx = x * Math.cos(rotRad) - y * Math.sin(rotRad);
    const ry = x * Math.sin(rotRad) + y * Math.cos(rotRad);
    pts.push([cLon + rx * dLon, cLat + ry * dLat]);
  }
  return [pts];
}

function circlePolygon(
  cLon: number,
  cLat: number,
  radiusKm: number,
  n = 36
): number[][][] {
  const dLat = 1 / 111.32;
  const dLon = 1 / (111.32 * Math.cos((cLat * Math.PI) / 180));
  const pts: number[][] = [];
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * 2 * Math.PI;
    pts.push([cLon + radiusKm * Math.cos(a) * dLon, cLat + radiusKm * Math.sin(a) * dLat]);
  }
  return [pts];
}

function windLabel(deg: number): string {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round(deg / 45) % 8];
}

export function generateMeteoReport(): MeteoReport {
  _tick++;
  _windDir = ((_windDir + rand(-3, 3)) + 360) % 360;
  _areaHa = Math.min(_areaHa * (1 + rand(0.01, 0.03)), 2800);
  _droneAngle += 0.12;

  const now = new Date();
  const cLon = BASE_LON + rand(-0.001, 0.001);
  const cLat = BASE_LAT + rand(-0.001, 0.001);

  const semiMajorKm = Math.sqrt((_areaHa / 100) * 2 * (1 / Math.PI));
  const semiMinorKm = semiMajorKm / 2;
  const spreadDir = (_windDir + 180) % 360;

  const windSpeedKmh = rand(28, 55);
  const fwi = Math.min(96, 48 + _tick * 0.6 + rand(-4, 4));
  const intensity: FireIntensity = fwi > 70 ? "extreme" : fwi > 50 ? "high" : fwi > 30 ? "moderate" : "low";
  const trend: FireTrend = fwi > 60 ? "growing" : "stable";

  const polygon = {
    type: "Polygon" as const,
    coordinates: ellipsePolygon(cLon, cLat, semiMajorKm, semiMinorKm, spreadDir),
  };

  const hourly = Array.from({ length: 24 }, (_, h) => {
    const gf = 1 + (h + 1) * rand(0.04, 0.09);
    const shiftKm = (h + 1) * rand(0.06, 0.14);
    const dLon = 1 / (111.32 * Math.cos((cLat * Math.PI) / 180));
    const dLat = 1 / 111.32;
    const sLon = shiftKm * Math.sin((spreadDir * Math.PI) / 180) * dLon;
    const sLat = shiftKm * Math.cos((spreadDir * Math.PI) / 180) * dLat;
    const hArea = _areaHa * gf;
    const hMajor = Math.sqrt((hArea / 100) * 2 * (1 / Math.PI));
    const hMinor = hMajor / 2;
    const hFwi = Math.min(96, fwi + h * 0.4);
    const hIntensity: FireIntensity =
      hFwi > 70 ? "extreme" : hFwi > 50 ? "high" : hFwi > 30 ? "moderate" : "low";
    return {
      hour_offset: h + 1,
      timestamp: new Date(now.getTime() + (h + 1) * 3_600_000).toISOString(),
      temperature_c: rand(28, 43),
      wind_speed_kmh: windSpeedKmh + rand(-6, 12),
      wind_direction_deg: _windDir,
      normal_wind_kmh: rand(5, 18),
      precipitation_mm: 0,
      fire_intensity: hIntensity,
      spread_rate_mh: rand(150, 650),
      spread_direction_deg: spreadDir,
      predicted_area_ha: hArea,
      predicted_perimeter: {
        type: "Polygon" as const,
        coordinates: ellipsePolygon(cLon + sLon, cLat + sLat, hMajor, hMinor, spreadDir),
      },
      risk_level: hIntensity,
      extinguishing_probability: Math.max(0.02, 0.42 - h * 0.014),
      flame_height_m: rand(5, 28),
    };
  });

  const hotspots = Array.from({ length: randInt(3, 6) }, () => ({
    lat: cLat + rand(-semiMajorKm * 0.009, semiMajorKm * 0.009),
    lon: cLon + rand(-semiMajorKm * 0.009, semiMajorKm * 0.009),
    temperature_c: rand(320, 870),
    confidence: rand(0.72, 0.97),
  }));

  const dLon = 1 / (111.32 * Math.cos((cLat * Math.PI) / 180));
  const dLat = 1 / 111.32;
  const orbitKm = semiMajorKm * 1.6;
  const droneLon = cLon + orbitKm * Math.sin(_droneAngle) * dLon;
  const droneLat = cLat + orbitKm * Math.cos(_droneAngle) * dLat;

  return {
    metadata: {
      generated_at: now.toUTCString(),
      model_version: "1.0.0",
      location: [cLon, cLat],
      forecast_hours: 24,
      data_sources: ["Open-Meteo", "Balbi'15", "YOLO26m-TRT", "Scott/Burgan"],
    },
    current_weather: {
      timestamp: now.toISOString(),
      temperature_c: rand(32, 42),
      relative_humidity_pct: rand(11, 22),
      wind_speed_kmh: windSpeedKmh,
      wind_direction_deg: _windDir,
      wind_gusts_kmh: windSpeedKmh + rand(8, 22),
      precipitation_mm: 0,
      cloud_cover_pct: rand(0, 12),
      soil_temperature_c: rand(38, 54),
      soil_moisture_pct: rand(3, 11),
    },
    fire_perimeter: {
      polygon,
      area_ha: _areaHa,
      centroid: [cLon, cLat],
      detected_at: new Date(now.getTime() - _tick * 30_000).toISOString(),
      confidence: rand(0.88, 0.97),
      front_depth_m: rand(25, 130),
      flame_height_m: rand(7, 24),
      hotspots,
    },
    prediction: {
      trend,
      confidence: rand(0.78, 0.93),
      spread_direction_deg: spreadDir,
      spread_rate_mh: rand(200, 580),
      current_area_ha: _areaHa,
      predicted_area_24h_ha: _areaHa * rand(2.5, 5.2),
      fire_weather_index: fwi,
      fuel_moisture_pct: rand(4, 9),
      fuel_type_id: 7,
      fuel_model_name: "TU3 — Mediterranean chaparral",
      growth_rate_m2_s: _tick < 2 ? null : rand(1.2, 9.0),
      acceleration_m2_s2: _tick < 3 ? null : rand(-0.3, 1.9),
      hourly,
    },
    situational_awareness: {
      summary: `Active fire of ${Math.round(_areaHa)} ha in Sierra Norte (Madrid). ${intensity === "extreme" ? "Extreme" : "Severe"} behavior with ${windLabel(_windDir)} winds at ${Math.round(windSpeedKmh)} km/h. Expansion expected to the south-east.`,
      fire_behavior: `Main front with ${Math.round(rand(7, 24))} m flames and ${Math.round(rand(25, 130))} m front depth. High spread rate driven by low fuel moisture (<10%).`,
      weather_summary: `No precipitation in 72 h. T ${Math.round(rand(32, 42))}°C, RH ${Math.round(rand(11, 22))}%. ${windLabel(_windDir)} wind gusting to ${Math.round(windSpeedKmh + rand(8, 22))} km/h.`,
      warnings:
        fwi >= 70
          ? [
              "CRITICAL — Extreme FWI (>70): risk of explosive fire behavior.",
              "Relative humidity <15%: maximum-danger conditions.",
              "Gusts above 50 km/h forecast in the next 6 hours.",
            ]
          : [
              "ALERT — Elevated FWI (>50): rapid spread likely.",
              "Low relative humidity: continuous monitoring recommended.",
            ],
      recommended_actions: [
        "Evacuate settlements within 3 km south-east of the perimeter.",
        "Close N-604 access between Miraflores and Rascafría.",
        "Coordinate aerial attack: helicopters on the right flank.",
        "Activate municipal emergency plan — level 2.",
        "Keep drone in surveillance orbit; do not interrupt telemetry.",
      ],
      infrastructure_at_risk: [
        {
          name: "Miraflores electrical substation",
          category: "energy",
          location: [BASE_LON + 0.04, BASE_LAT - 0.02],
          distance_km: rand(2.8, 3.6),
          eta_hours: rand(3, 6),
          risk_level: "high" as const,
        },
        {
          name: "N-604 (Miraflores – Rascafría)",
          category: "transport",
          location: [BASE_LON + 0.02, BASE_LAT - 0.035],
          distance_km: rand(1.2, 2.2),
          eta_hours: rand(1, 3),
          risk_level: "extreme" as const,
        },
        {
          name: "Sierra Norte campground",
          category: "settlement",
          location: [BASE_LON - 0.015, BASE_LAT + 0.025],
          distance_km: rand(3.5, 4.8),
          eta_hours: rand(5, 9),
          risk_level: "moderate" as const,
        },
      ],
    },
    risk_buffers: [5, 3, 1].map((km) => ({
      distance_km: km,
      geometry: {
        type: "Polygon" as const,
        coordinates: circlePolygon(cLon, cLat, km),
      },
    })),
    drone_telemetry: {
      lat: droneLat,
      lon: droneLon,
      altitud_m: rand(90, 155),
      heading_deg: ((_droneAngle * 180) / Math.PI + 90 + 360) % 360,
      speed_kmh: rand(38, 68),
      timestamp: now.toISOString(),
    },
  };
}
