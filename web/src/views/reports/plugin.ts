import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "reports",

    routes: [
        { path: "reports", name: "reports", component: () => import("./Index.vue"), meta: { title: "汇报中心" } },
    ],

    menus: [
        { title: "汇报中心", icon: "file-bar-chart", path: "/reports" },
    ],
} satisfies PluginFrontendConfig;
