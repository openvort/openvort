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

    /** 从后端拉取所有插件 UI 扩展 */
    const fetchExtensions = async () => {
        try {
            const res: any = await request.get("/admin/plugins/ui-extensions");
            extensions.value = res?.extensions || [];
            loaded.value = true;
        } catch {
            extensions.value = [];
            loaded.value = true;
        }
    };

    /** 获取所有插件声明的侧边栏菜单 */
    const pluginMenus = () => {
        const menus: MenuConfig[] = [];
        for (const ext of extensions.value) {
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

    return { extensions, loaded, fetchExtensions, pluginMenus };
});
