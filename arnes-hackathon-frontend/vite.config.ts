import react from "@vitejs/plugin-react-swc";
import { componentTagger } from "lovable-tagger";
import path from "path";
import { defineConfig } from "vite";

const apiProxyTarget = process.env.API_PROXY_TARGET || "http://127.0.0.1:8787";

export default defineConfig(({ mode }) => ({
	server: {
		host: "::",
		port: 8080,
		hmr: {
			overlay: false,
		},
		proxy: {
			"/api": {
				target: apiProxyTarget,
				changeOrigin: true,
			},
		},
	},
	plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "./src"),
		},
		dedupe: ["react", "react-dom", "react/jsx-runtime"],
	},
}));
