import { http, HttpResponse, delay } from "msw";
import {
  generateMockStatus,
  generateMockTelemetry,
  generateMockDetections,
  generateMockMission,
} from "./generators";

// Simulated Jetson endpoints — works for any base URL via wildcard matching
export const handlers = [
  http.get(/\/api\/status$/, async () => {
    await delay(50 + Math.random() * 100);
    return HttpResponse.json(generateMockStatus());
  }),

  http.get(/\/api\/telemetry$/, async () => {
    await delay(30 + Math.random() * 80);
    return HttpResponse.json(generateMockTelemetry());
  }),

  http.get(/\/api\/detections$/, async () => {
    await delay(40 + Math.random() * 120);
    return HttpResponse.json(generateMockDetections());
  }),

  http.get(/\/api\/mission$/, async () => {
    await delay(20);
    return HttpResponse.json(generateMockMission());
  }),
];
