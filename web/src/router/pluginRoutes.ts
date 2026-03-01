import router from "./index";
import type { PluginExtension } from "@/stores/modules/plugin";

const BUILTIN_PLUGINS = new Set(["vortflow", "vortgit"]);

/** Third-party plugin view mapping — add entries as new plugins are developed */
const pluginViews: Record<string, () => Promise<any>> = {};

let registered = false;

export function registerPluginRoutes(extensions: PluginExtension[]) {
    if (registered) return;
    registered = true;

    for (const ext of extensions) {
        if (BUILTIN_PLUGINS.has(ext.plugin)) continue;
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
}
