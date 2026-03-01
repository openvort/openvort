import router from "./index";
import type { PluginExtension } from "@/stores/modules/plugin";

const vortflowViews: Record<string, () => Promise<any>> = {
    "/vortflow/board": () => import("@/views/vortflow/Board.vue"),
    "/vortflow/stories": () => import("@/views/vortflow/Stories.vue"),
    "/vortflow/tasks": () => import("@/views/vortflow/Tasks.vue"),
    "/vortflow/bugs": () => import("@/views/vortflow/Bugs.vue"),
    "/vortflow/milestones": () => import("@/views/vortflow/Milestones.vue"),
};

const vortgitViews: Record<string, () => Promise<any>> = {
    "/vortgit/repos": () => import("@/views/vortgit/Repos.vue"),
    "/vortgit/providers": () => import("@/views/vortgit/Providers.vue"),
};

const pluginViews: Record<string, () => Promise<any>> = {
    ...vortflowViews,
    ...vortgitViews,
};

// Extra routes not driven by plugin menus (e.g. detail pages with params)
const vortflowExtraRoutes = [
    {
        path: "vortflow/projects/:id",
        name: "plugin-vortflow-project-detail",
        component: () => import("@/views/vortflow/ProjectDetail.vue"),
        meta: { title: "项目详情" },
    },
];

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
                const component = pluginViews[path];
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

    // Register extra routes (detail pages, etc.)
    for (const route of vortflowExtraRoutes) {
        if (!router.hasRoute(route.name)) {
            router.addRoute("root", route);
        }
    }
}
