<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { useUserStore, useAppStore } from "@/stores";
import { Bell, Search, LogOut, User, Settings, Menu } from "lucide-vue-next";
import { getHealthStatus } from "@/api";

defineProps<{ isScrolled: boolean; isMobile?: boolean }>();

const router = useRouter();
const userStore = useUserStore();
const appStore = useAppStore();
const showUserMenu = ref(false);

const version = ref("");
const llmHealthy = ref<boolean | null>(null);

const fetchHealth = async () => {
    try {
        const res: any = await getHealthStatus();
        version.value = res.version || "";
        llmHealthy.value = res.llm_healthy ?? null;
    } catch {
        llmHealthy.value = false;
    }
};

onMounted(fetchHealth);

const handleLogout = () => {
    userStore.logout();
    router.push("/login");
};

const goProfile = () => {
    showUserMenu.value = false;
    router.push("/profile");
};
</script>

<template>
    <header
        class="flex items-center justify-between h-[56px] px-4 md:px-6 bg-white border-b border-gray-100 flex-shrink-0 transition-shadow"
        :class="{ 'shadow-sm': isScrolled }"
    >
        <!-- 左侧 -->
        <div class="flex items-center gap-3 flex-1 min-w-0">
            <div
                v-if="isMobile"
                class="flex items-center justify-center w-9 h-9 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors flex-shrink-0"
                @click="appStore.openMobileSidebar()"
            >
                <Menu :size="20" class="text-gray-600" />
            </div>

            <div class="hidden md:flex items-center h-[36px] px-3 bg-gray-50 rounded-lg border border-gray-200 w-[260px]">
                <Search :size="16" class="text-gray-400 mr-2" />
                <input
                    type="text"
                    placeholder="搜索..."
                    class="bg-transparent border-none outline-none text-[13px] text-gray-600 w-full placeholder-gray-400"
                />
            </div>

            <div v-if="isMobile" class="p-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                <Search :size="18" class="text-gray-500" />
            </div>
        </div>

        <!-- 右侧 -->
        <div class="flex items-center gap-2 md:gap-4 flex-shrink-0">
            <!-- 版本号 -->
            <div class="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-50 text-[11px] text-gray-400 font-mono">
                v{{ version || 'dev' }}
            </div>
            <!-- 健康状态 -->
            <div class="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px]"
                :class="llmHealthy === true ? 'bg-green-50 text-green-600' : llmHealthy === false ? 'bg-red-50 text-red-500' : 'bg-gray-50 text-gray-400'">
                <span class="w-1.5 h-1.5 rounded-full inline-block" :class="llmHealthy === true ? 'bg-green-500' : llmHealthy === false ? 'bg-red-400' : 'bg-gray-300'"></span>
                AI {{ llmHealthy === true ? '在线' : llmHealthy === false ? '离线' : '...' }}
            </div>
            <!-- 用户信息 -->
            <div class="relative">
                <div
                    class="flex items-center gap-2 cursor-pointer px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
                    @click="showUserMenu = !showUserMenu"
                >
                    <div class="w-[28px] h-[28px] rounded-full bg-blue-600 flex items-center justify-center">
                        <span class="text-white text-xs font-medium">{{ (userStore.userInfo.name || 'U')[0] }}</span>
                    </div>
                    <span class="hidden sm:inline text-[13px] text-gray-700">{{ userStore.userInfo.name || '用户' }}</span>
                </div>

                <!-- 下拉菜单 -->
                <transition name="dropdown">
                    <div
                        v-if="showUserMenu"
                        class="absolute right-0 top-[44px] w-[160px] bg-white rounded-lg shadow-lg border border-gray-100 py-1 z-50"
                        @mouseleave="showUserMenu = false"
                    >
                        <div class="px-3 py-1.5 text-xs text-gray-400 border-b border-gray-100">
                            {{ userStore.userInfo.roles.join(', ') || 'member' }}
                        </div>
                        <div class="px-3 py-2 text-[13px] text-gray-600 hover:bg-gray-50 cursor-pointer flex items-center gap-2" @click="goProfile">
                            <User :size="14" /> 个人设置
                        </div>
                        <div class="border-t border-gray-100 my-1"></div>
                        <div class="px-3 py-2 text-[13px] text-red-500 hover:bg-red-50 cursor-pointer flex items-center gap-2" @click="handleLogout">
                            <LogOut :size="14" /> 退出登录
                        </div>
                    </div>
                </transition>
            </div>
        </div>
    </header>
</template>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
</style>
