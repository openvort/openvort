import router from "./index";
import type { PluginExtension } from "@/stores/modules/plugin";

const vortflowViews: Record<string, () => Promise<any>> = {
    "/vortflow/board": () => import("@/views/vortflow/Board.vue"),
    "/vortflow/stories": () => import("@/views/vortflow/Stories.vue"),
    "/vortflow/tasks": () => import("@/views/vortflow/Tasks.vue"),
    "/vortflow/bugs": () => import("@/views/vortflow/Bugs.vue"),
    "/vortflow/milestones": () => import("@/views/vortflow/Milestones.vue"),
};

let registered = false;

export function registerPluginRoutes(extensions: PluginExtension[]) {
    if (registered) return;
    registered = true;

    for (const ext of extensions) {
        if (!ext.menus) continue;
        for (const menu of ext.menus) {
            const children = menu.children || [];
            for (const child of children) {
                const path = child.path;
                if (!path) continue;
                const component = vortflowViews[path];
                if (!component) continue;
                const routePath = path.startsWith("/") ? path.slice(1) : path;
                const routeName = `plugin-${ext.plugin}-${routePath.replace(/\//g, "-")}`;
                if (router.hasRoute(routeName)) continue;
                router.addRoute("root", {
                    path: routePath,
                    name: routeName,
                    component,
                    meta: { title: child.label || child.title || "" },
                });
            }
        }
    }
}
