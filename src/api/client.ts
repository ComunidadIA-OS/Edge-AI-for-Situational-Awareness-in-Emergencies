import ky from "ky";

export function createJetsonClient(baseUrl: string) {
  return ky.create({
    baseUrl,
    timeout: 10_000,
    retry: { limit: 2, delay: () => 500 },
    headers: { Accept: "application/json" },
  });
}

/**
 * Parse a JSON response while tolerating non-UTF-8 payloads.
 *
 * `Response.json()` always decodes bytes as UTF-8. Some Jetson/Python backends
 * emit Latin-1 / Windows-1252 (very common for Spanish text), which turns
 * accented characters — "Ermita", "Rascafría", "39 °C" — into mojibake (�).
 * We decode strictly as UTF-8 first; only if those bytes are not valid UTF-8 do
 * we fall back to Windows-1252, which is a superset of Latin-1 and covers the
 * Spanish accent set. This keeps correct UTF-8 servers untouched while rescuing
 * legacy-encoded ones.
 */
export async function parseJsonResilient(response: Response): Promise<unknown> {
  const buffer = await response.arrayBuffer();
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(buffer);
  } catch {
    text = new TextDecoder("windows-1252").decode(buffer);
  }
  return JSON.parse(text);
}
