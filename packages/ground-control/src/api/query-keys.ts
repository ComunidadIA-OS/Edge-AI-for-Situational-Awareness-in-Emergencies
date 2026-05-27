export const queryKeys = {
  meteoReport: {
    all: ["meteoReport"] as const,
    latest: (url: string) => [...queryKeys.meteoReport.all, url, "latest"] as const,
  },
} as const;
