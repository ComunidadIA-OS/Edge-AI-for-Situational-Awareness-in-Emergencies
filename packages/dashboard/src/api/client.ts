import ky from "ky";

export function createJetsonClient(baseUrl: string) {
  return ky.create({
    prefix: baseUrl,
    timeout: 10_000,
    retry: { limit: 2, delay: () => 500 },
    headers: { Accept: "application/json" },
  });
}

export const firmsClient = ky.create({
  prefix: "https://firms.modaps.eosdis.nasa.gov",
  timeout: 15_000,
  retry: { limit: 1 },
});

export const weatherClient = ky.create({
  prefix: "https://api.open-meteo.com",
  timeout: 10_000,
  retry: { limit: 1 },
});
