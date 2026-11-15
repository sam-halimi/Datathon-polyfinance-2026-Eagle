import path from "node:path";
import type { NextConfig } from "next";

// Le site lit les sorties du pipeline là où il les écrit (agents/sorties/)
// et les personas de tests/scenarios/ : la racine de compilation est donc
// la racine du dépôt, pas web/.
const racine = path.resolve(__dirname, "..");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: { root: racine },
  outputFileTracingRoot: racine,
};

export default nextConfig;
