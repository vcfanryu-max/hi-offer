import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.NEXT_PUBLIC_DEMO_MODE === "true" ? "export" : undefined,
};

export default nextConfig;
