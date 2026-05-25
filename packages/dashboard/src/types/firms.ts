export type FIRMSHotspot = {
  latitude: number;
  longitude: number;
  brightness: number;
  scan: number;
  track: number;
  acq_date: string;
  acq_time: string;
  satellite: string;
  confidence: "low" | "nominal" | "high" | number | string;
  frp: number;
  daynight: "D" | "N";
};

export type FIRMSResponse = FIRMSHotspot[];
