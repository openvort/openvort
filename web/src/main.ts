// 样式
import "@/assets/styles/index.css";
import "@/components/vort/styles/index.css";

import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import pinia from "./stores";

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
