import { defineStore } from "pinia";
import { ref } from "vue";
import type { RouteLocationNormalized } from "vue-router";

export interface TabItem {
    path: string;
    name: string;
    title: string;
    closable: boolean;
}

export const useTabsStore = defineStore(
    "tabs",
    () => {
        const tabs = ref<TabItem[]>([{ path: "/", name: "workplace", title: "工作台", closable: false }]);
        const activeTab = ref("/");
        const cachedViews = ref<string[]>([]);

        const addTab = (route: RouteLocationNormalized) => {
            const title = (route.meta?.title as string) || route.name?.toString() || "";
            if (!title) return;
            const exists = tabs.value.find((t) => t.path === route.path);
            if (!exists) {
                tabs.value.push({
                    path: route.path,
                    name: route.name?.toString() || "",
                    title,
                    closable: route.path !== "/"
                });
            }
            activeTab.value = route.path;
        };

        const removeTab = (path: string) => {
            const index = tabs.value.findIndex((t) => t.path === path);
            if (index === -1) return;
            tabs.value.splice(index, 1);
            if (activeTab.value === path) {
                const next = tabs.value[index] || tabs.value[index - 1];
                activeTab.value = next?.path || "/";
            }
        };

        const removeOtherTabs = (path: string) => {
            tabs.value = tabs.value.filter((t) => !t.closable || t.path === path);
            activeTab.value = path;
        };

        const removeAllTabs = () => {
            tabs.value = tabs.value.filter((t) => !t.closable);
            activeTab.value = "/";
        };

        return { tabs, activeTab, cachedViews, addTab, removeTab, removeOtherTabs, removeAllTabs };
    },
    { persist: true }
);
