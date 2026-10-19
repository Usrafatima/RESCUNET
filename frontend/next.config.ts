import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow external tile servers for Leaflet
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.basemaps.cartocdn.com",
      },
      {
        protocol: "https",
        hostname: "unpkg.com",
      },
    ],
  },
  // Silence leaflet CSS warning
  transpilePackages: ["react-leaflet", "leaflet"],
};

export default nextConfig;
