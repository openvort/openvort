import type { PluginFrontendConfig } from "@/types/plugin";

export default {
    id: "vortsketch",

    routes: [
        { path: "vortsketch", name: "vortsketch", component: () => import("./Index.vue"), meta: { title: "VortSketch" } },
    ],

    menus: [
        { title: "VortSketch", icon: "pencil-ruler", path: "/vortsketch" },
    ],
} satisfies PluginFrontendConfig;
