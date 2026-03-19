import { defineStore } from "pinia";
import { ref } from "vue";

export const useAppStore = defineStore(
    "app",
    () => {
        /** 侧边栏是否折叠 */
        const sidebarCollapsed = ref(false);

        /** 是否显示标签页 */
        const showTabs = ref(true);

        /** 移动端侧边栏是否打开（抽屉模式） */
        const mobileSidebarOpen = ref(false);

        /** 切换侧边栏折叠状态 */
        const toggleSidebar = () => {
            sidebarCollapsed.value = !sidebarCollapsed.value;
        };

        /** 打开移动端侧边栏 */
        const openMobileSidebar = () => {
            mobileSidebarOpen.value = true;
        };

        /** 关闭移动端侧边栏 */
        const closeMobileSidebar = () => {
            mobileSidebarOpen.value = false;
        };

        return {
            sidebarCollapsed, showTabs, mobileSidebarOpen,
            toggleSidebar, openMobileSidebar, closeMobileSidebar
        };
    },
    { persist: true }
);
