import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Resolve dependencies of the shared, unmodified JSX renderer from this package.
const dependency = (path: string) => fileURLToPath(new URL(`./node_modules/${path}`, import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: [
      { find: /^react-katex$/, replacement: dependency("react-katex/dist/react-katex.js") },
      { find: /^katex\/(.*)$/, replacement: `${dependency("katex")}/$1` },
      { find: /^react\/jsx-runtime$/, replacement: dependency("react/jsx-runtime.js") },
      { find: /^react$/, replacement: dependency("react/index.js") },
    ],
  },
  server: {
    host: "127.0.0.1",
    port: 5186,
    strictPort: true,
    proxy: { "/v1": { target: process.env.SOCRATIC_REST_TARGET || "http://127.0.0.1:8000", changeOrigin: false } },
  },
  test: {
    include: ["tests/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    clearMocks: true,
  },
});
