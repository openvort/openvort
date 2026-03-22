import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "knowledge",

    routes: [
        { path: "knowledge", name: "knowledge", component: () => import("./Index.vue"), meta: { title: "知识库" } },
    ],

    menus: [
        { title: "知识库", icon: "library", path: "/knowledge" },
    ],
} satisfies PluginFrontendConfig;
