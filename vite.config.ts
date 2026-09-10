import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/* The build is served by the on-premise box itself, so assets are relative
 * and nothing is fetched from a CDN at runtime. */
export default defineConfig({
  root: "web",
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  /* Each service is its own app on its own port. The same paths sit behind one
   * reverse proxy in a deployment, so only the target differs here. */
  server: {
    proxy: Object.fromEntries(
      (
        [
          ["consult", 8000],
          ["scribe", 8001],
          ["rx", 8002],
          ["labs", 8003],
          ["forensics", 8004],
        ] as const
      ).map(([name, port]) => [
        `/api/${name}`,
        {
          target: `http://127.0.0.1:${port}`,
          changeOrigin: true,
          rewrite: (path: string) => path.replace(`/api/${name}`, ""),
        },
      ]),
    ),
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
