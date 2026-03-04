/** @type {import('next').NextConfig} */
const nextConfig = {
    // Standalone output — bundles only necessary files for production
    // Reduces container size from ~1GB to ~100MB
    output: 'standalone',

    // Enable SWC minification (faster than Terser)
    swcMinify: true,

    // Compress responses with gzip/brotli
    compress: true,

    // Production optimizations
    poweredByHeader: false,

    // Image optimization
    images: {
        formats: ['image/avif', 'image/webp'],
        minimumCacheTTL: 60,
    },

    // Headers for security and caching at scale
    async headers() {
        return [
            {
                source: '/(.*)',
                headers: [
                    { key: 'X-Content-Type-Options', value: 'nosniff' },
                    { key: 'X-Frame-Options', value: 'DENY' },
                    { key: 'X-XSS-Protection', value: '1; mode=block' },
                    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
                ],
            },
            {
                // Cache static assets aggressively
                source: '/_next/static/(.*)',
                headers: [
                    { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
                ],
            },
        ];
    },
}

module.exports = nextConfig
