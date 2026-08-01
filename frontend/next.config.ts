import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  output: "standalone",
  deploymentId: process.env.SODAI_DEPLOYMENT_ID,
};

export default nextConfig;
