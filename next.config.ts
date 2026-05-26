import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  transpilePackages: ["maplibre-gl"],
  turbopack: {
    resolveAlias: {
      "mapbox-gl": "maplibre-gl",
    },
  },
};

export default nextConfig;
