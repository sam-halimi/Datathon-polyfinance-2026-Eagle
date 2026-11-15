import path from "node:path";
import type { NextConfig } from "next";

// Le site lit les sorties du pipeline là où il les écrit (agents/sorties/)
// et les personas de tests/scenarios/ : la racine de compilation est donc
// la racine du dépôt, pas web/.
const racine = path.resolve(__dirname, "..");

// EAGLE_EXPORT=1 : export statique dans web/out (hébergement S3 + CloudFront,
// voir deploiement/deployer.py). Sans cette variable, rien ne change.
const exporter = process.env.EAGLE_EXPORT === "1";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(exporter ? { output: "export" as const, images: { unoptimized: true }, trailingSlash: true } : {}),
  turbopack: { root: racine },
  outputFileTracingRoot: racine,
};

export default nextConfig;
