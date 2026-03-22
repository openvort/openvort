import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "schedules",

    routes: [
        { path: "schedules", name: "schedules", component: () => import("./Index.vue"), meta: { title: "计划任务" } },
    ],

    menus: [
        { title: "计划任务", icon: "clock", path: "/schedules" },
    ],
} satisfies PluginFrontendConfig;
