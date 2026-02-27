<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import {
    getMySchedules, createMySchedule, updateMySchedule, deleteMySchedule,
    toggleMySchedule, runMySchedule,
    getAdminSchedules, createAdminSchedule, updateAdminSchedule, deleteAdminSchedule,
    toggleAdminSchedule, runAdminSchedule,
} from "@/api";
import { Plus, Play, Users, User, RefreshCw } from "lucide-vue-next";
import { message } from "@/components/vort/message";
import { useUserStore } from "@/stores";

// ---- 类型 ----

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
    enabled: boolean;
    last_run_at: string | null;
    last_status: string;
    last_result: string;
    created_at: string | null;
    updated_at: string | null;
}

// ---- 状态 ----

const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin);
const activeTab = ref("my");

const myJobs = ref<ScheduleJob[]>([]);
const teamJobs = ref<ScheduleJob[]>([]);
const loadingMy = ref(false);
const loadingTeam = ref(false);

// 弹窗
const dialogOpen = ref(false);
const dialogMode = ref<"create" | "edit">("create");
const dialogScope = ref<"personal" | "team">("personal");
const editingJob = ref<ScheduleJob | null>(null);
const saving = ref(false);

const scheduleTypeOptions = [
    { value: "cron", label: "Cron 表达式" },
    { value: "interval", label: "固定间隔（秒）" },
    { value: "once", label: "一次性" },
];

const form = ref({
    name: "",
    description: "",
    schedule_type: "cron" as string,
    schedule: "",
    timezone: "Asia/Shanghai",
    action_config: { prompt: "" },
    enabled: true,
});

// 执行结果抽屉
const resultOpen = ref(false);
const resultJob = ref<ScheduleJob | null>(null);

// ---- 数据加载 ----

async function loadMyJobs() {
    loadingMy.value = true;
    try {
        const res = await getMySchedules();
        myJobs.value = (res as any).jobs || [];
    } catch { myJobs.value = []; }
    loadingMy.value = false;
}

async function loadTeamJobs() {
    if (!isAdmin.value) return;
    loadingTeam.value = true;
    try {
        const res = await getAdminSchedules();
        teamJobs.value = (res as any).jobs || [];
    } catch { teamJobs.value = []; }
    loadingTeam.value = false;
}

function refresh() {
    loadMyJobs();
    if (isAdmin.value) loadTeamJobs();
}

onMounted(refresh);

// ---- 弹窗操作 ----

function openCreate(scope: "personal" | "team") {
    dialogMode.value = "create";
    dialogScope.value = scope;
    editingJob.value = null;
    form.value = {
        name: "",
        description: "",
        schedule_type: "cron",
        schedule: "",
        timezone: "Asia/Shanghai",
        action_config: { prompt: "" },
        enabled: true,
    };
    dialogOpen.value = true;
}

function openEdit(job: ScheduleJob) {
    dialogMode.value = "edit";
    dialogScope.value = job.scope as "personal" | "team";
    editingJob.value = job;
    form.value = {
        name: job.name,
        description: job.description,
        schedule_type: job.schedule_type,
        schedule: job.schedule,
        timezone: job.timezone,
        action_config: { prompt: job.action_config?.prompt || "" },
        enabled: job.enabled,
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

// ---- 行操作 ----

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

function showResult(job: ScheduleJob) {
    resultJob.value = job;
    resultOpen.value = true;
}

// ---- 辅助 ----

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
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <VortTabs v-model:activeKey="activeTab">
                <!-- 我的任务 Tab -->
                <VortTabPane tab-key="my" tab="我的任务">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2 text-sm text-gray-500">
                            <User :size="14" />
                            <span>共 {{ myJobs.length }} 个任务</span>
                        </div>
                        <VortButton variant="primary" @click="openCreate('personal')">
                            <Plus :size="14" class="mr-1" /> 新建任务
                        </VortButton>
                    </div>

                    <VortTable :data-source="myJobs" :loading="loadingMy" row-key="job_id" :pagination="false">
                        <VortTableColumn label="名称" prop="name" :min-width="180">
                            <template #default="{ row }">
                                <div class="font-medium text-gray-800">{{ row.name }}</div>
                                <div v-if="row.description" class="text-xs text-gray-400 mt-0.5">{{ row.description }}</div>
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
                        <VortTableColumn label="操作" :width="140" fixed="right">
                            <template #default="{ row }">
                                <TableActions>
                                    <TableActionsItem @click="handleRun(row)">执行</TableActionsItem>
                                    <TableActionsItem @click="openEdit(row)">编辑</TableActionsItem>
                                    <DeleteRecord
                                        :request-api="deleteApi"
                                        :params="{ job_id: row.job_id }"
                                        :title="`确定删除任务「${row.name}」？`"
                                        :on-success="refresh"
                                    >
                                        <TableActionsItem danger>删除</TableActionsItem>
                                    </DeleteRecord>
                                </TableActions>
                            </template>
                        </VortTableColumn>
                    </VortTable>
                </VortTabPane>

                <!-- 团队任务 Tab（仅 admin） -->
                <VortTabPane v-if="isAdmin" tab-key="team" tab="团队任务">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2 text-sm text-gray-500">
                            <Users :size="14" />
                            <span>共 {{ teamJobs.length }} 个任务</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <VortButton @click="loadTeamJobs">
                                <RefreshCw :size="14" class="mr-1" /> 刷新
                            </VortButton>
                            <VortButton variant="primary" @click="openCreate('team')">
                                <Plus :size="14" class="mr-1" /> 新建团队任务
                            </VortButton>
                        </div>
                    </div>

                    <VortTable :data-source="teamJobs" :loading="loadingTeam" row-key="job_id" :pagination="false">
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
                        <VortTableColumn label="操作" :width="140" fixed="right">
                            <template #default="{ row }">
                                <TableActions>
                                    <TableActionsItem @click="handleRun(row)">执行</TableActionsItem>
                                    <TableActionsItem @click="openEdit(row)">编辑</TableActionsItem>
                                    <DeleteRecord
                                        :request-api="deleteApi"
                                        :params="{ job_id: row.job_id }"
                                        :title="`确定删除任务「${row.name}」？`"
                                        :on-success="refresh"
                                    >
                                        <TableActionsItem danger>删除</TableActionsItem>
                                    </DeleteRecord>
                                </TableActions>
                            </template>
                        </VortTableColumn>
                    </VortTable>
                </VortTabPane>
            </VortTabs>
        </div>

        <!-- 新建/编辑弹窗 -->
        <VortDialog :open="dialogOpen" :title="dialogMode === 'create' ? '新建任务' : '编辑任务'" @update:open="dialogOpen = $event">
            <VortForm label-width="100px">
                <VortFormItem label="任务名称" required>
                    <VortInput v-model="form.name" placeholder="例如：每日站会提醒" />
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortInput v-model="form.description" placeholder="任务用途说明" />
                </VortFormItem>
                <VortFormItem label="调度类型" required>
                    <VortSelect v-model="form.schedule_type" :options="scheduleTypeOptions" placeholder="请选择" />
                </VortFormItem>
                <VortFormItem :label="scheduleFieldLabel" required>
                    <VortInput v-model="form.schedule" :placeholder="schedulePlaceholder" />
                </VortFormItem>
                <VortFormItem label="时区">
                    <VortInput v-model="form.timezone" placeholder="Asia/Shanghai" />
                </VortFormItem>
                <VortFormItem label="执行 Prompt" required>
                    <VortTextarea v-model="form.action_config.prompt" :rows="4"
                        placeholder="Agent 将执行的指令，例如：汇总今日所有未完成的任务，生成待办清单" />
                </VortFormItem>
                <VortFormItem label="立即启用">
                    <VortSwitch v-model:checked="form.enabled" />
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
