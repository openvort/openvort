<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAppStore, useUserStore, usePluginStore } from "@/stores";
import { menuConfig, type MenuConfig } from "@/router/menus";
import {
    Home, BarChart2, FileText, FileBarChart, Table, File, AlertTriangle,
    CheckCircle, User, Settings, ChevronDown, PanelLeftClose, PanelLeftOpen,
    MessageSquare, Puzzle, Radio, Users, Clock, BookOpen, Webhook, GitBranch, Cpu,
    Kanban, LayoutDashboard, ListChecks, CheckSquare, Bug, Milestone,
    Wrench, FolderGit2, Server, Shield
} from "lucide-vue-next";

const props = defineProps<{ isMobile?: boolean }>();

const route = useRoute();
const router = useRouter();
const appStore = useAppStore();
const userStore = useUserStore();
const pluginStore = usePluginStore();
const SUBMENU_STATE_KEY = "openvort.sidebar.open-submenus";
const expandedMenus = ref<string[]>([]);

const collapsed = computed(() => props.isMobile ? false : appStore.sidebarCollapsed);

const loadExpandedMenus = () => {
    if (typeof window === "undefined") return;
    try {
        const raw = window.localStorage.getItem(SUBMENU_STATE_KEY);
        expandedMenus.value = raw ? JSON.parse(raw) : [];
    } catch {
        expandedMenus.value = [];
    }
};

const persistExpandedMenus = () => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(SUBMENU_STATE_KEY, JSON.stringify(expandedMenus.value));
};

loadExpandedMenus();

// 图标映射
const iconMap: Record<string, any> = {
    home: Home, "bar-chart-2": BarChart2, "file-text": FileText, "file-bar-chart": FileBarChart,
    table: Table, file: File, "alert-triangle": AlertTriangle,
    "check-circle": CheckCircle, user: User, settings: Settings,
    "message-square": MessageSquare, puzzle: Puzzle, radio: Radio, users: Users,
    clock: Clock, "book-open": BookOpen, webhook: Webhook, "git-branch": GitBranch, cpu: Cpu,
    kanban: Kanban, "layout-dashboard": LayoutDashboard, "list-checks": ListChecks,
    "check-square": CheckSquare, bug: Bug, milestone: Milestone,
    wrench: Wrench, "folder-git-2": FolderGit2, server: Server, shield: Shield,
};

const filterByRole = (items: MenuConfig[]) => {
    const roles = userStore.userInfo.roles || [];
    return items.filter(item => {
        if (!item.requiredRole) return true;
        return roles.includes(item.requiredRole);
    });
};

const allMenus = computed(() => {
    const staticMenus = filterByRole(menuConfig);
    const dynamicMenus = pluginStore.pluginMenus();
    if (!dynamicMenus.length) return staticMenus;
    const profileIdx = staticMenus.findIndex(m => m.position === "bottom");
    if (profileIdx >= 0) {
        const result = [...staticMenus];
        result.splice(profileIdx, 0, ...dynamicMenus);
        return result;
    }
    return [...staticMenus, ...dynamicMenus];
});

const filteredMenus = computed(() => allMenus.value.filter(m => m.position !== "bottom"));
const bottomMenus = computed(() => allMenus.value.filter(m => m.position === "bottom"));

// 当前展开的菜单
const openKeys = computed(() => {
    const keys = new Set(expandedMenus.value);

    const parent = route.meta?.parent as string;
    if (parent) {
        const menu = filteredMenus.value.find((m) => m.title === parent);
        if (menu) keys.add(menu.title);
        return [...keys];
    }
    const activeParent = filteredMenus.value.find((m) =>
        m.children?.some((c) => c.path === route.path)
    );
    if (activeParent) {
        keys.add(activeParent.title);
    }
    return [...keys];
});

watch(filteredMenus, () => {
    const validParentTitles = new Set(
        filteredMenus.value.filter((m) => m.children?.length).map((m) => m.title)
    );
    const nextExpanded = expandedMenus.value.filter((title) => validParentTitles.has(title));
    if (nextExpanded.length !== expandedMenus.value.length) {
        expandedMenus.value = nextExpanded;
        persistExpandedMenus();
    }
}, { immediate: true });

const isActive = (item: MenuConfig): boolean => {
    if (item.path) return route.path === item.path;
    return item.children?.some((c) => c.path === route.path) || false;
};

const isChildActive = (child: MenuConfig): boolean => {
    return route.path === child.path;
};

const handleClick = (item: MenuConfig) => {
    if (item.path) {
        router.push(item.path);
        if (props.isMobile) {
            appStore.closeMobileSidebar();
        }
    }
};

const handleChildClick = (child: MenuConfig) => {
    handleClick(child);
};

const handleMenuToggle = (title: string, event: Event) => {
    const isOpen = (event.currentTarget as HTMLDetailsElement).open;
    const next = new Set(expandedMenus.value);
    if (isOpen) next.add(title);
    else next.delete(title);
    expandedMenus.value = [...next];
    persistExpandedMenus();
};
</script>

<template>
    <aside
        class="flex flex-col h-full bg-white border-r border-gray-100 transition-all duration-300 flex-shrink-0"
        :class="[
            isMobile
                ? 'fixed inset-y-0 left-0 z-50 w-[220px] shadow-xl'
                : collapsed ? 'w-[64px]' : 'w-[220px]',
            isMobile && !appStore.mobileSidebarOpen ? '-translate-x-full' : 'translate-x-0'
        ]"
    >
        <!-- Logo -->
        <div class="flex items-center h-[56px] px-4 border-b border-gray-100 flex-shrink-0">
            <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
                <span class="text-white font-bold text-sm">O</span>
            </div>
            <transition name="fade">
                <h1 v-if="!collapsed" class="ml-3 text-[16px] font-semibold text-gray-900 whitespace-nowrap">
                    OpenVort
                </h1>
            </transition>
        </div>

        <!-- 菜单 -->
        <nav class="flex-1 overflow-y-auto py-2 px-2">
            <template v-for="item in filteredMenus" :key="item.title">
                <!-- 分组标签 -->
                <div v-if="item.label" class="mt-3 mb-1 first:mt-0" :class="collapsed ? 'border-t border-gray-100 mx-2' : ''">
                    <span v-if="!collapsed" class="px-3 text-[11px] font-medium text-gray-400 uppercase tracking-wider">{{ item.label }}</span>
                </div>

                <!-- 无子菜单 -->
                <div
                    v-if="!item.children"
                    class="flex items-center h-[40px] px-3 rounded-md cursor-pointer mb-0.5 transition-colors"
                    :class="isActive(item) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                    @click="handleClick(item)"
                >
                    <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0" />
                    <span v-if="!collapsed" class="ml-3 text-[14px] truncate">{{ item.title }}</span>
                </div>

                <!-- 有子菜单 -->
                <details
                    v-else
                    class="mb-0.5"
                    :open="openKeys.includes(item.title)"
                    @toggle="handleMenuToggle(item.title, $event)"
                >
                    <summary
                        class="flex items-center h-[40px] px-3 rounded-md cursor-pointer transition-colors list-none"
                        :class="isActive(item) ? 'text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                    >
                        <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0" />
                        <span v-if="!collapsed" class="ml-3 text-[14px] flex-1 truncate">{{ item.title }}</span>
                        <ChevronDown v-if="!collapsed" :size="14" class="text-gray-400 transition-transform" />
                    </summary>

                    <div v-if="!collapsed" class="ml-4 pl-4 border-l border-gray-100">
                        <div
                            v-for="child in item.children"
                            :key="child.title"
                            class="flex items-center h-[36px] px-3 rounded-md cursor-pointer text-[13px] transition-colors"
                            :class="isChildActive(child) ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'"
                            @click="handleChildClick(child)"
                        >
                            {{ child.title }}
                        </div>
                    </div>
                </details>
            </template>
        </nav>

        <!-- 底部固定区域 -->
        <div class="flex-shrink-0 border-t border-gray-100 px-2 py-2">
            <div
                v-for="item in bottomMenus"
                :key="item.title"
                class="flex items-center h-[40px] px-3 rounded-md cursor-pointer mb-0.5 transition-colors"
                :class="isActive(item) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                @click="handleClick(item)"
            >
                <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0" />
                <span v-if="!collapsed" class="ml-3 text-[14px] truncate">{{ item.title }}</span>
            </div>
            <!-- 折叠按钮 -->
            <div
                v-if="!isMobile"
                class="flex items-center h-[40px] px-3 rounded-md cursor-pointer text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
                @click="appStore.toggleSidebar()"
            >
                <PanelLeftClose v-if="!collapsed" :size="18" class="flex-shrink-0" />
                <PanelLeftOpen v-else :size="18" class="flex-shrink-0" />
                <span v-if="!collapsed" class="ml-3 text-[14px] truncate">收起侧栏</span>
            </div>
        </div>
    </aside>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
details > summary::-webkit-details-marker { display: none; }
details[open] > summary .lucide-chevron-down { transform: rotate(180deg); }
</style>
