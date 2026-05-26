import ky from "ky";

export function createJetsonClient(baseUrl: string) {
  return ky.create({
    baseUrl,
    timeout: 10_000,
    retry: { limit: 2, delay: () => 500 },
    headers: { Accept: "application/json" },
  });
}
