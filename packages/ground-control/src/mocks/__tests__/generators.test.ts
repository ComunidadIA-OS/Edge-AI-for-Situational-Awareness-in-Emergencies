import { describe, it, expect } from "vitest";
import { generateMeteoReport } from "../generators";

describe("generateMeteoReport", () => {
  it("returns a valid MeteoReport shape", () => {
    const r = generateMeteoReport();
    expect(r.metadata.model_version).toBe("1.0.0");
    expect(r.metadata.forecast_hours).toBe(24);
    expect(Array.isArray(r.metadata.data_sources)).toBe(true);
  });

  it("produces exactly 24 hourly predictions", () => {
    expect(generateMeteoReport().prediction.hourly).toHaveLength(24);
  });

  it("produces exactly 3 risk buffers at 5, 3, 1 km", () => {
    const buffers = generateMeteoReport().risk_buffers;
    expect(buffers).toHaveLength(3);
    expect(buffers.map((b) => b.distance_km).sort((a, b) => b - a)).toEqual([5, 3, 1]);
  });

  it("area_ha grows between consecutive calls", () => {
    const first = generateMeteoReport().fire_perimeter.area_ha;
    const second = generateMeteoReport().fire_perimeter.area_ha;
    expect(second).toBeGreaterThan(first);
  });

  it("drone_telemetry has lat and lon", () => {
    const r = generateMeteoReport();
    expect(typeof r.drone_telemetry?.lat).toBe("number");
    expect(typeof r.drone_telemetry?.lon).toBe("number");
  });

  it("fire_perimeter polygon is a closed ring", () => {
    const r = generateMeteoReport();
    const ring = r.fire_perimeter.polygon.coordinates[0];
    expect(ring[0]).toEqual(ring[ring.length - 1]);
  });

  it("hourly predictions have ascending hour_offset", () => {
    const hourly = generateMeteoReport().prediction.hourly;
    hourly.forEach((h, i) => expect(h.hour_offset).toBe(i + 1));
  });
});
