import { http, HttpResponse, delay } from "msw";
import { generateMeteoReport } from "./generators";

export const handlers = [
  http.get(/\/latest$/, async () => {
    await delay(40 + Math.random() * 80);
    return HttpResponse.json(generateMeteoReport());
  }),

  http.get(/\/history$/, async () => {
    await delay(60);
    return HttpResponse.json([]);
  }),

  http.get(/\/health$/, async () => {
    await delay(15);
    return HttpResponse.json({ status: "ok", uptime_seconds: Date.now() / 1000 - 1_748_000_000 });
  }),
];
