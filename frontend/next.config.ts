import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: process.env.NEXT_PUBLIC_STATIC_EXPORT === "true" ? "export" : undefined,
};

export default nextConfig;
