<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useTabsStore } from "@/stores";
import { X } from "lucide-vue-next";

const route = useRoute();
const router = useRouter();
const tabsStore = useTabsStore();

// 右键菜单状态
const contextMenu = ref({ visible: false, x: 0, y: 0, path: "", closable: false });

// 监听路由变化，自动添加标签
watch(() => route.path, () => {
    if (route.name && route.name !== "login") {
        tabsStore.addTab(route);
    }
}, { immediate: true });

const handleTabClick = (path: string) => {
    router.push(path);
};

const handleTabClose = (path: string, e: Event) => {
    e.stopPropagation();
    tabsStore.removeTab(path);
    if (tabsStore.activeTab !== route.path) {
        router.push(tabsStore.activeTab);
    }
};

// 右键菜单
const handleContextMenu = (e: MouseEvent, path: string, closable: boolean) => {
    e.preventDefault();
    contextMenu.value = { visible: true, x: e.clientX, y: e.clientY, path, closable };

    // 点击其他地方关闭
    const close = () => {
        contextMenu.value.visible = false;
        document.removeEventListener("click", close);
    };
    nextTick(() => document.addEventListener("click", close));
};

const closeCurrentTab = () => {
    const { path } = contextMenu.value;
    contextMenu.value.visible = false;
    tabsStore.removeTab(path);
    if (tabsStore.activeTab !== route.path) {
        router.push(tabsStore.activeTab);
    }
};

const closeOtherTabs = () => {
    const { path } = contextMenu.value;
    contextMenu.value.visible = false;
    tabsStore.removeOtherTabs(path);
    if (route.path !== path) {
        router.push(path);
    }
};

const closeRightTabs = () => {
    const { path } = contextMenu.value;
    contextMenu.value.visible = false;
    const idx = tabsStore.tabs.findIndex((t) => t.path === path);
    if (idx === -1) return;
    // 保留当前及左侧所有 + 不可关闭的
    tabsStore.tabs.splice(idx + 1).forEach(() => {});
    const remaining = tabsStore.tabs.map((t) => t.path);
    if (!remaining.includes(route.path)) {
        router.push(path);
    }
    tabsStore.activeTab = remaining.includes(tabsStore.activeTab) ? tabsStore.activeTab : path;
};

const closeAllTabs = () => {
    contextMenu.value.visible = false;
    tabsStore.removeAllTabs();
    router.push(tabsStore.activeTab);
};
</script>

<template>
    <div class="flex items-center h-[40px] bg-white border-b border-gray-100 px-4 gap-1 flex-shrink-0 overflow-x-auto">
        <div
            v-for="tab in tabsStore.tabs"
            :key="tab.path"
            class="flex items-center h-[28px] px-3 rounded-md text-[12px] cursor-pointer whitespace-nowrap transition-colors gap-1 flex-shrink-0"
            :class="tabsStore.activeTab === tab.path ? 'bg-blue-50 text-blue-600' : 'text-gray-500 hover:bg-gray-50'"
            @click="handleTabClick(tab.path)"
            @contextmenu="handleContextMenu($event, tab.path, tab.closable)"
        >
            <span>{{ tab.title }}</span>
            <X
                v-if="tab.closable"
                :size="12"
                class="ml-1 hover:text-red-500 transition-colors"
                @click="handleTabClose(tab.path, $event)"
            />
        </div>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
        <div
            v-if="contextMenu.visible"
            class="fixed z-[9999] bg-white rounded-lg shadow-lg border border-gray-100 py-1 min-w-[140px]"
            :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        >
            <div
                v-if="contextMenu.closable"
                class="px-3 py-2 text-[13px] text-gray-600 hover:bg-gray-50 cursor-pointer"
                @click="closeCurrentTab"
            >关闭当前</div>
            <div
                class="px-3 py-2 text-[13px] text-gray-600 hover:bg-gray-50 cursor-pointer"
                @click="closeOtherTabs"
            >关闭其它</div>
            <div
                class="px-3 py-2 text-[13px] text-gray-600 hover:bg-gray-50 cursor-pointer"
                @click="closeRightTabs"
            >关闭右侧</div>
            <div class="border-t border-gray-100 my-0.5"></div>
            <div
                class="px-3 py-2 text-[13px] text-gray-600 hover:bg-gray-50 cursor-pointer"
                @click="closeAllTabs"
            >关闭全部</div>
        </div>
    </Teleport>
</template>
