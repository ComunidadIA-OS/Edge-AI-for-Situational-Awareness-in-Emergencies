export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function formatElapsed(startIso: string): string {
  const diffMs = Date.now() - new Date(startIso).getTime();
  const h = Math.floor(diffMs / 3_600_000);
  const m = Math.floor((diffMs % 3_600_000) / 60_000);
  const s = Math.floor((diffMs % 60_000) / 1_000);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function confidenceColor(confidence: number): [number, number, number, number] {
  // Returns RGBA for deck.gl layers
  if (confidence >= 0.85) return [239, 68, 68, 200];   // red-500
  if (confidence >= 0.70) return [249, 115, 22, 200];  // orange-500
  if (confidence >= 0.55) return [234, 179, 8, 200];   // yellow-500
  return [132, 204, 22, 180];                           // lime-400
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

export function windDirectionLabel(deg: number): string {
  const dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
  return dirs[Math.round(deg / 45) % 8];
}
