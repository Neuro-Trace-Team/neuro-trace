import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config.ts";

export default mergeConfig(viteConfig, defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    restoreMocks: true,
    coverage: { reporter: ["text", "html"], include: ["src/**/*.{ts,tsx}"], exclude: ["src/main.tsx", "src/types/**"] },
  },
}));

