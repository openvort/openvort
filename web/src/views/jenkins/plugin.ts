import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "jenkins",

    routes: [
        { path: "jenkins", name: "jenkins", component: () => import("./Index.vue"), meta: { title: "Jenkins", fullscreen: true } },
    ],

    menus: [
        { title: "Jenkins", icon: "hard-drive", path: "/jenkins" },
    ],
} satisfies PluginFrontendConfig;
