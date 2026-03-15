<script setup lang="ts">
import { ref, computed, watch } from "vue";
import {
    getMySchedules, createMySchedule, updateMySchedule, deleteMySchedule,
    toggleMySchedule, runMySchedule, batchDeleteMySchedules,
    getAdminSchedules, createAdminSchedule, updateAdminSchedule, deleteAdminSchedule,
    toggleAdminSchedule, runAdminSchedule, batchDeleteAdminSchedules,
    getScheduleExecutors,
} from "@/api";
import { Plus, Users, User, HelpCircle, Bot, Trash2 } from "lucide-vue-next";
import { message } from "@/components/vort";
import { useUserStore } from "@/stores";
import { useCrudPage } from "@/hooks";

// ---- Types ----

interface ScheduleJob {
    id: number;
    job_id: string;
    name: string;
    description: string;
    owner_id: string;
    scope: string;
    schedule_type: string;
    schedule: string;
    timezone: string;
    action_type: string;
    action_config: Record<string, any>;
    target_member_id: string;
    enabled: boolean;
    visible: boolean;
    last_run_at: string | null;
    last_status: string;
    last_result: string;
    created_at: string | null;
    updated_at: string | null;
}

interface Executor {
    id: string;
    name: string;
    virtual_role: string;
}

type FilterParams = {
    page: number;
    size: number;
    keyword: string;
    schedule_type: string;
    last_status: string;
    hide_done_once: boolean;
};

// ---- State ----

const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);
const activeTab = ref("my");

const scheduleTypeFilterOptions = [
    { label: "Cron 定时", value: "cron" },
    { label: "固定间隔", value: "interval" },
    { label: "一次性", value: "once" },
];

const statusFilterOptions = [
    { label: "成功", value: "success" },
    { label: "失败", value: "failed" },
    { label: "待执行", value: "pending" },
];

const scheduleTypeOptions = [
    { value: "cron", label: "Cron 表达式" },
    { value: "interval", label: "固定间隔（秒）" },
    { value: "once", label: "一次性" },
];

// ---- My Jobs CRUD ----

const fetchMyJobs = async (params: FilterParams) => {
    const res = await getMySchedules({
        page: params.page, page_size: params.size,
        keyword: params.keyword || undefined,
        schedule_type: params.schedule_type || undefined,
        last_status: params.last_status || undefined,
        hide_done_once: params.hide_done_once,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const {
    listData: myJobs, loading: loadingMy, total: myTotal,
    filterParams: myFilter, showPagination: myShowPagination,
    rowSelection: myRowSelection, selectedIds: mySelectedIds,
    hasSelection: myHasSelection, clearSelection: myCleanSelection,
    loadData: loadMyJobs, onSearchSubmit: mySearchSubmit, resetParams: myResetParams,
} = useCrudPage<ScheduleJob, FilterParams>({
    api: fetchMyJobs,
    idKey: "job_id",
    defaultParams: { page: 1, size: 20, keyword: "", schedule_type: "", last_status: "", hide_done_once: true },
});

// ---- Team Jobs CRUD ----

const fetchTeamJobs = async (params: FilterParams) => {
    const res = await getAdminSchedules({
        page: params.page, page_size: params.size,
        keyword: params.keyword || undefined,
        schedule_type: params.schedule_type || undefined,
        last_status: params.last_status || undefined,
        hide_done_once: params.hide_done_once,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const {
    listData: teamJobs, loading: loadingTeam, total: teamTotal,
    filterParams: teamFilter, showPagination: teamShowPagination,
    rowSelection: teamRowSelection, selectedIds: teamSelectedIds,
    hasSelection: teamHasSelection, clearSelection: teamCleanSelection,
    loadData: loadTeamJobs, onSearchSubmit: teamSearchSubmit, resetParams: teamResetParams,
} = useCrudPage<ScheduleJob, FilterParams>({
    api: fetchTeamJobs,
    idKey: "job_id",
    defaultParams: { page: 1, size: 20, keyword: "", schedule_type: "", last_status: "", hide_done_once: true },
});

function refresh() {
    loadMyJobs();
    if (isAdmin.value) loadTeamJobs();
}

// ---- Executors ----

const executors = ref<Executor[]>([]);
const loadingExecutors = ref(false);

async function loadExecutors() {
    loadingExecutors.value = true;
    try {
        const res = await getScheduleExecutors();
        executors.value = (res as any).executors || [];
    } catch { executors.value = []; }
    loadingExecutors.value = false;
}

// ---- Dialog ----

const dialogOpen = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const dialogScope = ref<"personal" | "team">("personal");
const editingJob = ref<ScheduleJob | null>(null);
const saving = ref(false);

const form = ref({
    name: "",
    description: "",
    schedule_type: "cron" as string,
    schedule: "",
    timezone: "Asia/Shanghai",
    action_config: { prompt: "" },
    target_member_id: "",
    enabled: true,
    visible: true,
});

function openCreate(scope: "personal" | "team") {
    dialogMode.value = "create";
    dialogScope.value = scope;
    editingJob.value = null;
    form.value = {
        name: "", description: "", schedule_type: "cron", schedule: "",
        timezone: "Asia/Shanghai", action_config: { prompt: "" },
        target_member_id: "", enabled: true, visible: true,
    };
    dialogOpen.value = true;
}

function openEdit(job: ScheduleJob) {
    dialogMode.value = "edit";
    dialogScope.value = job.scope as "personal" | "team";
    editingJob.value = job;
    form.value = {
        name: job.name, description: job.description,
        schedule_type: job.schedule_type, schedule: job.schedule,
        timezone: job.timezone,
        action_config: { prompt: job.action_config?.prompt || "" },
        target_member_id: job.target_member_id || "",
        enabled: job.enabled, visible: job.visible ?? true,
    };
    dialogOpen.value = true;
}

async function handleSave() {
    if (!form.value.name.trim()) { message.warning("请输入任务名称"); return; }
    if (!form.value.schedule.trim()) { message.warning("请输入调度规则"); return; }
    if (!form.value.action_config.prompt.trim()) { message.warning("请输入执行 Prompt"); return; }

    saving.value = true;
    try {
        if (dialogMode.value === "create") {
            const fn = dialogScope.value === "team" ? createAdminSchedule : createMySchedule;
            await fn(form.value);
            message.success("任务创建成功");
        } else if (editingJob.value) {
            const fn = dialogScope.value === "team" ? updateAdminSchedule : updateMySchedule;
            await fn(editingJob.value.job_id, form.value);
            message.success("任务更新成功");
        }
        dialogOpen.value = false;
        refresh();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || e?.detail || "操作失败");
    }
    saving.value = false;
}

// ---- Result Drawer ----

const resultOpen = ref(false);
const resultJob = ref<ScheduleJob | null>(null);

function showResult(job: ScheduleJob) {
    resultJob.value = job;
    resultOpen.value = true;
}

// ---- Row Actions ----

async function handleToggle(job: ScheduleJob) {
    const fn = activeTab.value === "team" ? toggleAdminSchedule : toggleMySchedule;
    try {
        await fn(job.job_id);
        refresh();
    } catch { message.error("操作失败"); }
}

function deleteApi(params: Record<string, unknown>) {
    const jobId = params.job_id as string;
    const fn = activeTab.value === "team" ? deleteAdminSchedule : deleteMySchedule;
    return fn(jobId);
}

async function handleRun(job: ScheduleJob) {
    const fn = activeTab.value === "team" ? runAdminSchedule : runMySchedule;
    try {
        message.info("正在执行...");
        const res = await fn(job.job_id);
        if ((res as any).success) {
            message.success("执行完成");
        } else {
            message.error((res as any).error || "执行失败");
        }
        refresh();
    } catch { message.error("执行失败"); }
}

// ---- Batch Delete ----

const batchDeleting = ref(false);

async function handleBatchDelete() {
    const ids = activeTab.value === "team" ? teamSelectedIds.value : mySelectedIds.value;
    if (!ids.length) return;
    batchDeleting.value = true;
    try {
        const fn = activeTab.value === "team" ? batchDeleteAdminSchedules : batchDeleteMySchedules;
        await fn(ids);
        message.success(`已删除 ${ids.length} 个任务`);
        if (activeTab.value === "team") { teamCleanSelection(); } else { myCleanSelection(); }
        refresh();
    } catch { message.error("批量删除失败"); }
    batchDeleting.value = false;
}

// ---- Helpers ----

function scheduleLabel(job: ScheduleJob): string {
    if (job.schedule_type === "cron") return `Cron: ${job.schedule}`;
    if (job.schedule_type === "interval") return `每 ${job.schedule} 秒`;
    if (job.schedule_type === "once") return `一次性: ${job.schedule}`;
    return job.schedule;
}

function statusTagColor(status: string): string {
    if (status === "success") return "success";
    if (status === "failed") return "error";
    return "default";
}

function statusText(status: string): string {
    if (status === "success") return "成功";
    if (status === "failed") return "失败";
    return "待执行";
}

function formatTime(iso: string | null): string {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("zh-CN"); } catch { return iso; }
}

const schedulePlaceholder = computed(() => {
    if (form.value.schedule_type === "cron") return "0 9 * * 1-5";
    if (form.value.schedule_type === "interval") return "3600";
    return "2026-03-01T09:00:00";
});

const scheduleFieldLabel = computed(() => {
    if (form.value.schedule_type === "cron") return "Cron 表达式";
    if (form.value.schedule_type === "interval") return "间隔秒数";
    return "执行时间";
});

// ---- Init ----

loadMyJobs();
loadExecutors();

watch(activeTab, (tab) => {
    if (tab === "team" && isAdmin.value && teamJobs.value.length === 0) {
        loadTeamJobs();
    }
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <VortTabs v-model:activeKey="activeTab">
                <!-- 我的任务 Tab -->
                <VortTabPane tab-key="my" tab="我的任务">
                    <!-- Filter bar -->
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                                <VortInputSearch v-model="myFilter.keyword" placeholder="搜索任务..." allow-clear class="sm:w-[180px]" @search="mySearchSubmit" @keyup.enter="mySearchSubmit" />
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-gray-500 whitespace-nowrap">类型</span>
                                <VortSelect v-model="myFilter.schedule_type" placeholder="全部" allow-clear class="sm:w-[130px]" @change="mySearchSubmit">
                                    <VortSelectOption v-for="opt in scheduleTypeFilterOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                                </VortSelect>
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                                <VortSelect v-model="myFilter.last_status" placeholder="全部" allow-clear class="sm:w-[110px]" @change="mySearchSubmit">
                                    <VortSelectOption v-for="opt in statusFilterOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                                </VortSelect>
                            </div>
                            <div class="flex items-center gap-2">
                                <VortCheckbox v-model:checked="myFilter.hide_done_once" @change="mySearchSubmit">隐藏已完成一次性</VortCheckbox>
                            </div>
                            <div class="flex items-center gap-2">
                                <VortButton variant="primary" size="small" @click="mySearchSubmit">查询</VortButton>
                                <VortButton size="small" @click="myResetParams">重置</VortButton>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0">
                            <VortButton variant="primary" @click="openCreate('personal')">
                                <Plus :size="14" class="mr-1" /> 新建任务
                            </VortButton>
                            <AiAssistButton prompt="我想创建一个计划任务，请引导我完成设置。我需要设置任务名称、调度规则（支持 cron 定时/固定间隔/一次性执行）以及任务到期后 AI 要执行的内容。" />
                        </div>
                    </div>

                    <!-- Batch actions -->
                    <div v-if="myHasSelection" class="flex items-center gap-3 mb-3 px-2 py-2 bg-blue-50 rounded-lg">
                        <span class="text-sm text-blue-600">已选 {{ mySelectedIds.length }} 项</span>
                        <VortPopconfirm title="确定批量删除选中的任务？" @confirm="handleBatchDelete">
                            <VortButton size="small" variant="danger" :loading="batchDeleting">
                                <Trash2 :size="14" class="mr-1" /> 批量删除
                            </VortButton>
                        </VortPopconfirm>
                        <VortButton size="small" @click="myCleanSelection">取消选择</VortButton>
                    </div>

                    <VortTable :data-source="myJobs" :loading="loadingMy" row-key="job_id" :pagination="false" :row-selection="myRowSelection">
                        <VortTableColumn label="名称" prop="name" :min-width="180">
                            <template #default="{ row }">
                                <div class="font-medium text-gray-800">{{ row.name }}</div>
                                <div v-if="row.description" class="text-xs text-gray-400 mt-0.5">{{ row.description }}</div>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="调度规则" :min-width="160">
                            <template #default="{ row }">{{ scheduleLabel(row) }}</template>
                        </VortTableColumn>
                        <VortTableColumn label="执行人" :width="100">
                            <template #default="{ row }">
                                <div v-if="row.target_member_id" class="flex items-center gap-1">
                                    <Bot :size="14" class="text-blue-500" />
                                    <span class="text-xs">AI 员工</span>
                                </div>
                                <div v-else class="text-xs text-gray-400">系统助手</div>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="启用" :width="80">
                            <template #default="{ row }">
                                <VortSwitch :checked="row.enabled" @update:checked="handleToggle(row)" />
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="上次执行" :min-width="140">
                            <template #default="{ row }">
                                <VortTag :color="statusTagColor(row.last_status)" size="small">
                                    {{ statusText(row.last_status) }}
                                </VortTag>
                                <div class="text-xs text-gray-400 mt-1">{{ formatTime(row.last_run_at) }}</div>
                                <VortButton v-if="row.last_result" variant="link" size="small" @click="showResult(row)">
                                    查看结果
                                </VortButton>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="操作" :width="180" fixed="right">
                            <template #default="{ row }">
                                <div class="flex items-center gap-2 whitespace-nowrap">
                                    <a class="text-sm text-blue-600 cursor-pointer" @click="handleRun(row)">执行</a>
                                    <VortDivider type="vertical" />
                                    <a class="text-sm text-blue-600 cursor-pointer" @click="openEdit(row)">编辑</a>
                                    <VortDivider type="vertical" />
                                    <DeleteRecord
                                        :request-api="deleteApi"
                                        :params="{ job_id: row.job_id }"
                                        :title="`确定删除任务「${row.name}」？`"
                                        :on-success="refresh"
                                    >
                                        <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                    </DeleteRecord>
                                </div>
                            </template>
                        </VortTableColumn>
                    </VortTable>

                    <div v-if="myShowPagination" class="flex justify-end mt-4">
                        <VortPagination v-model:current="myFilter.page" v-model:page-size="myFilter.size" :total="myTotal" show-total-info show-size-changer @change="loadMyJobs" />
                    </div>
                </VortTabPane>

                <!-- 团队任务 Tab（仅 admin） -->
                <VortTabPane v-if="isAdmin" tab-key="team" tab="团队任务">
                    <!-- Filter bar -->
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                                <VortInputSearch v-model="teamFilter.keyword" placeholder="搜索任务..." allow-clear class="sm:w-[180px]" @search="teamSearchSubmit" @keyup.enter="teamSearchSubmit" />
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-gray-500 whitespace-nowrap">类型</span>
                                <VortSelect v-model="teamFilter.schedule_type" placeholder="全部" allow-clear class="sm:w-[130px]" @change="teamSearchSubmit">
                                    <VortSelectOption v-for="opt in scheduleTypeFilterOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                                </VortSelect>
                            </div>
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                                <VortSelect v-model="teamFilter.last_status" placeholder="全部" allow-clear class="sm:w-[110px]" @change="teamSearchSubmit">
                                    <VortSelectOption v-for="opt in statusFilterOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                                </VortSelect>
                            </div>
                            <div class="flex items-center gap-2">
                                <VortCheckbox v-model:checked="teamFilter.hide_done_once" @change="teamSearchSubmit">隐藏已完成一次性</VortCheckbox>
                            </div>
                            <div class="flex items-center gap-2">
                                <VortButton variant="primary" size="small" @click="teamSearchSubmit">查询</VortButton>
                                <VortButton size="small" @click="teamResetParams">重置</VortButton>
                            </div>
                        </div>
                        <div class="flex items-center gap-2 flex-shrink-0">
                            <VortButton variant="primary" @click="openCreate('team')">
                                <Plus :size="14" class="mr-1" /> 新建团队任务
                            </VortButton>
                        </div>
                    </div>

                    <!-- Batch actions -->
                    <div v-if="teamHasSelection" class="flex items-center gap-3 mb-3 px-2 py-2 bg-blue-50 rounded-lg">
                        <span class="text-sm text-blue-600">已选 {{ teamSelectedIds.length }} 项</span>
                        <VortPopconfirm title="确定批量删除选中的任务？" @confirm="handleBatchDelete">
                            <VortButton size="small" variant="danger" :loading="batchDeleting">
                                <Trash2 :size="14" class="mr-1" /> 批量删除
                            </VortButton>
                        </VortPopconfirm>
                        <VortButton size="small" @click="teamCleanSelection">取消选择</VortButton>
                    </div>

                    <VortTable :data-source="teamJobs" :loading="loadingTeam" row-key="job_id" :pagination="false" :row-selection="teamRowSelection">
                        <VortTableColumn label="名称" prop="name" :min-width="180">
                            <template #default="{ row }">
                                <div class="font-medium text-gray-800">{{ row.name }}</div>
                                <div v-if="row.description" class="text-xs text-gray-400 mt-0.5">{{ row.description }}</div>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="范围" :width="80">
                            <template #default="{ row }">
                                <VortTag :color="row.scope === 'team' ? 'blue' : 'default'" size="small">
                                    {{ row.scope === 'team' ? '团队' : '个人' }}
                                </VortTag>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="调度规则" :min-width="160">
                            <template #default="{ row }">{{ scheduleLabel(row) }}</template>
                        </VortTableColumn>
                        <VortTableColumn label="启用" :width="80">
                            <template #default="{ row }">
                                <VortSwitch :checked="row.enabled" @update:checked="handleToggle(row)" />
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="可见" :width="80">
                            <template #default="{ row }">
                                <VortTag :color="row.visible ? 'green' : 'default'" size="small">
                                    {{ row.visible ? '可见' : '隐藏' }}
                                </VortTag>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="上次执行" :min-width="140">
                            <template #default="{ row }">
                                <VortTag :color="statusTagColor(row.last_status)" size="small">
                                    {{ statusText(row.last_status) }}
                                </VortTag>
                                <div class="text-xs text-gray-400 mt-1">{{ formatTime(row.last_run_at) }}</div>
                                <VortButton v-if="row.last_result" variant="link" size="small" @click="showResult(row)">
                                    查看结果
                                </VortButton>
                            </template>
                        </VortTableColumn>
                        <VortTableColumn label="操作" :width="180" fixed="right">
                            <template #default="{ row }">
                                <div class="flex items-center gap-2 whitespace-nowrap">
                                    <a class="text-sm text-blue-600 cursor-pointer" @click="handleRun(row)">执行</a>
                                    <VortDivider type="vertical" />
                                    <a class="text-sm text-blue-600 cursor-pointer" @click="openEdit(row)">编辑</a>
                                    <VortDivider type="vertical" />
                                    <DeleteRecord
                                        :request-api="deleteApi"
                                        :params="{ job_id: row.job_id }"
                                        :title="`确定删除任务「${row.name}」？`"
                                        :on-success="refresh"
                                    >
                                        <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                    </DeleteRecord>
                                </div>
                            </template>
                        </VortTableColumn>
                    </VortTable>

                    <div v-if="teamShowPagination" class="flex justify-end mt-4">
                        <VortPagination v-model:current="teamFilter.page" v-model:page-size="teamFilter.size" :total="teamTotal" show-total-info show-size-changer @change="loadTeamJobs" />
                    </div>
                </VortTabPane>
            </VortTabs>
        </div>

        <!-- 新建/编辑弹窗 -->
        <VortDialog :open="dialogOpen" :title="dialogMode === 'create' ? '新建任务' : '编辑任务'" @update:open="dialogOpen = $event">
            <VortForm label-width="120px">
                <VortFormItem label="任务名称" required>
                    <VortInput v-model="form.name" placeholder="例如：每日站会提醒" />
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortInput v-model="form.description" placeholder="任务用途说明" />
                </VortFormItem>
                <VortFormItem label="调度类型" required>
                    <VortSelect v-model="form.schedule_type" :options="scheduleTypeOptions" placeholder="请选择" />
                </VortFormItem>
                <VortFormItem required>
                    <template #label>
                        <span>{{ scheduleFieldLabel }}</span>
                        <VortTooltip v-if="form.schedule_type === 'cron'">
                            <template #title>
                                <div class="leading-normal" style="min-width: 200px;">
                                    <div class="font-medium mb-1.5">格式：分 时 日 月 周</div>
                                    <table class="w-full mb-2" style="border-spacing: 4px 2px; border-collapse: separate;">
                                        <tr><td class="text-yellow-300 font-mono">*</td><td>每个</td><td class="text-yellow-300 font-mono">-</td><td>范围</td></tr>
                                        <tr><td class="text-yellow-300 font-mono">,</td><td>列举</td><td class="text-yellow-300 font-mono">/</td><td>步长</td></tr>
                                    </table>
                                    <div class="font-medium mb-1">示例</div>
                                    <table class="w-full" style="border-spacing: 4px 2px; border-collapse: separate;">
                                        <tr><td class="font-mono whitespace-nowrap">0 9 * * 1-5</td><td class="text-gray-300">工作日 9:00</td></tr>
                                        <tr><td class="font-mono whitespace-nowrap">0 */2 * * *</td><td class="text-gray-300">每 2 小时</td></tr>
                                        <tr><td class="font-mono whitespace-nowrap">30 8 1 * *</td><td class="text-gray-300">每月 1 号 8:30</td></tr>
                                        <tr><td class="font-mono whitespace-nowrap">0 0 * * 0</td><td class="text-gray-300">每周日 0:00</td></tr>
                                    </table>
                                </div>
                            </template>
                            <HelpCircle :size="14" class="ml-1 text-gray-400 cursor-help inline-block align-middle" />
                        </VortTooltip>
                    </template>
                    <VortInput v-model="form.schedule" :placeholder="schedulePlaceholder" />
                </VortFormItem>
                <VortFormItem label="时区">
                    <VortInput v-model="form.timezone" placeholder="Asia/Shanghai" />
                </VortFormItem>
                <VortFormItem label="执行人">
                    <VortSelect v-model="form.target_member_id" placeholder="系统助手" allow-clear :loading="loadingExecutors">
                        <VortSelectOption v-for="ex in executors" :key="ex.id" :value="ex.id">
                            <div class="flex items-center gap-2">
                                <Bot :size="14" class="text-blue-500" />
                                <span>{{ ex.name }}</span>
                                <span v-if="ex.virtual_role" class="text-gray-400 text-xs">({{ ex.virtual_role }})</span>
                            </div>
                        </VortSelectOption>
                    </VortSelect>
                    <template #help>
                        <span class="text-gray-400 text-xs">留空则由系统默认 AI 执行，選択 AI 员工则由该员工执行并汇报</span>
                    </template>
                </VortFormItem>
                <VortFormItem label="执行 Prompt" required>
                    <VortTextarea v-model="form.action_config.prompt" :rows="4"
                        placeholder="Agent 将执行的指令，例如：汇总今日所有未完成的任务，生成待办清单" />
                </VortFormItem>
                <VortFormItem label="立即启用">
                    <VortSwitch v-model:checked="form.enabled" />
                </VortFormItem>
                <VortFormItem v-if="dialogScope === 'team'" label="对成员可见">
                    <VortSwitch v-model:checked="form.visible" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="dialogOpen = false">取消</VortButton>
                    <VortButton variant="primary" :loading="saving" @click="handleSave">
                        {{ dialogMode === 'create' ? '创建' : '保存' }}
                    </VortButton>
                </div>
            </template>
        </VortDialog>

        <!-- 执行结果抽屉 -->
        <VortDrawer :open="resultOpen" title="执行结果" :width="480" @update:open="resultOpen = $event">
            <div v-if="resultJob" class="space-y-4">
                <div>
                    <div class="text-sm font-medium text-gray-700">{{ resultJob.name }}</div>
                    <div class="text-xs text-gray-400 mt-1">{{ formatTime(resultJob.last_run_at) }}</div>
                </div>
                <div>
                    <VortTag :color="statusTagColor(resultJob.last_status)">
                        {{ statusText(resultJob.last_status) }}
                    </VortTag>
                </div>
                <div class="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
                    {{ resultJob.last_result || '暂无结果' }}
                </div>
            </div>
        </VortDrawer>
    </div>
</template>
