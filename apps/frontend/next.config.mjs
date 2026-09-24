const API_TARGET = process.env.API_TARGET || "http://localhost:18000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  // React Compiler is heavy during dev (full Babel pass per .tsx). Keep it off
  // by default; opt-in via `ENABLE_REACT_COMPILER=1 npm run build` for CI.
  reactCompiler: process.env.ENABLE_REACT_COMPILER === "1",
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  output: "standalone",
  experimental: {
    // One static-generation worker: keeps peak memory low on 1~2G hosts.
    // Override with NEXT_BUILD_CPUS on machines that have RAM to spare.
    cpus: Number(process.env.NEXT_BUILD_CPUS) || 1,
  },
  allowedDevOrigins: ["172.16.187.149"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_TARGET}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
