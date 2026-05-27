import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { SituationalPanel } from "../SituationalPanel";
import { generateMeteoReport } from "@/src/mocks/generators";

vi.mock("@/src/api/meteo-report", () => ({
  useMeteoReport: vi.fn(),
}));

import { useMeteoReport } from "@/src/api/meteo-report";

const mockUseMeteoReport = vi.mocked(useMeteoReport);

describe("SituationalPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while pending", () => {
    mockUseMeteoReport.mockReturnValue({ isPending: true, isError: false, data: undefined } as never);
    render(<SituationalPanel />);
    expect(screen.getByText(/Waiting for Jetson/i)).toBeTruthy();
  });

  it("shows error state on failure", () => {
    mockUseMeteoReport.mockReturnValue({ isPending: false, isError: true, data: undefined } as never);
    render(<SituationalPanel />);
    expect(screen.getByText(/No Jetson data/i)).toBeTruthy();
  });

  it("renders KPIs when data is available", () => {
    const report = generateMeteoReport();
    mockUseMeteoReport.mockReturnValue({ isPending: false, isError: false, data: report } as never);
    render(<SituationalPanel />);
    expect(screen.getByText(/Current area/i)).toBeTruthy();
    expect(screen.getAllByText(/FWI/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Spread/i).length).toBeGreaterThan(0);
  });

  it("shows critical banner when FWI >= 70", () => {
    const report = generateMeteoReport();
    report.prediction.fire_weather_index = 75;
    mockUseMeteoReport.mockReturnValue({ isPending: false, isError: false, data: report } as never);
    render(<SituationalPanel />);
    expect(screen.getByText(/CRITICAL SITUATION/i)).toBeTruthy();
  });

  it("does not show critical banner when FWI < 70", () => {
    const report = generateMeteoReport();
    report.prediction.fire_weather_index = 45;
    report.situational_awareness.warnings = [];
    mockUseMeteoReport.mockReturnValue({ isPending: false, isError: false, data: report } as never);
    render(<SituationalPanel />);
    expect(screen.queryByText(/CRITICAL SITUATION/i)).toBeNull();
  });

  it("renders recommended actions list", () => {
    const report = generateMeteoReport();
    mockUseMeteoReport.mockReturnValue({ isPending: false, isError: false, data: report } as never);
    render(<SituationalPanel />);
    expect(screen.getByText(/Recommended actions/i)).toBeTruthy();
  });
});
