import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "knowledge",

    routes: [
        { path: "knowledge", name: "knowledge", component: () => import("./Index.vue"), meta: { title: "知识库" } },
        { path: "knowledge/doc/:id", name: "knowledge-doc", component: () => import("./DocDetail.vue"), meta: { title: "文档详情" } },
    ],

    menus: [
        { title: "知识库", icon: "library", path: "/knowledge" },
    ],
} satisfies PluginFrontendConfig;
