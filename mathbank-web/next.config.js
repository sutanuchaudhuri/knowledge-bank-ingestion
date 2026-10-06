/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // mathbank-widgets (../mathbank-widgets, installed as a copied file: dependency) ships JSX source.
  transpilePackages: ["mathbank-widgets"],
};

module.exports = nextConfig;
