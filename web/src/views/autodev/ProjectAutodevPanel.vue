<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import { message } from "@openvort/vort-ui";
import { RefreshCw, Play, Pause, Save, ExternalLink } from "lucide-vue-next";
import {
    getAutodevProject, saveAutodevProject, pauseAutodevProject, resumeAutodevProject,
    getAutodevQueue, syncAutodevProject, dispatchAutodev, getAutodevRuns, getAutodevStats,
    getAutodevGlobal, setAutodevGlobalJob,
} from "@/api";
import type { AutodevProjectConfig, AutodevRun, AutodevQueueItem } from "@/api/autodev";
import { useUserStore } from "@/stores";

const props = defineProps<{ projectId: string }>();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);

const loading = ref(true);
const saving = ref(false);
const busy = ref("");
const config = ref<AutodevProjectConfig | null>(null);
const form = ref<any>(defaultForm());
const queue = ref<AutodevQueueItem[]>([]);
const queueUnmapped = ref(0);
const runs = ref<AutodevRun[]>([]);
const stats = ref<any>(null);
const globalState = ref<any>(null);
const envText = ref("{}");
let timer: number | null = null;

function defaultForm() {
    return {
        repo_path: "", jira_project_key: "", sync_jql: "", sync_window_days: 30,
        sync_first_window_days: 365, sync_max_results: 200,
        deliver: false, enabled: true, hcm_base_url: "", hcm_username: "", hcm_password: "",
    };
}

// 固定参数（镜像 / 模型 / 超时 / 日上限 / 熔断 / 单价 / 状态映射）来自后端 contract，不可改
const fixed = computed<any>(() => globalState.value?.fixed || null);
const master = computed<any>(() => globalState.value?.master || null);

const outcomeColor: Record<string, string> = {
    delivered: "green", verified: "blue", no_change: "default", failed: "red", running: "orange",
};
const outcomeLabel: Record<string, string> = {
    delivered: "已交付", verified: "已验证", no_change: "无改动", failed: "失败", running: "运行中",
};

function fmtTime(s: string | null) {
    if (!s) return "-";
    return s.replace("T", " ").slice(0, 19);
}
function fmtTokens(n: number) {
    if (!n) return "0";
    return n >= 1_000_000 ? `${(n / 1_000_000).toFixed(2)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}
function fmtDuration(ms: number) {
    if (!ms) return "-";
    const m = Math.round(ms / 60000);
    return m >= 60 ? `${Math.floor(m / 60)}h${m % 60}m` : `${m}m`;
}

async function loadAll() {
    loading.value = true;
    try {
        const [cfgRes, globalRes] = await Promise.all([
            getAutodevProject(props.projectId), getAutodevGlobal().catch(() => null),
        ]);
        globalState.value = globalRes;
        config.value = (cfgRes as any).config;
        if (config.value) {
            const c = config.value;
            form.value = {
                repo_path: c.repo_path, jira_project_key: c.jira_project_key,
                sync_jql: c.sync_jql, sync_window_days: c.sync_window_days,
                sync_first_window_days: c.sync_first_window_days, sync_max_results: c.sync_max_results,
                deliver: c.deliver, enabled: c.enabled, hcm_base_url: c.hcm_base_url,
                hcm_username: c.hcm_username, hcm_password: c.hcm_password,
            };
            envText.value = JSON.stringify(c.env || {}, null, 2);
            await refreshLive();
        }
    } catch (e: any) {
        message.error(e?.message || "加载自动交付配置失败");
    } finally {
        loading.value = false;
    }
}

async function refreshLive() {
    if (!config.value) return;
    const [q, r, s] = await Promise.all([
        getAutodevQueue(props.projectId).catch(() => ({ items: [], unmapped_dev_assign: 0 })),
        getAutodevRuns(props.projectId, 50).catch(() => ({ items: [] })),
        getAutodevStats(props.projectId, 7).catch(() => null),
    ]);
    queue.value = (q as any).items || [];
    queueUnmapped.value = (q as any).unmapped_dev_assign || 0;
    runs.value = (r as any).items || [];
    stats.value = s;
}

async function handleSave() {
    let env: Record<string, string> = {};
    try {
        env = envText.value.trim() ? JSON.parse(envText.value) : {};
    } catch {
        message.warning("非密变量必须是合法 JSON 对象");
        return;
    }
    saving.value = true;
    try {
        const res = await saveAutodevProject(props.projectId, { ...form.value, env });
        config.value = (res as any).config;
        message.success("已保存");
        await refreshLive();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || e?.message || "保存失败");
    } finally {
        saving.value = false;
    }
}

async function run(kind: string, fn: () => Promise<any>, okText: (r: any) => string) {
    busy.value = kind;
    try {
        const r: any = await fn();
        message.success(okText(r));
        await loadAll();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || e?.message || `${kind} 失败`);
    } finally {
        busy.value = "";
    }
}

const handleSync = () => run("sync", () => syncAutodevProject(props.projectId),
    (r) => `同步完成：命中 ${r.counts.seen} · 新建 ${r.counts.created} · 状态变更 ${r.counts.state_changed}`);
const handleDispatch = (key = "") => run("dispatch", () => dispatchAutodev(props.projectId, key), (r) => r.text);
const handlePause = () => run("pause", () => pauseAutodevProject(props.projectId), () => "已暂停派发");
const handleResume = () => run("resume", () => resumeAutodevProject(props.projectId), () => "已恢复派发");
const toggleGlobal = (action: "autodev_dispatch" | "autodev_sync", enabled: boolean) =>
    run(action, () => setAutodevGlobalJob(action, enabled), () => (enabled ? "已启用" : "已停用"));

onMounted(() => {
    loadAll();
    timer = window.setInterval(() => { if (config.value) refreshLive(); }, 30000);
});
onBeforeUnmount(() => { if (timer) window.clearInterval(timer); });
</script>

<template>
    <div class="space-y-4">
        <div v-if="loading" class="bg-white rounded-xl p-6 text-sm text-gray-400">加载中…</div>
        <template v-else>
            <!-- 统计 + 操作 -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h4 class="text-sm font-medium text-gray-800">自动交付 · 近 7 天</h4>
                    <div class="flex items-center gap-2">
                        <VortButton size="small" :loading="busy === 'sync'" :disabled="!config || !isAdmin" @click="handleSync">
                            <RefreshCw :size="14" class="mr-1" />同步 Jira
                        </VortButton>
                        <VortButton size="small" variant="primary" :loading="busy === 'dispatch'" :disabled="!config || !isAdmin" @click="handleDispatch()">
                            <Play :size="14" class="mr-1" />立即派发
                        </VortButton>
                        <VortButton v-if="config && !config.paused" size="small" :loading="busy === 'pause'" :disabled="!isAdmin" @click="handlePause">
                            <Pause :size="14" class="mr-1" />暂停
                        </VortButton>
                        <VortButton v-else-if="config" size="small" :loading="busy === 'resume'" :disabled="!isAdmin" @click="handleResume">
                            <Play :size="14" class="mr-1" />恢复
                        </VortButton>
                    </div>
                </div>
                <div v-if="!config" class="text-sm text-gray-400">该项目尚未配置自动交付，先在下方填写并保存。</div>
                <div v-else-if="stats" class="grid grid-cols-2 md:grid-cols-6 gap-3">
                    <div class="rounded-lg bg-gray-50 p-3"><div class="text-xs text-gray-400">队列</div><div class="text-xl font-medium">{{ stats.queue }}</div><div v-if="stats.queue_unmapped" class="text-xs text-orange-500">{{ stats.queue_unmapped }} 张无 Jira 映射</div></div>
                    <div class="rounded-lg bg-gray-50 p-3"><div class="text-xs text-gray-400">运行中</div><div class="text-xl font-medium">{{ stats.running }}</div></div>
                    <div class="rounded-lg bg-gray-50 p-3"><div class="text-xs text-gray-400">已交付单</div><div class="text-xl font-medium">{{ stats.delivered_tickets }}</div><div class="text-xs text-gray-400">共 {{ stats.runs }} 次运行</div></div>
                    <div class="rounded-lg bg-gray-50 p-3"><div class="text-xs text-gray-400">token</div><div class="text-xl font-medium">{{ fmtTokens(stats.total_tokens) }}</div></div>
                    <div class="rounded-lg bg-gray-50 p-3"><div class="text-xs text-gray-400">费用</div><div class="text-xl font-medium">{{ stats.priced ? `¥${stats.cost}` : '未配单价' }}</div></div>
                    <div class="rounded-lg bg-gray-50 p-3"><div class="text-xs text-gray-400">闸门</div><div class="text-sm font-medium" :class="stats.gate?.allowed ? 'text-green-600' : 'text-orange-600'">{{ stats.gate?.allowed ? `可派 ${stats.gate.allowed}` : (stats.gate?.reason || '-') }}</div></div>
                </div>
                <div v-if="globalState" class="mt-4 flex flex-wrap items-center gap-4 text-xs text-gray-500">
                    <span>全局任务：</span>
                    <template v-for="a in ['autodev_sync', 'autodev_dispatch']" :key="a">
                        <span class="flex items-center gap-2">
                            {{ a === 'autodev_sync' ? 'Jira 同步' : '派发' }}
                            <VortTag :color="globalState.jobs?.[a]?.enabled ? 'green' : 'default'" size="small">
                                {{ globalState.jobs?.[a] ? (globalState.jobs[a].enabled ? `每 ${globalState.jobs[a].schedule}s` : '已停用') : '未创建' }}
                            </VortTag>
                            <a v-if="isAdmin" class="text-blue-600 cursor-pointer" @click="toggleGlobal(a as any, !(globalState.jobs?.[a]?.enabled))">
                                {{ globalState.jobs?.[a]?.enabled ? '停用' : '启用' }}
                            </a>
                            <span v-if="globalState.jobs?.[a]?.last_run_at" class="text-gray-400">上次 {{ fmtTime(globalState.jobs[a].last_run_at) }} · {{ globalState.jobs[a].last_status }}</span>
                        </span>
                    </template>
                    <span v-if="!globalState.ai_member_id" class="text-orange-500">未配置全局 AI 员工（系统设置 → 插件 → AutoDev）</span>
                    <span v-else-if="master?.error" class="text-orange-500">master：{{ master.error }}</span>
                    <span v-else-if="master" class="text-gray-400">master {{ master.name }} · slot {{ master.max_slots }}</span>
                </div>
            </div>

            <!-- 队列 -->
            <div v-if="config" class="bg-white rounded-xl p-6">
                <h4 class="text-sm font-medium text-gray-800 mb-3">派发队列 <span class="text-xs text-gray-400 font-normal">dev_assign · 指派给 AI 员工 · 有 Jira 映射</span></h4>
                <div v-if="queue.length === 0" class="text-sm text-gray-400">队列为空。把已同步的需求指派给 AI 员工并置为「已分配」即进入队列。</div>
                <vort-table v-else :data-source="queue" :pagination="false" size="small">
                    <vort-table-column label="工单" prop="key" :width="130" />
                    <vort-table-column label="标题" :min-width="240"><template #default="{ row }"><span class="line-clamp-1">{{ row.title }}</span></template></vort-table-column>
                    <vort-table-column label="优先级" prop="priority" :width="80" />
                    <vort-table-column label="状态" :width="100"><template #default="{ row }"><vort-tag :color="row.running ? 'orange' : 'default'" size="small">{{ row.running ? '运行中' : '待派' }}</vort-tag></template></vort-table-column>
                    <vort-table-column label="操作" :width="100"><template #default="{ row }"><a v-if="isAdmin && !row.running" class="text-blue-600 cursor-pointer text-sm" @click="handleDispatch(row.key)">派发</a></template></vort-table-column>
                </vort-table>
            </div>

            <!-- 运行记录 -->
            <div v-if="config" class="bg-white rounded-xl p-6">
                <h4 class="text-sm font-medium text-gray-800 mb-3">运行记录</h4>
                <div v-if="runs.length === 0" class="text-sm text-gray-400">还没有运行记录。</div>
                <vort-table v-else :data-source="runs" :pagination="false" size="small">
                    <vort-table-column label="工单" prop="issue_key" :width="120" />
                    <vort-table-column label="结果" :width="100"><template #default="{ row }"><vort-tag :color="outcomeColor[row.status === 'running' ? 'running' : row.outcome] || 'default'" size="small">{{ outcomeLabel[row.status === 'running' ? 'running' : row.outcome] || row.outcome || row.status }}</vort-tag></template></vort-table-column>
                    <vort-table-column label="退出码" :min-width="220"><template #default="{ row }"><span class="text-xs text-gray-600">{{ row.exit_code ?? '-' }} · {{ row.exit_meaning }}</span><div v-if="row.error" class="text-xs text-orange-500 line-clamp-1">{{ row.error }}</div></template></vort-table-column>
                    <vort-table-column label="MR" :width="70"><template #default="{ row }"><a v-if="row.mr_url" :href="row.mr_url" target="_blank" class="text-blue-600"><ExternalLink :size="14" /></a><span v-else class="text-gray-300">-</span></template></vort-table-column>
                    <vort-table-column label="token" :width="110"><template #default="{ row }"><span class="text-xs">{{ fmtTokens(row.input_tokens) }} / {{ fmtTokens(row.output_tokens) }}</span></template></vort-table-column>
                    <vort-table-column label="费用" :width="80"><template #default="{ row }"><span class="text-xs">{{ row.cost ? `¥${row.cost}` : '-' }}</span></template></vort-table-column>
                    <vort-table-column label="耗时" :width="70"><template #default="{ row }"><span class="text-xs">{{ fmtDuration(row.duration_ms) }}</span></template></vort-table-column>
                    <vort-table-column label="触发" prop="trigger" :width="80" />
                    <vort-table-column label="开始" :width="150"><template #default="{ row }"><span class="text-xs text-gray-500">{{ fmtTime(row.started_at) }}</span></template></vort-table-column>
                </vort-table>
            </div>

            <!-- 配置 -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h4 class="text-sm font-medium text-gray-800">配置</h4>
                    <VortButton size="small" variant="primary" :loading="saving" :disabled="!isAdmin" @click="handleSave"><Save :size="14" class="mr-1" />保存</VortButton>
                </div>
                <div class="grid grid-cols-1 lg:grid-cols-2 gap-x-8">
                    <VortForm layout="vertical">
                        <VortFormItem label="交付仓路径" required>
                            <VortInput v-model="form.repo_path" placeholder="/data/autodev/repos/cpic" />
                            <div class="text-xs text-gray-400 mt-1">宿主绝对路径，主仓不是 worktree</div>
                        </VortFormItem>
                        <VortFormItem label="Jira 项目 key" required><VortInput v-model="form.jira_project_key" placeholder="TPYBX" /></VortFormItem>
                        <VortFormItem label="同步 JQL">
                            <VortInput v-model="form.sync_jql" placeholder="留空 = updated >= -窗口 天" />
                        </VortFormItem>
                        <div class="grid grid-cols-3 gap-3">
                            <VortFormItem label="增量窗口(天)"><VortInput v-model.number="form.sync_window_days" /></VortFormItem>
                            <VortFormItem label="首次窗口(天)"><VortInput v-model.number="form.sync_first_window_days" /></VortFormItem>
                            <VortFormItem label="每次最多"><VortInput v-model.number="form.sync_max_results" /></VortFormItem>
                        </div>
                    </VortForm>
                    <VortForm layout="vertical">
                        <div class="grid grid-cols-2 gap-3">
                            <VortFormItem label="真交付">
                                <VortSwitch v-model:checked="form.deliver" />
                                <div class="text-xs text-gray-400 mt-1">推分支 / 开 MR / 回写 Jira</div>
                            </VortFormItem>
                            <VortFormItem label="启用派发">
                                <VortSwitch v-model:checked="form.enabled" />
                                <div class="text-xs text-gray-400 mt-1">关掉即退出全局轮转</div>
                            </VortFormItem>
                        </div>
                        <VortFormItem label="平台地址">
                            <VortInput v-model="form.hcm_base_url" placeholder="HCM_BASE_URL" />
                        </VortFormItem>
                        <div class="grid grid-cols-2 gap-3">
                            <VortFormItem label="系统用户"><VortInput v-model="form.hcm_username" /></VortFormItem>
                            <VortFormItem label="密码">
                                <VortInput v-model="form.hcm_password" type="password" />
                                <div class="text-xs text-gray-400 mt-1">**** 开头 = 不修改</div>
                            </VortFormItem>
                        </div>
                        <VortFormItem label="非密环境变量">
                            <VortTextarea v-model="envText" :rows="3" />
                            <div class="text-xs text-gray-400 mt-1">JSON；含 TOKEN / SECRET / PASSWORD 的键会被拒绝</div>
                        </VortFormItem>
                    </VortForm>
                </div>

                <!-- 固定参数：部署级常量，只读 -->
                <div v-if="fixed" class="mt-4 border-t pt-4">
                    <div class="text-xs text-gray-400 mb-2">固定参数（部署级常量，改需动 contract.py + 服务器 build/v4）</div>
                    <div class="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-600">
                        <span>镜像 {{ fixed.worker_image }}</span>
                        <span>模型 {{ fixed.model }}</span>
                        <span>超时 {{ Math.round(fixed.timeout_seconds / 3600) }}h</span>
                        <span>日上限 {{ fixed.daily_cap }}</span>
                        <span>熔断 {{ fixed.failure_threshold }} 连败</span>
                        <span>单价 {{ fixed.price_in_per_m === null ? '未定价' : `¥${fixed.price_in_per_m} / ¥${fixed.price_out_per_m} 每百万 token` }}</span>
                        <span>状态映射 {{ Object.entries(fixed.status_map).map(([k, v]) => `${k}→${v}`).join('、') }}</span>
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>
