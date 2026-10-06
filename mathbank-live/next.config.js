/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Shared add-ons (WidgetHost, MathComposer, voice) ship JSX source from ../mathbank-widgets.
  transpilePackages: ["mathbank-widgets"],
};

export default nextConfig;
