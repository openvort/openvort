import { defineStore } from "pinia";
import { ref } from "vue";

export interface MenuItem {
    path: string;
    name: string;
    meta: {
        title: string;
        icon?: string;
    };
    children?: MenuItem[];
}

export const useMenuStore = defineStore("menu", () => {
    const menus = ref<MenuItem[]>([]);

    const setMenus = (data: MenuItem[]) => {
        menus.value = data;
    };

    return { menus, setMenus };
});
