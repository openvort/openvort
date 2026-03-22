<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useUserStore } from "@/stores";
import {
    checkUpgrade, getReleases, getUpgradeStreamUrl,
    getBackups, createBackup, deleteBackup,
    getBackupDownloadUrl, getRestoreStreamUrl,
    getSettings, updateSettings,
} from "@/api";
import { message } from "@/components/vort";
import {
    ArrowUpCircle, Download, Trash2, RotateCcw, Database,
    RefreshCw, Loader2, X, Check, HardDriveDownload, Clock,
    FileText, AlertTriangle,
} from "lucide-vue-next";

const userStore = useUserStore();
const activeTab = ref("upgrade");

// ---- Auto check update setting ----
const autoCheckUpdate = ref(true);
const autoCheckReady = ref(false);
const savingAutoCheck = ref(false);

async function loadAutoCheckSetting() {
    try {
        const data = await getSettings() as any;
        autoCheckUpdate.value = data.auto_check_update !== false;
    } catch { /* ignore */ }
    autoCheckReady.value = true;
}

function normalizeSwitchValue(next: unknown, fallback: boolean): boolean {
    if (typeof next === "boolean") return next;
    if (next === 1 || next === "1" || next === "true") return true;
    if (next === 0 || next === "0" || next === "false" || next === null || next === undefined) return false;
    return fallback;
}

async function handleAutoCheckUpdate(next: unknown) {
    if (!autoCheckReady.value || savingAutoCheck.value) return;
    const nextValue = normalizeSwitchValue(next, !autoCheckUpdate.value);
    const oldValue = autoCheckUpdate.value;
    autoCheckUpdate.value = nextValue;
    savingAutoCheck.value = true;
    try {
        await updateSettings({ auto_check_update: nextValue });
        // Re-sync from backend to avoid stale UI state.
        await loadAutoCheckSetting();
    } catch {
        autoCheckUpdate.value = oldValue;
        message.error("保存失败");
    } finally {
        savingAutoCheck.value = false;
    }
}

// ---- Upgrade tab state ----
const updateInfo = ref<any>({});
const releases = ref<any[]>([]);
const loadingUpdate = ref(false);
const loadingReleases = ref(false);

async function loadUpdateInfo(force = false) {
    loadingUpdate.value = true;
    try {
        updateInfo.value = await checkUpgrade(force);
    } catch { /* ignore */ }
    finally { loadingUpdate.value = false; }
}

async function loadReleases() {
    loadingReleases.value = true;
    try {
        releases.value = (await getReleases(30)) as any[] || [];
    } catch { /* ignore */ }
    finally { loadingReleases.value = false; }
}

// ---- Backup tab state ----
const backups = ref<any[]>([]);
const loadingBackups = ref(false);
const creatingBackup = ref(false);

async function loadBackups() {
    loadingBackups.value = true;
    try {
        backups.value = (await getBackups()) as any[] || [];
    } catch { /* ignore */ }
    finally { loadingBackups.value = false; }
}

async function handleCreateBackup() {
    creatingBackup.value = true;
    try {
        await createBackup();
        message.success("备份创建成功");
        await loadBackups();
    } catch {
        message.error("备份创建失败");
    } finally {
        creatingBackup.value = false;
    }
}

function handleDownloadBackup(filename: string) {
    const url = getBackupDownloadUrl(filename, userStore.token);
    window.open(url, "_blank");
}

const deletingBackup = ref("");
async function handleDeleteBackup(filename: string) {
    deletingBackup.value = filename;
    try {
        await deleteBackup(filename);
        message.success("备份已删除");
        backups.value = backups.value.filter(b => b.filename !== filename);
    } catch {
        message.error("删除失败");
    } finally {
        deletingBackup.value = "";
    }
}

// ---- Upgrade / Rollback dialog (SSE) ----
const sseDialog = ref(false);
const sseTitle = ref("");
const sseStep = ref("");
const sseMessage = ref("");
const sseError = ref("");
const sseRunning = ref(false);
const sseDone = ref(false);

function resetSseDialog() {
    sseStep.value = "";
    sseMessage.value = "";
    sseError.value = "";
    sseRunning.value = false;
    sseDone.value = false;
}

function startUpgradeOrRollback(version: string, isRollback = false) {
    sseDialog.value = true;
    sseTitle.value = isRollback ? `回退到 v${version}` : `升级到 v${version}`;
    resetSseDialog();
    sseRunning.value = true;

    const url = getUpgradeStreamUrl(version, userStore.token);
    fetch(url, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${userStore.token}`,
        },
        body: JSON.stringify({ version }),
    }).then(async (resp) => {
        if (!resp.ok || !resp.body) {
            sseError.value = `请求失败 (${resp.status})`;
            sseRunning.value = false;
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
                        sseStep.value = ev.step || "";
                        sseMessage.value = ev.message || "";
                    } else if (ev.type === "done") {
                        sseDone.value = true;
                        sseRunning.value = false;
                        sseMessage.value = ev.message || "操作完成";
                    } else if (ev.type === "error") {
                        sseError.value = ev.message || "操作失败";
                        sseRunning.value = false;
                    }
                } catch { /* ignore */ }
            }
        }
        if (sseRunning.value) sseRunning.value = false;
    }).catch((err) => {
        sseError.value = `连接失败: ${err}`;
        sseRunning.value = false;
    });
}

// ---- Restore dialog ----
function startRestore(filename: string) {
    sseDialog.value = true;
    sseTitle.value = `恢复备份: ${filename}`;
    resetSseDialog();
    sseRunning.value = true;

    const url = getRestoreStreamUrl(filename, userStore.token);
    fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${userStore.token}` },
    }).then(async (resp) => {
        if (!resp.ok || !resp.body) {
            sseError.value = `请求失败 (${resp.status})`;
            sseRunning.value = false;
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
                        sseStep.value = ev.step || "";
                        sseMessage.value = ev.message || "";
                    } else if (ev.type === "done") {
                        sseDone.value = true;
                        sseRunning.value = false;
                        sseMessage.value = ev.message || "恢复完成";
                    } else if (ev.type === "error") {
                        sseError.value = ev.message || "恢复失败";
                        sseRunning.value = false;
                    }
                } catch { /* ignore */ }
            }
        }
        if (sseRunning.value) sseRunning.value = false;
    }).catch((err) => {
        sseError.value = `连接失败: ${err}`;
        sseRunning.value = false;
    });
}

const confirmRestore = ref("");
function askRestore(filename: string) {
    confirmRestore.value = filename;
}
function doRestore() {
    const f = confirmRestore.value;
    confirmRestore.value = "";
    startRestore(f);
}

const confirmDelete = ref("");
function askDelete(filename: string) {
    confirmDelete.value = filename;
}
function doDelete() {
    const f = confirmDelete.value;
    confirmDelete.value = "";
    handleDeleteBackup(f);
}

// ---- Helpers ----
const stepLabels: Record<string, string> = {
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
    restoring: "恢复数据库",
};

function formatSize(bytes: number) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function formatDate(iso: string) {
    if (!iso) return "-";
    try {
        return new Date(iso).toLocaleString("zh-CN");
    } catch { return iso; }
}

onMounted(() => {
    loadAutoCheckSetting();
    loadUpdateInfo();
    loadReleases();
    loadBackups();
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-base font-medium text-gray-800">系统升级与备份</h3>
            </div>

            <VortTabs v-model:activeKey="activeTab">
                <!-- ================ Tab 1: System Upgrade ================ -->
                <VortTabPane tab-key="upgrade" tab="系统升级">
                    <div class="mt-4 space-y-6">
                        <!-- Current version & update info -->
                        <div class="flex items-start gap-4 p-4 rounded-lg" :class="updateInfo.update_available ? 'bg-blue-50' : 'bg-gray-50'">
                            <ArrowUpCircle :size="24" :class="updateInfo.update_available ? 'text-blue-500' : 'text-gray-400'" class="mt-0.5 flex-shrink-0" />
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-3 flex-wrap">
                                    <span class="text-sm font-medium text-gray-800">当前版本: v{{ updateInfo.current_version || '-' }}</span>
                                    <span v-if="updateInfo.update_available" class="text-sm text-blue-600 font-medium">
                                        → v{{ updateInfo.latest_version }} 可用
                                    </span>
                                    <span v-else-if="updateInfo.latest_version" class="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full">已是最新</span>
                                </div>
                                <div v-if="updateInfo.release_notes && updateInfo.update_available" class="mt-2 text-xs text-gray-500 whitespace-pre-wrap line-clamp-3">
                                    {{ updateInfo.release_notes }}
                                </div>
                            </div>
                            <div class="flex items-center gap-2 flex-shrink-0">
                                <VortButton size="small" @click="loadUpdateInfo(true)" :loading="loadingUpdate">
                                    <RefreshCw :size="12" class="mr-1" /> 检查更新
                                </VortButton>
                                <VortButton v-if="updateInfo.update_available" type="primary" size="small"
                                    @click="startUpgradeOrRollback(updateInfo.latest_version)">
                                    <HardDriveDownload :size="12" class="mr-1" /> 升级
                                </VortButton>
                            </div>
                        </div>

                        <!-- Auto check update status -->
                        <div class="flex items-center justify-between px-4 py-3 bg-gray-50 rounded-lg">
                            <div>
                                <div class="text-sm font-medium text-gray-700">自动检查更新</div>
                                <div class="text-xs text-gray-400 mt-0.5">开启后系统会定期检查新版本，关闭可避免 GitHub API 频率限制</div>
                            </div>
                            <div class="flex items-center gap-3">
                                <span
                                    class="text-xs px-2 py-0.5 rounded-full font-medium"
                                    :class="!autoCheckReady
                                        ? 'bg-blue-100 text-blue-600'
                                        : autoCheckUpdate
                                            ? 'bg-green-100 text-green-700'
                                            : 'bg-gray-200 text-gray-600'"
                                >
                                    {{ !autoCheckReady ? "加载中" : autoCheckUpdate ? "已开启" : "已关闭" }}
                                </span>
                                <VortButton
                                    size="small"
                                    :loading="savingAutoCheck"
                                    :disabled="!autoCheckReady || savingAutoCheck"
                                    @click="handleAutoCheckUpdate(!autoCheckUpdate)"
                                >
                                    {{ !autoCheckReady ? "请稍候" : autoCheckUpdate ? "关闭" : "开启" }}
                                </VortButton>
                            </div>
                        </div>

                        <!-- Releases list -->
                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="text-sm font-medium text-gray-700">历史版本</h4>
                                <VortButton size="small" @click="loadReleases" :loading="loadingReleases">
                                    <RefreshCw :size="12" class="mr-1" /> 刷新
                                </VortButton>
                            </div>

                            <div v-if="loadingReleases && !releases.length" class="py-8 text-center text-gray-400 text-sm">
                                <Loader2 :size="20" class="animate-spin inline-block mb-2" /><br />加载中...
                            </div>

                            <div v-else-if="!releases.length" class="py-8 text-center text-gray-400 text-sm">
                                暂无版本信息
                            </div>

                            <div v-else class="border border-gray-100 rounded-lg overflow-hidden">
                                <div v-for="(rel, idx) in releases" :key="rel.version"
                                    class="flex items-center gap-4 px-4 py-3 text-sm"
                                    :class="idx !== releases.length - 1 ? 'border-b border-gray-50' : ''"
                                >
                                    <div class="flex items-center gap-2 w-[120px] flex-shrink-0">
                                        <span class="font-mono text-gray-800">v{{ rel.version }}</span>
                                        <span v-if="rel.is_current" class="text-[10px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full">当前</span>
                                    </div>
                                    <div class="flex-1 min-w-0 text-xs text-gray-500 truncate">
                                        {{ rel.release_notes?.split('\n')[0] || '-' }}
                                    </div>
                                    <div class="text-xs text-gray-400 w-[140px] flex-shrink-0 text-right">
                                        {{ formatDate(rel.published_at) }}
                                    </div>
                                    <div class="w-[80px] flex-shrink-0 text-right">
                                        <VortButton v-if="!rel.is_current" size="small" @click="startUpgradeOrRollback(rel.version, !rel.is_newer)">
                                            {{ rel.is_newer ? '升级' : '回退' }}
                                        </VortButton>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </VortTabPane>

                <!-- ================ Tab 2: Database Backup ================ -->
                <VortTabPane tab-key="backup" tab="数据库备份">
                    <div class="mt-4 space-y-4">
                        <div class="flex items-center justify-between">
                            <p class="text-xs text-gray-500">备份文件存储在服务器 ~/.openvort/backups/ 目录下。升级前会自动创建备份。</p>
                            <div class="flex items-center gap-2">
                                <VortButton size="small" @click="loadBackups" :loading="loadingBackups">
                                    <RefreshCw :size="12" class="mr-1" /> 刷新
                                </VortButton>
                                <VortButton type="primary" size="small" @click="handleCreateBackup" :loading="creatingBackup">
                                    <Database :size="12" class="mr-1" /> 立即备份
                                </VortButton>
                            </div>
                        </div>

                        <div v-if="loadingBackups && !backups.length" class="py-8 text-center text-gray-400 text-sm">
                            <Loader2 :size="20" class="animate-spin inline-block mb-2" /><br />加载中...
                        </div>

                        <div v-else-if="!backups.length" class="py-8 text-center text-gray-400 text-sm">
                            <Database :size="24" class="inline-block mb-2 opacity-40" /><br />暂无备份
                        </div>

                        <div v-else class="border border-gray-100 rounded-lg overflow-hidden">
                            <div class="grid grid-cols-[1fr_100px_160px_180px] gap-2 px-4 py-2 bg-gray-50 text-xs text-gray-500 font-medium">
                                <span>文件名</span>
                                <span class="text-right">大小</span>
                                <span class="text-right">创建时间</span>
                                <span class="text-right">操作</span>
                            </div>
                            <div v-for="(bk, idx) in backups" :key="bk.filename"
                                class="grid grid-cols-[1fr_100px_160px_180px] gap-2 px-4 py-2.5 text-sm items-center"
                                :class="idx !== backups.length - 1 ? 'border-b border-gray-50' : ''"
                            >
                                <div class="flex items-center gap-2 min-w-0">
                                    <FileText :size="14" class="text-gray-400 flex-shrink-0" />
                                    <span class="font-mono text-xs text-gray-700 truncate">{{ bk.filename }}</span>
                                </div>
                                <span class="text-xs text-gray-500 text-right">{{ formatSize(bk.size) }}</span>
                                <span class="text-xs text-gray-400 text-right">{{ formatDate(bk.created_at) }}</span>
                                <div class="flex items-center justify-end gap-1">
                                    <button class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-blue-600 transition-colors" title="下载" @click="handleDownloadBackup(bk.filename)">
                                        <Download :size="14" />
                                    </button>
                                    <button class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-orange-600 transition-colors" title="恢复" @click="askRestore(bk.filename)">
                                        <RotateCcw :size="14" />
                                    </button>
                                    <button class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-red-500 transition-colors" title="删除" @click="askDelete(bk.filename)">
                                        <Trash2 :size="14" />
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </VortTabPane>
            </VortTabs>
        </div>
    </div>

    <!-- SSE Progress dialog -->
    <teleport to="body">
        <transition name="fade">
            <div v-if="sseDialog" class="fixed inset-0 z-[200] flex items-center justify-center bg-black/40" @click.self="!sseRunning && (sseDialog = false)">
                <div class="bg-white rounded-xl shadow-2xl w-[480px] max-w-[90vw] overflow-hidden">
                    <div class="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                        <h3 class="text-[15px] font-semibold text-gray-800">{{ sseTitle }}</h3>
                        <button v-if="!sseRunning" class="p-1 rounded hover:bg-gray-100 transition-colors" @click="sseDialog = false">
                            <X :size="16" class="text-gray-400" />
                        </button>
                    </div>

                    <div class="px-5 py-6 space-y-4">
                        <!-- Running -->
                        <template v-if="sseRunning">
                            <div class="flex flex-col items-center gap-4 py-4">
                                <Loader2 :size="32" class="text-blue-500 animate-spin" />
                                <div class="text-center">
                                    <div class="text-sm font-medium text-gray-800">{{ stepLabels[sseStep] || '准备中...' }}</div>
                                    <div class="text-xs text-gray-500 mt-1">{{ sseMessage }}</div>
                                </div>
                                <div class="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                                    <div class="bg-blue-500 h-full rounded-full transition-all duration-500 animate-pulse" style="width: 70%"></div>
                                </div>
                                <p class="text-[11px] text-gray-400">请勿关闭页面或刷新浏览器</p>
                            </div>
                        </template>

                        <!-- Done -->
                        <template v-if="sseDone">
                            <div class="flex flex-col items-center gap-4 py-4">
                                <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center">
                                    <Check :size="24" class="text-green-600" />
                                </div>
                                <div class="text-center">
                                    <div class="text-sm font-medium text-gray-800">{{ sseMessage }}</div>
                                    <div class="text-xs text-gray-500 mt-1">刷新页面以加载新版本</div>
                                </div>
                                <button class="w-full py-2.5 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                                    @click="location.reload()">
                                    <RefreshCw :size="14" /> 刷新页面
                                </button>
                            </div>
                        </template>

                        <!-- Error -->
                        <template v-if="sseError && !sseRunning">
                            <div class="flex flex-col items-center gap-4 py-4">
                                <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                                    <X :size="24" class="text-red-500" />
                                </div>
                                <div class="text-center">
                                    <div class="text-sm font-medium text-red-600">操作失败</div>
                                    <div class="text-xs text-gray-500 mt-1 max-w-[360px] break-all">{{ sseError }}</div>
                                </div>
                                <button class="w-full py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 text-sm font-medium rounded-lg transition-colors"
                                    @click="sseDialog = false">
                                    关闭
                                </button>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </transition>

        <!-- Confirm restore dialog -->
        <transition name="fade">
            <div v-if="confirmRestore" class="fixed inset-0 z-[210] flex items-center justify-center bg-black/40" @click.self="confirmRestore = ''">
                <div class="bg-white rounded-xl shadow-2xl w-[400px] max-w-[90vw] p-6 space-y-4">
                    <div class="flex items-start gap-3">
                        <AlertTriangle :size="20" class="text-orange-500 mt-0.5 flex-shrink-0" />
                        <div>
                            <h4 class="text-sm font-semibold text-gray-800">确认恢复数据库？</h4>
                            <p class="text-xs text-gray-500 mt-1">
                                将从备份 <span class="font-mono">{{ confirmRestore }}</span> 恢复数据库。
                                此操作会覆盖当前数据库中的所有数据，建议先创建一个新的备份。
                            </p>
                        </div>
                    </div>
                    <div class="flex justify-end gap-2">
                        <button class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors" @click="confirmRestore = ''">取消</button>
                        <button class="px-4 py-2 text-sm text-white bg-orange-500 hover:bg-orange-600 rounded-lg transition-colors" @click="doRestore">确认恢复</button>
                    </div>
                </div>
            </div>
        </transition>

        <!-- Confirm delete dialog -->
        <transition name="fade">
            <div v-if="confirmDelete" class="fixed inset-0 z-[210] flex items-center justify-center bg-black/40" @click.self="confirmDelete = ''">
                <div class="bg-white rounded-xl shadow-2xl w-[400px] max-w-[90vw] p-6 space-y-4">
                    <div class="flex items-start gap-3">
                        <AlertTriangle :size="20" class="text-red-500 mt-0.5 flex-shrink-0" />
                        <div>
                            <h4 class="text-sm font-semibold text-gray-800">确认删除备份？</h4>
                            <p class="text-xs text-gray-500 mt-1">
                                将永久删除备份文件 <span class="font-mono">{{ confirmDelete }}</span>，此操作不可恢复。
                            </p>
                        </div>
                    </div>
                    <div class="flex justify-end gap-2">
                        <button class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors" @click="confirmDelete = ''">取消</button>
                        <button class="px-4 py-2 text-sm text-white bg-red-500 hover:bg-red-600 rounded-lg transition-colors" @click="doDelete">确认删除</button>
                    </div>
                </div>
            </div>
        </transition>
    </teleport>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
