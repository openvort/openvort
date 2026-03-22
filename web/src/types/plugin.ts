import type { RouteRecordRaw } from "vue-router";
import type { MenuConfig } from "@/router/menus";

export interface PluginFrontendConfig {
    id: string;
    routes: RouteRecordRaw[];
    menus: MenuConfig[];
}
