<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { useAppStore } from "@/stores";
import { useBreakpoint } from "@/hooks";
import { initWebSocket, closeWebSocket } from "@/composables/useWebSocket";
import Sidebar from "./components/Sidebar.vue";
import Header from "./components/Header.vue";

const route = useRoute();
const appStore = useAppStore();
const { isMobile } = useBreakpoint();

onMounted(() => { initWebSocket(); });
onUnmounted(() => { closeWebSocket(); });
const isScrolled = ref(false);
type LayoutScrollbarRef = {
    setScrollTop?: (value: number) => void;
};
const contentRef = ref<LayoutScrollbarRef | null>(null);

const handleScroll = ({ scrollTop }: { scrollTop: number; scrollLeft: number }) => {
    isScrolled.value = scrollTop > 0;
};

watch(() => route.path, () => {
    contentRef.value?.setScrollTop?.(0);
    isScrolled.value = false;
});

// 切换到桌面端时自动关闭移动端侧边栏
watch(isMobile, (val) => {
    if (!val) {
        appStore.closeMobileSidebar();
    }
});
</script>

<template>
    <div class="flex h-screen overflow-hidden bg-gray-50">
        <!-- 移动端遮罩层 -->
        <transition name="overlay-fade">
            <div
                v-if="isMobile && appStore.mobileSidebarOpen"
                class="fixed inset-0 bg-black/50 z-40"
                @click="appStore.closeMobileSidebar()"
            />
        </transition>

        <!-- 侧边栏 -->
        <Sidebar :is-mobile="isMobile" />

        <!-- 右侧主区域 -->
        <div class="flex flex-col flex-1 overflow-hidden">
            <!-- 顶部栏 -->
            <Header :is-scrolled="isScrolled" :is-mobile="isMobile" />
            <!-- 内容区域 -->
            <VortScrollbar ref="contentRef" class="flex-1" tag="main" view-class="h-full" @scroll="handleScroll">
                <router-view v-slot="{ Component, route: currentRoute }">
                    <transition name="fade" mode="out-in">
                        <div :key="currentRoute.path" :class="currentRoute.meta.fullscreen ? 'h-full' : 'p-4 md:p-6 min-h-[calc(100vh-160px)]'">
                            <component :is="Component" />
                        </div>
                    </transition>
                </router-view>
            </VortScrollbar>
        </div>
    </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
    transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
    opacity: 0;
}
.overlay-fade-enter-active,
.overlay-fade-leave-active {
    transition: opacity 0.3s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
    opacity: 0;
}
</style>
