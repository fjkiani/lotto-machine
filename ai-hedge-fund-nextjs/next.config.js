/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  images: {
    domains: ['cdn.example.com'], // Add domains for remote images if needed
  },
  env: {
    // Public environment variables (will be exposed to the browser)
    NEXT_PUBLIC_APP_VERSION: '0.1.0',
  },
  experimental: {
    serverComponentsExternalPackages: ['sharp']
  },
  // Skip Node.js compatibility check for development
  skipNodeVersionCheck: process.env.NODE_ENV === 'development',
  // Buffer browser polyfill for compatibility
  webpack: (config) => {
    config.resolve.fallback = { 
      ...config.resolve.fallback, 
      "buffer": require.resolve("buffer/") 
    };
    return config;
  }
};

module.exports = nextConfig; 