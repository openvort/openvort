<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import {
    getVortgitCodeTasks, getVortgitCodeTask, getVortgitCodeTaskStats,
    getVortgitRepos, getMembers, batchDeleteVortgitCodeTasks,
} from "@/api";
import {
    RefreshCw, ExternalLink, TerminalSquare, Clock, FileCode2,
    CheckCircle2, XCircle, Loader2, AlertCircle,
} from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import { useUserStore } from "@/stores";

interface CodeTask {
    id: string;
    repo_id: string;
    member_id: string;
    story_id: string | null;
    task_id: string | null;
    bug_id: string | null;
    cli_tool: string;
    task_description: string;
    branch_name: string;
    status: string;
    pr_url: string;
    files_changed: string[];
    diff_summary: string;
    duration_seconds: number;
    created_at: string;
    cli_stdout?: string;
    cli_stderr?: string;
}

interface Stats {
    total: number;
    success: number;
    failed: number;
    running: number;
    success_rate: number;
    active_repos: number;
    this_week: number;
}

const router = useRouter();
const userStore = useUserStore();

const tasks = ref<CodeTask[]>([]);
const total = ref(0);
const loading = ref(false);
const stats = ref<Stats | null>(null);

const filterStatus = ref("");
const filterRepo = ref("");
const filterMember = ref("");
const page = ref(1);
const pageSize = ref(20);

const repos = ref<{ id: string; name: string; full_name: string }[]>([]);
const members = ref<{ id: string; name: string }[]>([]);

const selectedRowKeys = ref<string[]>([]);

const drawerOpen = ref(false);
const drawerTask = ref<CodeTask | null>(null);
const drawerLoading = ref(false);
const showStdout = ref(false);

const statusOptions = [
    { value: "", label: "全部状态" },
    { value: "running", label: "执行中" },
    { value: "success", label: "成功" },
    { value: "failed", label: "失败" },
    { value: "review", label: "待审核" },
    { value: "pending", label: "等待中" },
];

const repoOptions = computed(() => [
    { value: "", label: "全部仓库" },
    ...repos.value.map(r => ({ value: r.id, label: r.full_name || r.name })),
]);

const memberOptions = computed(() => [
    { value: "", label: "全部成员" },
    ...members.value.map(m => ({ value: m.id, label: m.name })),
]);

const repoMap = computed(() => {
    const m: Record<string, string> = {};
    for (const r of repos.value) m[r.id] = r.full_name || r.name;
    return m;
});

const memberMap = computed(() => {
    const m: Record<string, string> = {};
    for (const item of members.value) m[item.id] = item.name;
    return m;
});

const isAdmin = computed(() => userStore.isAdmin);

const rowSelection = computed(() => ({
    selectedRowKeys: selectedRowKeys.value,
    onChange: (keys: (string | number)[]) => {
        selectedRowKeys.value = (keys as string[]);
    },
}));

const hasSelection = computed(() => selectedRowKeys.value.length > 0);

async function loadTasks() {
    loading.value = true;
    try {
        const res: any = await getVortgitCodeTasks({
            status: filterStatus.value || undefined,
            repo_id: filterRepo.value || undefined,
            member_id: filterMember.value || undefined,
            page: page.value,
            page_size: pageSize.value,
        });
        tasks.value = res.items || [];
        total.value = res.total || 0;
        selectedRowKeys.value = [];
    } catch {
        tasks.value = [];
    }
    loading.value = false;
}

async function loadStats() {
    try {
        stats.value = await getVortgitCodeTaskStats() as any;
    } catch {
        stats.value = null;
    }
}

async function loadRefs() {
    try {
        const [repoRes, memberRes]: any[] = await Promise.all([
            getVortgitRepos({ page: 1, page_size: 200 }),
            getMembers({ page: 1, size: 500 }),
        ]);
        repos.value = repoRes.items || [];
        members.value = memberRes.items || [];
    } catch { /* noop */ }
}

function handleFilter() {
    page.value = 1;
    loadTasks();
}

function handlePageChange(p: number) {
    page.value = p;
    loadTasks();
}

async function openDetail(task: CodeTask) {
    drawerOpen.value = true;
    drawerLoading.value = true;
    showStdout.value = false;
    try {
        drawerTask.value = await getVortgitCodeTask(task.id) as any;
    } catch {
        drawerTask.value = task;
    }
    drawerLoading.value = false;
}

function goToChat(task: CodeTask) {
    const prompt = `请继续之前的编码任务：${task.task_description}，仓库 ${repoMap.value[task.repo_id] || task.repo_id}`;
    router.push({ name: "chat", query: { prompt } });
}

function statusColor(s: string): string {
    if (s === "success") return "success";
    if (s === "review") return "warning";
    if (s === "failed") return "error";
    if (s === "running") return "processing";
    return "default";
}

function statusLabel(s: string): string {
    return statusOptions.find(o => o.value === s)?.label || s;
}

function cliToolLabel(t: string): string {
    if (t === "claude-code") return "Claude Code";
    if (t === "aider") return "Aider";
    return t;
}

function formatDuration(s: number): string {
    if (!s) return "-";
    if (s < 60) return `${s}秒`;
    return `${Math.floor(s / 60)}分${s % 60}秒`;
}

function formatTime(iso: string | null): string {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("zh-CN"); } catch { return iso; }
}

function truncate(s: string | null | undefined, len: number): string {
    if (!s) return "-";
    return s.length > len ? s.slice(0, len) + "..." : s;
}

function memberLabel(id: string): string {
    const name = memberMap.value[id];
    if (name) return name;
    if (!id) return "-";
    return id.length > 12 ? `${id.slice(0, 6)}...${id.slice(-4)}` : id;
}

function refresh() {
    loadTasks();
    loadStats();
}

async function handleBatchDelete() {
    if (!selectedRowKeys.value.length) return;
    try {
        await batchDeleteVortgitCodeTasks(selectedRowKeys.value);
        message.success("已删除选中的任务");
        await refresh();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "删除失败");
    }
}

onMounted(() => {
    loadRefs();
    refresh();
});
</script>

<template>
    <div class="space-y-4">
        <!-- Stats cards -->
        <div v-if="stats" class="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                    <TerminalSquare :size="20" class="text-blue-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ stats.total }}</div>
                    <div class="text-xs text-gray-400">总任务数</div>
                </div>
            </div>
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                    <CheckCircle2 :size="20" class="text-green-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ stats.success_rate }}%</div>
                    <div class="text-xs text-gray-400">成功率</div>
                </div>
            </div>
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
                    <FileCode2 :size="20" class="text-purple-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ stats.active_repos }}</div>
                    <div class="text-xs text-gray-400">活跃仓库</div>
                </div>
            </div>
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-orange-50 flex items-center justify-center">
                    <Clock :size="20" class="text-orange-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ stats.this_week }}</div>
                    <div class="text-xs text-gray-400">本周任务</div>
                </div>
            </div>
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-yellow-50 flex items-center justify-center">
                    <Loader2 :size="20" class="text-yellow-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ stats.running }}</div>
                    <div class="text-xs text-gray-400">执行中任务</div>
                </div>
            </div>
        </div>

        <!-- List -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center gap-2 flex-wrap">
                    <VortSelect v-model="filterStatus" :options="statusOptions" placeholder="状态" style="width: 120px" @change="handleFilter" />
                    <VortSelect v-model="filterRepo" :options="repoOptions" placeholder="仓库" style="width: 200px" @change="handleFilter" />
                    <VortSelect v-model="filterMember" :options="memberOptions" placeholder="成员" style="width: 140px" @change="handleFilter" />
                </div>
                <VortButton @click="refresh">
                    <RefreshCw :size="14" class="mr-1" /> 刷新
                </VortButton>
            </div>

            <div v-if="isAdmin && hasSelection" class="flex items-center gap-3 mb-4">
                <span class="text-sm text-gray-500">已选 {{ selectedRowKeys.length }} 项</span>
                <VortPopconfirm title="确认批量删除选中的任务？" @confirm="handleBatchDelete">
                    <VortButton size="small">
                        批量删除
                    </VortButton>
                </VortPopconfirm>
                <VortButton size="small" @click="selectedRowKeys = []">取消选择</VortButton>
            </div>

            <VortTable
                :data-source="tasks"
                :loading="loading"
                row-key="id"
                :pagination="false"
                :row-selection="isAdmin ? rowSelection : undefined"
            >
                <VortTableColumn label="触发人" :width="100">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-700">{{ memberLabel(row.member_id) }}</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="仓库" :min-width="140">
                    <template #default="{ row }">
                        <router-link :to="{ name: 'vortgit-repos' }" class="text-blue-600 text-sm hover:underline">
                            {{ repoMap[row.repo_id] || row.repo_id }}
                        </router-link>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="任务描述" :min-width="220">
                    <template #default="{ row }">
                        <a class="text-sm text-gray-800 cursor-pointer hover:text-blue-600" @click="openDetail(row)">
                            {{ truncate(row.task_description, 60) }}
                        </a>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="关联" :width="100">
                    <template #default="{ row }">
                        <VortTag v-if="row.bug_id" color="error" size="small">Bug</VortTag>
                        <VortTag v-else-if="row.task_id" color="blue" size="small">Task</VortTag>
                        <VortTag v-else-if="row.story_id" color="green" size="small">Story</VortTag>
                        <span v-else class="text-xs text-gray-300">-</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="CLI" :width="110">
                    <template #default="{ row }">
                        <VortTag size="small">{{ cliToolLabel(row.cli_tool) }}</VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="状态" :width="100">
                    <template #default="{ row }">
                        <VortTag :color="statusColor(row.status)" size="small">
                            <Loader2 v-if="row.status === 'running'" :size="12" class="mr-1 animate-spin inline" />
                            {{ statusLabel(row.status) }}
                        </VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="耗时" :width="90">
                    <template #default="{ row }">
                        <span class="text-xs text-gray-500">{{ formatDuration(row.duration_seconds) }}</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="PR" :width="60">
                    <template #default="{ row }">
                        <a v-if="row.pr_url" :href="row.pr_url" target="_blank" class="text-blue-500 hover:text-blue-700">
                            <ExternalLink :size="14" />
                        </a>
                        <span v-else class="text-xs text-gray-300">-</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="时间" :width="140">
                    <template #default="{ row }">
                        <span class="text-xs text-gray-400">{{ formatTime(row.created_at) }}</span>
                    </template>
                </VortTableColumn>
            </VortTable>

            <div v-if="total > 0" class="mt-4 flex justify-end">
                <VortPagination
                    v-model:current="page"
                    v-model:page-size="pageSize"
                    :total="total"
                    show-total-info
                    show-size-changer
                    @change="handlePageChange"
                />
            </div>
        </div>

        <!-- Detail drawer -->
        <VortDrawer :open="drawerOpen" title="编码任务详情" :width="560" @update:open="drawerOpen = $event">
            <VortSpin :spinning="drawerLoading">
                <div v-if="drawerTask" class="space-y-5">
                    <!-- Status and meta -->
                    <div class="flex items-center gap-3">
                        <VortTag :color="statusColor(drawerTask.status)" size="small">
                            {{ statusLabel(drawerTask.status) }}
                        </VortTag>
                        <span class="text-xs text-gray-400">{{ formatTime(drawerTask.created_at) }}</span>
                        <span class="text-xs text-gray-400">{{ formatDuration(drawerTask.duration_seconds) }}</span>
                    </div>

                    <!-- Description -->
                    <div>
                        <div class="text-xs text-gray-400 mb-1">任务描述</div>
                        <div class="text-sm text-gray-800">{{ drawerTask.task_description }}</div>
                    </div>

                    <!-- Branch -->
                    <div class="flex items-center gap-4">
                        <div>
                            <div class="text-xs text-gray-400 mb-1">分支</div>
                            <code class="text-xs bg-gray-100 px-2 py-0.5 rounded">{{ drawerTask.branch_name }}</code>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">仓库</div>
                            <span class="text-sm">{{ repoMap[drawerTask.repo_id] || drawerTask.repo_id }}</span>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">CLI 工具</div>
                            <VortTag size="small">{{ cliToolLabel(drawerTask.cli_tool) }}</VortTag>
                        </div>
                    </div>

                    <!-- References -->
                    <div v-if="drawerTask.bug_id || drawerTask.task_id || drawerTask.story_id" class="flex items-center gap-2">
                        <VortTag v-if="drawerTask.bug_id" color="error" size="small">Bug #{{ drawerTask.bug_id.slice(0, 8) }}</VortTag>
                        <VortTag v-if="drawerTask.task_id" color="blue" size="small">Task #{{ drawerTask.task_id.slice(0, 8) }}</VortTag>
                        <VortTag v-if="drawerTask.story_id" color="green" size="small">Story #{{ drawerTask.story_id.slice(0, 8) }}</VortTag>
                    </div>

                    <!-- Changed files -->
                    <div v-if="drawerTask.files_changed?.length">
                        <div class="text-xs text-gray-400 mb-1">变更文件 ({{ drawerTask.files_changed.length }})</div>
                        <div class="bg-gray-50 rounded-lg p-3 max-h-48 overflow-y-auto">
                            <div v-for="f in drawerTask.files_changed" :key="f" class="text-xs text-gray-700 font-mono py-0.5">
                                {{ f }}
                            </div>
                        </div>
                    </div>

                    <!-- Diff summary -->
                    <div v-if="drawerTask.diff_summary">
                        <div class="text-xs text-gray-400 mb-1">Diff 摘要</div>
                        <div class="bg-gray-50 rounded-lg p-3 text-xs text-gray-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
                            {{ drawerTask.diff_summary }}
                        </div>
                    </div>

                    <!-- PR link -->
                    <div v-if="drawerTask.pr_url">
                        <a :href="drawerTask.pr_url" target="_blank"
                            class="inline-flex items-center gap-1 px-4 py-2 rounded-lg bg-blue-50 text-blue-600 hover:bg-blue-100 text-sm font-medium">
                            <ExternalLink :size="14" />
                            查看 Pull Request
                        </a>
                    </div>

                    <!-- CLI output -->
                    <div v-if="drawerTask.cli_stdout || drawerTask.cli_stderr">
                        <VortButton variant="link" size="small" @click="showStdout = !showStdout">
                            {{ showStdout ? '收起' : '查看' }} CLI 输出日志
                        </VortButton>
                        <div v-if="showStdout" class="mt-2 space-y-2">
                            <div v-if="drawerTask.cli_stdout" class="bg-gray-900 rounded-lg p-3 text-xs text-green-400 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
                                {{ drawerTask.cli_stdout }}
                            </div>
                            <div v-if="drawerTask.cli_stderr" class="bg-gray-900 rounded-lg p-3 text-xs text-red-400 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                                {{ drawerTask.cli_stderr }}
                            </div>
                        </div>
                    </div>

                    <!-- Re-execute button -->
                    <div class="pt-2">
                        <VortButton @click="goToChat(drawerTask)">
                            <TerminalSquare :size="14" class="mr-1" />
                            重新执行
                        </VortButton>
                    </div>
                </div>
            </VortSpin>
        </VortDrawer>
    </div>
</template>
