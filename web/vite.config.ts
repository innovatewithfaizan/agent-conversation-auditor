/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./" lets the static build run from any path (GitHub Pages project sites).
export default defineConfig({
  plugins: [react()],
  base: "./",
  test: { environment: "jsdom", globals: true },
});
