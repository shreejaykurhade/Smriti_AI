import type { NextConfig } from 'next';
const config: NextConfig = {
  typescript: {tsconfigPath: process.env.SMRITI_BUILD_DIR === ".next-preview" ? "tsconfig.preview.json" : "tsconfig.production.json"},
  distDir: process.env.SMRITI_BUILD_DIR || ".next",
  async headers() {
    return [{source: '/sw.js', headers: [{key: 'Cache-Control', value: 'no-cache, no-store, must-revalidate'}]}];
  },
  async rewrites() {
    if (!process.env.LOCAL_ARCHIVE_URL || process.env.VERCEL) return [];
    return ['ask','translate','health','records','records/:id'].map(path => ({source:`/api/${path}`,destination:`${process.env.LOCAL_ARCHIVE_URL}/api/${path}`}));
  },
};
export default config;
