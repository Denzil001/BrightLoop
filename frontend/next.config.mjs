/** @type {import('next').NextConfig} */
const nextConfig = {
  distDir: process.env.BRIGHTLOOP_BUILD_DIR || ".next",
  typescript: {tsconfigPath: process.env.BRIGHTLOOP_BUILD_DIR === ".next-benchmark" ? "tsconfig.benchmark.json" : "tsconfig.json"},
  poweredByHeader: false,
  async headers() {
    return [{source: "/:path*", headers: [
      {key: "X-Content-Type-Options", value: "nosniff"},
      {key: "X-Frame-Options", value: "DENY"},
      {key: "Referrer-Policy", value: "no-referrer"},
      {key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()"},
      {key: "Content-Security-Policy", value: "frame-ancestors 'none'; object-src 'none'; base-uri 'self'"},
    ]}];
  },
};

export default nextConfig;
