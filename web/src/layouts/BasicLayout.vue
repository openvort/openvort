<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { useAppStore } from "@/stores";
import { useBreakpoint } from "@/hooks";
import Sidebar from "./components/Sidebar.vue";
import Header from "./components/Header.vue";
import PageTabs from "./components/PageTabs.vue";
import Footer from "./components/Footer.vue";

const route = useRoute();
const appStore = useAppStore();
const { isMobile } = useBreakpoint();
const isScrolled = ref(false);
const isFullscreen = computed(() => !!route.meta.fullscreen);

const handleScroll = (e: Event) => {
    const target = e.target as HTMLElement;
    isScrolled.value = target.scrollTop > 0;
};

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

            <!-- 标签页 -->
            <PageTabs />

            <!-- 内容区域 -->
            <div class="flex-1 overflow-auto" @scroll="handleScroll">
                <main :class="isFullscreen ? 'h-full' : 'p-4 md:p-6 min-h-[calc(100vh-160px)]'">
                    <router-view v-slot="{ Component }">
                        <transition name="fade" mode="out-in">
                            <component :is="Component" />
                        </transition>
                    </router-view>
                </main>

                <!-- 页脚 -->
                <Footer v-if="!isFullscreen" />
            </div>
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
