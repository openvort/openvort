<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from "vue";
import { useRouter } from "vue-router";
import { useUserStore, useAppStore } from "@/stores";
import { LogOut, User, Menu, RefreshCw, ArrowUpCircle, X, Download, Loader2 } from "lucide-vue-next";
import { getHealthStatus, getUpgradeStreamUrl } from "@/api";
import ActiveTaskIndicator from "@/components/ActiveTaskIndicator.vue";
import NotificationPopover from "./NotificationPopover.vue";

defineProps<{ isScrolled: boolean; isMobile?: boolean }>();

const router = useRouter();
const userStore = useUserStore();
const appStore = useAppStore();

const version = ref("");
const llmHealthy = ref<boolean | null>(null);
const llmError = ref("");
let healthTimer: ReturnType<typeof setInterval> | null = null;

const updateAvailable = ref(false);
const latestVersion = ref("");
const releaseNotes = ref("");

const isAdmin = computed(() => userStore.userInfo.roles.includes("admin"));

const checkVersionUpdate = (serverVersion: string) => {
    if (!serverVersion) return;
    const cachedVersion = localStorage.getItem("app_version");
    if (!cachedVersion) {
        localStorage.setItem("app_version", serverVersion);
        return;
    }
    if (cachedVersion !== serverVersion) {
        localStorage.clear();
        sessionStorage.clear();
        localStorage.setItem("app_version", serverVersion);
        location.reload();
    }
};

const healthChecking = ref(false);

const fetchHealth = async (force = false) => {
    if (force) healthChecking.value = true;
    try {
        const res: any = await getHealthStatus(force);
        version.value = res.version || "";
        llmHealthy.value = res.llm_healthy ?? null;
        llmError.value = res.llm_error || "";
        updateAvailable.value = res.update_available || false;
        latestVersion.value = res.latest_version || "";
        releaseNotes.value = res.release_notes || "";
        checkVersionUpdate(res.version);
    } catch {
        llmHealthy.value = false;
        llmError.value = "无法连接服务器";
    } finally {
        healthChecking.value = false;
    }
};

const handleRefreshHealth = () => {
    if (healthChecking.value) return;
    llmHealthy.value = null;
    fetchHealth(true);
};

onMounted(() => {
    fetchHealth();
    healthTimer = setInterval(fetchHealth, 60_000);
});

onUnmounted(() => {
    if (healthTimer) clearInterval(healthTimer);
});

const handleLogout = () => {
    userStore.logout();
    router.push("/login");
};

const goProfile = () => {
    router.push("/profile");
};

// ---- Upgrade dialog ----
const showUpgradeDialog = ref(false);
const upgradeStep = ref("");
const upgradeMessage = ref("");
const upgradeError = ref("");
const upgradeRunning = ref(false);
const upgradeDone = ref(false);
const upgradePercent = ref<number | null>(null);
const upgradeCurrentStep = ref(0);
const upgradeTotalSteps = ref(0);

const openUpgradeDialog = () => {
    showUpgradeDialog.value = true;
    upgradeStep.value = "";
    upgradeMessage.value = "";
    upgradeError.value = "";
    upgradeRunning.value = false;
    upgradeDone.value = false;
    upgradePercent.value = null;
    upgradeCurrentStep.value = 0;
    upgradeTotalSteps.value = 0;
};

const startUpgrade = () => {
    upgradeRunning.value = true;
    upgradeError.value = "";

    const url = getUpgradeStreamUrl(latestVersion.value, userStore.token);
    fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${userStore.token}`,
        },
        body: JSON.stringify({ version: latestVersion.value }),
    }).then(async (resp) => {
        if (!resp.ok || !resp.body) {
            upgradeError.value = `请求失败 (${resp.status})`;
            upgradeRunning.value = false;
            return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });

            const lines = buf.split("\n");
            buf = lines.pop() || "";

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                try {
                    const ev = JSON.parse(line.slice(6));
                    if (ev.type === "progress") {
                        upgradeStep.value = ev.step || "";
                        upgradeMessage.value = ev.message || "";
                        upgradePercent.value = ev.percent ?? null;
                        upgradeCurrentStep.value = ev.current_step ?? 0;
                        upgradeTotalSteps.value = ev.total_steps ?? 0;
                    } else if (ev.type === "done") {
                        upgradeDone.value = true;
                        upgradeRunning.value = false;
                        upgradeMessage.value = ev.message || "更新完成";
                    } else if (ev.type === "error") {
                        upgradeError.value = ev.message || "升级失败";
                        upgradeRunning.value = false;
                    }
                } catch { /* ignore parse errors */ }
            }
        }
        if (upgradeRunning.value) upgradeRunning.value = false;
    }).catch((err) => {
        upgradeError.value = `连接失败: ${err}`;
        upgradeRunning.value = false;
    });
};

const handleRefresh = () => {
    location.reload();
};

const stepLabel = computed(() => {
    const map: Record<string, string> = {
        backing_up: "备份数据库",
        backed_up: "备份完成",
        fetching: "获取版本信息",
        downloading: "下载后端包",
        downloading_frontend: "下载前端包",
        installing: "安装更新",
        installed: "安装完成",
        updating_frontend: "更新前端",
        frontend_updated: "前端已更新",
        restarting: "重启服务",
        rolling_back: "回滚中",
    };
    return map[upgradeStep.value] || upgradeStep.value;
});
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

            <!-- Update banner -->
            <div
                v-if="updateAvailable && latestVersion"
                class="hidden md:flex items-center gap-2 px-3 py-1 rounded-full text-[12px] transition-colors"
                :class="isAdmin ? 'bg-blue-50 text-blue-600 cursor-pointer hover:bg-blue-100' : 'bg-gray-50 text-gray-500'"
                @click="isAdmin ? openUpgradeDialog() : undefined"
            >
                <ArrowUpCircle :size="14" />
                <span>新版本 {{ latestVersion }} 可用</span>
                <span v-if="isAdmin" class="font-medium">— 点击更新</span>
            </div>
        </div>

        <!-- 右侧 -->
        <div class="flex items-center gap-2 md:gap-4 flex-shrink-0">
            <ActiveTaskIndicator />
        </div>
        <div class="flex items-center gap-2 md:gap-4 flex-shrink-0">
            <!-- 版本号 -->
            <div class="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-50 text-[11px] text-gray-400 font-mono">
                v{{ version || 'dev' }}
            </div>
            <!-- 健康状态 -->
            <div class="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px]"
                :class="llmHealthy === true ? 'bg-green-50 text-green-600' : llmHealthy === false ? 'bg-red-50 text-red-500' : 'bg-gray-50 text-gray-400'"
                :title="llmError || ''">
                <span class="w-1.5 h-1.5 rounded-full inline-block" :class="llmHealthy === true ? 'bg-green-500' : llmHealthy === false ? 'bg-red-400' : 'bg-gray-300'"></span>
                AI {{ llmHealthy === true ? '在线' : llmHealthy === false ? '离线' : '检测中' }}
                <RefreshCw
                    :size="10"
                    class="cursor-pointer hover:opacity-70 transition-opacity ml-0.5"
                    :class="{ 'animate-spin': healthChecking }"
                    @click.stop="handleRefreshHealth"
                />
            </div>
            <!-- 通知 -->
            <NotificationPopover />
            <!-- 用户信息 -->
            <vort-dropdown trigger="click" placement="bottomRight">
                <div class="flex items-center gap-2 cursor-pointer px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors">
                    <img v-if="userStore.userInfo.avatar_url" :src="userStore.userInfo.avatar_url" class="w-[28px] h-[28px] rounded-full object-cover" />
                    <div v-else class="w-[28px] h-[28px] rounded-full bg-blue-600 flex items-center justify-center">
                        <span class="text-white text-xs font-medium">{{ (userStore.userInfo.name || 'U')[0] }}</span>
                    </div>
                    <span class="hidden sm:inline text-[13px] text-gray-700">{{ userStore.userInfo.name || '用户' }}</span>
                </div>
                <template #overlay>
                    <div class="px-3 py-1.5 text-xs text-gray-400">
                        {{ userStore.userInfo.roles.join(', ') || 'member' }}
                    </div>
                    <vort-dropdown-menu-separator />
                    <vort-dropdown-menu-item @click="goProfile">
                        <User :size="14" /> 个人设置
                    </vort-dropdown-menu-item>
                    <vort-dropdown-menu-separator />
                    <vort-dropdown-menu-item class="text-red-500" @click="handleLogout">
                        <LogOut :size="14" /> 退出登录
                    </vort-dropdown-menu-item>
                </template>
            </vort-dropdown>
        </div>
    </header>

    <!-- Upgrade dialog (teleported to body) -->
    <teleport to="body">
        <transition name="fade">
            <div v-if="showUpgradeDialog" class="fixed inset-0 z-[200] flex items-center justify-center bg-black/40" @click.self="!upgradeRunning && (showUpgradeDialog = false)">
                <div class="bg-white rounded-xl shadow-2xl w-[480px] max-w-[90vw] max-h-[80vh] overflow-hidden">
                    <!-- Header -->
                    <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                        <h3 class="text-[15px] font-semibold text-gray-800">系统更新</h3>
                        <button v-if="!upgradeRunning" class="p-1 rounded hover:bg-gray-100 transition-colors" @click="showUpgradeDialog = false">
                            <X :size="16" class="text-gray-400" />
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
                        <!-- Not started yet -->
                        <template v-if="!upgradeRunning && !upgradeDone && !upgradeError">
                            <div class="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                                <ArrowUpCircle :size="20" class="text-blue-500 flex-shrink-0" />
                                <div>
                                    <div class="text-sm font-medium text-gray-800">v{{ version }} → v{{ latestVersion }}</div>
                                    <div class="text-xs text-gray-500 mt-0.5">更新前将自动备份数据库</div>
                                </div>
                            </div>
                            <div v-if="releaseNotes" class="text-[13px] text-gray-600 leading-relaxed whitespace-pre-wrap bg-gray-50 rounded-lg p-3 max-h-[200px] overflow-y-auto">{{ releaseNotes }}</div>
                            <button
                                class="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
                                @click="startUpgrade"
                            >
                                开始更新
                            </button>
                        </template>

                        <!-- Running -->
                        <template v-if="upgradeRunning">
                            <div class="flex flex-col items-center gap-4 py-6">
                                <Loader2 :size="32" class="text-blue-500 animate-spin" />
                                <div class="text-center">
                                    <div class="text-sm font-medium text-gray-800">
                                        {{ stepLabel || '准备中...' }}
                                        <span v-if="upgradeTotalSteps" class="text-gray-400 font-normal text-xs ml-1">({{ upgradeCurrentStep }}/{{ upgradeTotalSteps }})</span>
                                    </div>
                                    <div class="text-xs text-gray-500 mt-1">{{ upgradeMessage }}</div>
                                </div>
                                <div class="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                                    <div class="bg-blue-500 h-full rounded-full transition-all duration-300"
                                         :class="{ 'animate-pulse': upgradePercent == null }"
                                         :style="{ width: (upgradePercent ?? 15) + '%' }"></div>
                                </div>
                                <p class="text-[11px] text-gray-400">请勿关闭页面或刷新浏览器</p>
                            </div>
                        </template>

                        <!-- Done -->
                        <template v-if="upgradeDone">
                            <div class="flex flex-col items-center gap-4 py-6">
                                <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                                    <ArrowUpCircle :size="24" class="text-green-600" />
                                </div>
                                <div class="text-center">
                                    <div class="text-sm font-medium text-gray-800">{{ upgradeMessage }}</div>
                                    <div class="text-xs text-gray-500 mt-1">刷新页面以加载新版本</div>
                                </div>
                                <button
                                    class="w-full py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                                    @click="handleRefresh"
                                >
                                    <RefreshCw :size="14" /> 刷新页面
                                </button>
                            </div>
                        </template>

                        <!-- Error -->
                        <template v-if="upgradeError && !upgradeRunning">
                            <div class="flex flex-col items-center gap-4 py-6">
                                <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                                    <X :size="24" class="text-red-500" />
                                </div>
                                <div class="text-center">
                                    <div class="text-sm font-medium text-red-600">更新失败</div>
                                    <div class="text-xs text-gray-500 mt-1 max-w-[360px]">{{ upgradeError }}</div>
                                </div>
                                <button
                                    class="w-full py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg transition-colors"
                                    @click="showUpgradeDialog = false"
                                >
                                    关闭
                                </button>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </transition>
    </teleport>
</template>

<style scoped>
.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
