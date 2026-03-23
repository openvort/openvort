<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { useAppStore, useUserStore } from "@/stores";
import { useBreakpoint } from "@/hooks";
import { initWebSocket, closeWebSocket } from "@/composables/useWebSocket";
import { changePassword } from "@/api";
import { message } from "@/components/vort";
import Sidebar from "./components/Sidebar.vue";
import Header from "./components/Header.vue";
import AiFloat from "@/components/ai-float/AiFloat.vue";

const route = useRoute();
const appStore = useAppStore();
const userStore = useUserStore();
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

watch(isMobile, (val) => {
    if (!val) {
        appStore.closeMobileSidebar();
    }
});

// --- Forced password change ---
const pwdForm = ref({ oldPassword: "", newPassword: "", confirmPassword: "" });
const pwdChanging = ref(false);
const pwdError = ref("");

async function handleForceChangePassword() {
    pwdError.value = "";
    if (!pwdForm.value.oldPassword) { pwdError.value = "请输入当前密码"; return; }
    if (pwdForm.value.newPassword.length < 6) { pwdError.value = "新密码长度不能少于 6 位"; return; }
    if (pwdForm.value.newPassword !== pwdForm.value.confirmPassword) { pwdError.value = "两次输入的新密码不一致"; return; }
    if (pwdForm.value.newPassword === pwdForm.value.oldPassword) { pwdError.value = "新密码不能与当前密码相同"; return; }
    pwdChanging.value = true;
    try {
        const res: any = await changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword);
        if (res?.success) {
            userStore.setMustChangePassword(false);
            pwdForm.value = { oldPassword: "", newPassword: "", confirmPassword: "" };
            message.success("密码修改成功");
        } else {
            pwdError.value = res?.detail || "修改失败";
        }
    } catch (e: any) {
        pwdError.value = e?.response?.data?.detail || "修改失败，请检查当前密码是否正确";
    } finally {
        pwdChanging.value = false;
    }
}
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

        <!-- AI 助手浮标 -->
        <AiFloat />

        <!-- 强制修改密码弹窗 -->
        <VortDialog
            :open="userStore.mustChangePassword"
            title="请修改初始密码"
            width="small"
            :closable="false"
            :mask-closable="false"
            :keyboard="false"
        >
            <p class="text-sm text-gray-500 mb-4">
                您当前使用的是系统分配的初始密码，为保障账号安全，请立即修改密码。
            </p>
            <div class="space-y-3">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">当前密码</label>
                    <VortInputPassword v-model="pwdForm.oldPassword" placeholder="请输入当前密码" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">新密码</label>
                    <VortInputPassword v-model="pwdForm.newPassword" placeholder="至少 6 位" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">确认新密码</label>
                    <VortInputPassword v-model="pwdForm.confirmPassword" placeholder="再次输入新密码" @keyup.enter="handleForceChangePassword" />
                </div>
                <p v-if="pwdError" class="text-xs text-red-500">{{ pwdError }}</p>
            </div>
            <template #footer>
                <VortButton type="primary" :loading="pwdChanging" @click="handleForceChangePassword">
                    确认修改
                </VortButton>
            </template>
        </VortDialog>
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
