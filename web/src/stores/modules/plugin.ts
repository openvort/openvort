import { defineStore } from "pinia";
import { ref } from "vue";
import request from "@/utils/request";
import type { MenuConfig } from "@/router/menus";

export interface PluginExtension {
    plugin: string;
    display_name: string;
    menus?: MenuConfig[];
    dashboard_widgets?: { type: string; title: string; api: string }[];
}

export const usePluginStore = defineStore("plugin", () => {
    const extensions = ref<PluginExtension[]>([]);
    const loaded = ref(false);
    /** 上次拉取是否成功。失败时不能把「拉不到」当成「都禁用了」，否则一次网络抖动就清空半个侧边栏。 */
    const ok = ref(false);

    /** 从后端拉取所有插件 UI 扩展（接口只返回已启用的插件） */
    const fetchExtensions = async () => {
        try {
            const res: any = await request.get("/platform/ui-extensions");
            extensions.value = res?.extensions || [];
            ok.value = true;
        } catch {
            extensions.value = [];
            ok.value = false;
        }
        loaded.value = true;
    };

    /** 插件是否启用。只对声明了 UI 扩展的插件有意义；拉取失败时一律放行。 */
    const isPluginEnabled = (name: string) =>
        !ok.value || extensions.value.some(e => e.plugin === name);

    const BUILTIN_PLUGINS = new Set(["vortflow", "vortgit", "vortsketch", "vortcert"]);

    /** 获取第三方插件声明的侧边栏菜单（内置插件已静态定义在 menus.ts） */
    const pluginMenus = () => {
        const menus: MenuConfig[] = [];
        for (const ext of extensions.value) {
            if (BUILTIN_PLUGINS.has(ext.plugin)) continue;
            if (ext.menus) {
                for (const m of ext.menus) {
                    if (m.position === "sidebar" || !m.position) {
                        menus.push({
                            title: m.label || m.title || "",
                            icon: m.icon || "puzzle",
                            path: m.path,
                            children: m.children?.map((c: any) => ({
                                title: c.label || c.title || "",
                                icon: c.icon || "",
                                path: c.path,
                            })),
                        });
                    }
                }
            }
        }
        return menus;
    };

    return { extensions, loaded, ok, fetchExtensions, pluginMenus, isPluginEnabled };
});
