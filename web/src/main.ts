// 样式
import "@/assets/styles/index.css";
import "@openvort/vort-ui/styles";

import "@/utils/zod-zh";

import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import pinia from "./stores";

// Vite chunk 过期自动刷新：部署新版本后旧 chunk 被清除，动态 import 会 404
window.addEventListener("vite:preloadError", (event) => {
    const reloadedKey = "vite_chunk_reload";
    if (!sessionStorage.getItem(reloadedKey)) {
        sessionStorage.setItem(reloadedKey, "1");
        window.location.reload();
    }
    event.preventDefault();
});
// 成功加载后清除标记，避免影响下次部署
window.addEventListener("load", () => {
    sessionStorage.removeItem("vite_chunk_reload");
});

// 加载 SVG 图标
const iconModules = import.meta.glob("./assets/icons/**/*.svg", { eager: true, query: "?raw", import: "default" });
const icons: Record<string, string> = {};
for (const path in iconModules) {
    const name = path.replace("./assets/icons/", "").replace(".svg", "").replace(/\//g, "-");
    icons[name] = iconModules[path] as string;
}

const app = createApp(App);

// 注入图标集
app.provide("vort-icons", icons);

app.use(pinia);
app.use(router);
app.mount("#app");
