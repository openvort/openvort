<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAppStore, useUserStore, usePluginStore, useNotificationStore } from "@/stores";
import { menuConfig, type MenuConfig } from "@/router/menus";
import openvortLogo from "@/assets/brand/openvort-logo.png";
import {
    Home, BarChart2, FileText, FileBarChart, Table, File, AlertTriangle,
    CheckCircle, User, Settings, ChevronDown, PanelLeftClose, PanelLeftOpen,
    MessageSquare, Puzzle, Radio, Users, Clock, BookOpen, Webhook, GitBranch, Cpu,
    Kanban, LayoutDashboard, ListChecks, CheckSquare, Bug,
    Wrench, FolderGit2, Server, Shield, Sparkles, Library, Bot, Store, Bell,
    BookMarked, ExternalLink, HardDrive, ClipboardCheck
} from "lucide-vue-next";

const props = defineProps<{ isMobile?: boolean }>();

const route = useRoute();
const router = useRouter();
const appStore = useAppStore();
const userStore = useUserStore();
const pluginStore = usePluginStore();
const notificationStore = useNotificationStore();
const SUBMENU_STATE_KEY = "openvort.sidebar.open-submenus";
const expandedMenus = ref<string[]>([]);
const popupItem = ref<MenuConfig | null>(null);
const popupStyle = ref<Record<string, string>>({});
const popupVisible = ref(false);

const collapsed = computed(() => props.isMobile ? false : appStore.sidebarCollapsed);
const collapseProgress = ref(collapsed.value ? 0 : 1);
let rafId: number | null = null;
let popupCloseTimer: number | null = null;

watch(collapsed, (newVal) => {
    if (rafId) cancelAnimationFrame(rafId);
    const start = collapseProgress.value;
    const end = newVal ? 0 : 1;
    const duration = 300;
    const startTime = performance.now();

    const animate = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        collapseProgress.value = start + (end - start) * eased;
        if (progress < 1) {
            rafId = requestAnimationFrame(animate);
        }
    };
    rafId = requestAnimationFrame(animate);
});

onUnmounted(() => {
    if (rafId) cancelAnimationFrame(rafId);
    if (popupCloseTimer) window.clearTimeout(popupCloseTimer);
});

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
    "check-square": CheckSquare, bug: Bug,
    wrench: Wrench, "folder-git-2": FolderGit2, server: Server, shield: Shield,
    sparkles: Sparkles, library: Library, bot: Bot, store: Store, bell: Bell,
    "book-marked": BookMarked, "external-link": ExternalLink, "hard-drive": HardDrive,
    "clipboard-check": ClipboardCheck,
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

const topMenus = computed(() => allMenus.value.filter(m => m.position === "top"));
const filteredMenus = computed(() => allMenus.value.filter(m => !m.position));
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
    if (item.externalUrl) {
        window.open(item.externalUrl, "_blank", "noopener,noreferrer");
        return;
    }
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

const clearPopupTimer = () => {
    if (popupCloseTimer) {
        window.clearTimeout(popupCloseTimer);
        popupCloseTimer = null;
    }
};

const closePopup = () => {
    popupVisible.value = false;
    popupItem.value = null;
};

const handleCollapsedMenuEnter = (item: MenuConfig, event: MouseEvent) => {
    if (!collapsed.value || props.isMobile || !item.children?.length) return;
    clearPopupTimer();
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    popupItem.value = item;
    popupStyle.value = {
        top: `${Math.max(rect.top, 8)}px`,
        left: `${rect.right + 8}px`
    };
    popupVisible.value = true;
};

const handleCollapsedMenuLeave = () => {
    if (!collapsed.value || props.isMobile) return;
    clearPopupTimer();
    popupCloseTimer = window.setTimeout(() => {
        closePopup();
    }, 120);
};

const handlePopupMouseEnter = () => {
    clearPopupTimer();
};

const handlePopupMouseLeave = () => {
    clearPopupTimer();
    popupCloseTimer = window.setTimeout(() => {
        closePopup();
    }, 100);
};

const handlePopupChildClick = (child: MenuConfig) => {
    handleChildClick(child);
    clearPopupTimer();
    closePopup();
};

const handleCollapsedSummaryClick = (event: MouseEvent) => {
    if (!collapsed.value || props.isMobile) return;
    event.preventDefault();
};

watch([collapsed, () => props.isMobile, () => route.path], () => {
    clearPopupTimer();
    closePopup();
});
</script>

<template>
    <aside
        class="flex flex-col h-full bg-white border-r border-gray-100 flex-shrink-0 transition-transform duration-300"
        :style="{
            '--collapse-progress': collapseProgress,
            width: props.isMobile ? '220px' : `${64 + 156 * collapseProgress}px`
        }"
        :class="[
            props.isMobile ? 'fixed inset-y-0 left-0 z-50' : '',
            props.isMobile && !appStore.mobileSidebarOpen ? '-translate-x-full' : 'translate-x-0'
        ]"
    >
        <!-- Logo -->
        <div class="flex items-center h-[56px] px-4web flex-shrink-0 overflow-hidden ml-3">
            <img :src="openvortLogo" alt="OpenVort" class="h-8 w-auto max-w-none" />
        </div>

        <!-- 顶部固定区域 -->
        <div v-if="topMenus.length" class="flex-shrink-0 border-b border-gray-100 px-2 py-2 overflow-hidden">
            <div
                v-for="item in topMenus"
                :key="item.title"
                class="flex items-center h-[40px] px-3 rounded-md cursor-pointer mb-0.5 transition-colors"
                :class="isActive(item) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                @click="handleClick(item)"
            >
                <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0 relative">
                </component>
                <span v-if="item.path === '/chat' && collapsed && notificationStore.totalUnreadCount > 0"
                    class="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-red-500 border border-white" />
                <span
                    class="ml-3 text-[14px] leading-5 truncate overflow-hidden"
                    :style="{
                        maxWidth: `${140 * collapseProgress}px`,
                        opacity: collapseProgress,
                        transition: 'none'
                    }"
                >{{ item.title }}</span>
                <span v-if="item.path === '/chat' && !collapsed && notificationStore.totalUnreadCount > 0"
                    class="ml-auto flex-shrink-0 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center px-1"
                >{{ notificationStore.totalUnreadCount > 99 ? '99+' : notificationStore.totalUnreadCount }}</span>
            </div>
        </div>

        <!-- 菜单 -->
        <VortScrollbar class="flex-1">
            <nav class="py-2 px-2">
                <template v-for="item in filteredMenus" :key="item.title">
                    <!-- 分组标签 -->
                    <div
                        v-if="item.label"
                        class="overflow-hidden"
                        :style="{
                            maxHeight: `${20 * collapseProgress}px`,
                            marginTop: `${12 * collapseProgress}px`,
                            marginBottom: `${10 * collapseProgress}px`,
                            opacity: collapseProgress,
                            transition: 'none'
                        }"
                    >
                        <span
                            class="px-3 text-[11px] font-medium text-gray-400 uppercase tracking-wider block overflow-hidden"
                            :style="{
                                maxWidth: `${200 * collapseProgress}px`,
                                maxHeight: `${20 * collapseProgress}px`,
                                opacity: collapseProgress,
                                transition: 'none'
                            }"
                        >{{ item.label }}</span>
                    </div>

                    <!-- 无子菜单 -->
                    <div
                        v-if="!item.children"
                        class="flex items-center h-[40px] px-3 rounded-md cursor-pointer mb-0.5 transition-colors"
                        :class="isActive(item) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                        @click="handleClick(item)"
                    >
                        <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0 relative">
                        </component>
                        <span v-if="item.path === '/chat' && collapsed && notificationStore.totalUnreadCount > 0"
                            class="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-red-500 border border-white" />
                        <span
                            class="ml-3 text-[14px] leading-5 truncate overflow-hidden"
                            :style="{
                                maxWidth: `${140 * collapseProgress}px`,
                                opacity: collapseProgress,
                                transition: 'none'
                            }"
                        >{{ item.title }}</span>
                        <span v-if="item.path === '/chat' && !collapsed && notificationStore.totalUnreadCount > 0"
                            class="ml-auto flex-shrink-0 min-w-[18px] h-[18px] rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center px-1"
                        >{{ notificationStore.totalUnreadCount > 99 ? '99+' : notificationStore.totalUnreadCount }}</span>
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
                            @mouseenter="handleCollapsedMenuEnter(item, $event)"
                            @mouseleave="handleCollapsedMenuLeave"
                            @click="handleCollapsedSummaryClick"
                        >
                            <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0" />
                            <span
                                class="ml-3 text-[14px] leading-5 flex-1 truncate overflow-hidden"
                                :style="{
                                    maxWidth: `${100 * collapseProgress}px`,
                                    opacity: collapseProgress,
                                    transition: 'none'
                                }"
                            >{{ item.title }}</span>
                            <ChevronDown
                                :size="14"
                                class="text-gray-400 overflow-hidden"
                                :style="{
                                    maxWidth: `${14 * collapseProgress}px`,
                                    opacity: collapseProgress,
                                    transition: 'none'
                                }"
                            />
                        </summary>

                        <div
                            class="ml-4 pl-4 border-l border-gray-100 overflow-hidden"
                            :style="{
                                maxHeight: `${500 * collapseProgress}px`,
                                opacity: collapseProgress,
                                transition: 'none'
                            }"
                        >
                            <div
                                v-for="child in item.children"
                                :key="child.title"
                                class="flex items-center h-[36px] px-3 rounded-md cursor-pointer text-[13px] transition-colors"
                                :class="isChildActive(child) ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-700'"
                                @click="handleChildClick(child)"
                            >
                                {{ child.title }}
                                <ExternalLink v-if="child.externalUrl" :size="12" class="ml-1 opacity-40" />
                            </div>
                        </div>
                    </details>
                </template>
            </nav>
        </VortScrollbar>

        <!-- 底部固定区域 -->
        <div class="flex-shrink-0 border-t border-gray-100 px-2 py-2 overflow-hidden">
            <div
                v-for="item in bottomMenus"
                :key="item.title"
                class="flex items-center h-[40px] px-3 rounded-md cursor-pointer mb-0.5 transition-colors"
                :class="isActive(item) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                @click="handleClick(item)"
            >
                <component :is="iconMap[item.icon]" v-if="iconMap[item.icon]" :size="18" class="flex-shrink-0" />
                <span
                    class="ml-3 text-[14px] truncate overflow-hidden"
                    :style="{
                        maxWidth: `${140 * collapseProgress}px`,
                        opacity: collapseProgress,
                        transition: 'none'
                    }"
                >{{ item.title }}</span>
            </div>
            <!-- 折叠按钮 -->
            <div
                v-if="!isMobile"
                class="flex items-center h-[40px] px-3 rounded-md cursor-pointer text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
                @click="appStore.toggleSidebar()"
            >
                <div class="relative w-[18px] h-[18px] flex-shrink-0">
                    <PanelLeftClose
                        :size="18"
                        class="absolute inset-0"
                        :style="{ opacity: collapseProgress, transition: 'none' }"
                    />
                    <PanelLeftOpen
                        :size="18"
                        class="absolute inset-0"
                        :style="{ opacity: 1 - collapseProgress, transition: 'none' }"
                    />
                </div>
                <span
                    class="ml-3 text-[14px] truncate overflow-hidden"
                    :style="{
                        maxWidth: `${80 * collapseProgress}px`,
                        opacity: collapseProgress,
                        transition: 'none'
                    }"
                >收起侧栏</span>
            </div>
        </div>

        <Teleport to="body">
            <Transition name="sidebar-popup">
                <div
                    v-if="popupVisible && popupItem?.children?.length"
                    class="fixed z-[70] min-w-[180px] rounded-lg border border-gray-200 bg-white py-2 shadow-lg"
                    :style="popupStyle"
                    @mouseenter="handlePopupMouseEnter"
                    @mouseleave="handlePopupMouseLeave"
                >
                    <div class="px-5 pb-2 text-xs font-medium text-gray-400">
                        {{ popupItem.title }}
                    </div>
                    <div
                        v-for="child in popupItem.children"
                        :key="child.title"
                        class="mx-2 flex h-[36px] items-center rounded-md px-3 text-[13px] cursor-pointer transition-colors"
                        :class="isChildActive(child) ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'"
                        @click="handlePopupChildClick(child)"
                    >
                        {{ child.title }}
                        <ExternalLink v-if="child.externalUrl" :size="12" class="ml-1 opacity-40" />
                    </div>
                </div>
            </Transition>
        </Teleport>
    </aside>
</template>

<style scoped>
details > summary::-webkit-details-marker { display: none; }
details[open] > summary .lucide-chevron-down { transform: rotate(180deg); }
.sidebar-popup-enter-active,
.sidebar-popup-leave-active {
    transition: opacity 0.15s ease, transform 0.15s ease;
}
.sidebar-popup-enter-from,
.sidebar-popup-leave-to {
    opacity: 0;
    transform: translateX(-4px);
}
</style>
