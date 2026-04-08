import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";
import Components from "unplugin-vue-components/vite";
import svgLoader from "vite-svg-loader";
import { VortResolver } from "@openvort/vort-ui/resolver";
import { VortBizResolver } from "./src/components/vort-biz/resolver";

export default defineConfig({
    plugins: [
        vue(),
        tailwindcss(),
        Components({
            dirs: [],
            resolvers: [VortBizResolver(), VortResolver()],
            dts: "src/components.d.ts"
        }),
        svgLoader()
    ],
    resolve: {
        alias: {
            "@": "/src"
        }
    },
    server: {
        port: 9090,
        strictPort: true,
        host: true,
        headers: {
            "Cache-Control": "no-store"
        },
        proxy: {
            "/api": {
                target: "http://localhost:8090",
                changeOrigin: true,
                ws: true
            },
            "/uploads": {
                target: "http://localhost:8090",
                changeOrigin: true
            }
        }
    }
});
