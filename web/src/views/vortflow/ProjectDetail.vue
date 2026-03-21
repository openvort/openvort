<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick, onBeforeUnmount } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
    ArrowLeft, ArrowRight, Bug, Users, Plus,
    Trash2, FolderGit2, TerminalSquare, ExternalLink,
    Repeat, User, Hash,
} from "lucide-vue-next";
import {
    getVortflowProject, getVortflowStats, getVortflowStories,
    getVortflowTasks, getVortflowBugs, getVortflowProjectMembers,
    addVortflowProjectMember, removeVortflowProjectMember,
    getVortgitRepos, getVortgitCodeTasks, getVortflowIterations,
} from "@/api";
import { useVortFlowStore } from "@/stores";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import * as echarts from "echarts";

const route = useRoute();
const router = useRouter();
const vortFlowStore = useVortFlowStore();
const projectId = computed(() => route.params.id as string);

const {
    memberOptions, ownerGroups, getAvatarBg, getAvatarLabel,
    getMemberAvatarUrl, getMemberIdByName, getMemberNameById,
    loadMemberOptions,
} = useWorkItemCommon();

watch(projectId, (id) => {
    if (id && id !== vortFlowStore.selectedProjectId) {
        vortFlowStore.setProjectId(id);
    }
}, { immediate: true });

const loading = ref(true);
const project = ref<any>({});
const stats = ref({ stories: { total: 0, done: 0 }, tasks: { total: 0, done: 0 }, bugs: { total: 0, closed: 0 } });
const stories = ref<any[]>([]);
const tasks = ref<any[]>([]);
const bugs = ref<any[]>([]);
const members = ref<any[]>([]);
const repos = ref<any[]>([]);
const codeTasks = ref<any[]>([]);
const iterations = ref<any[]>([]);
const activeTab = ref("overview");

const roleLabels: Record<string, string> = {
    owner: "负责人", pm: "产品经理", dev: "开发", tester: "测试",
    member: "成员", viewer: "观察者",
};
const roleColorMap: Record<string, string> = {
    owner: "orange", pm: "blue", dev: "green", tester: "purple",
    member: "default", viewer: "default",
};
const roleOptions = [
    { value: "owner", label: "负责人" },
    { value: "pm", label: "产品经理" },
    { value: "dev", label: "开发" },
    { value: "tester", label: "测试" },
    { value: "member", label: "成员" },
    { value: "viewer", label: "观察者" },
];

const repoTypeColorMap: Record<string, string> = {
    frontend: "blue", backend: "green", mobile: "purple", docs: "cyan", infra: "orange", other: "default"
};
const repoTypeLabels: Record<string, string> = {
    frontend: "前端", backend: "后端", mobile: "移动端", docs: "文档", infra: "基础设施", other: "其他"
};

const stateColorMap: Record<string, string> = {
    intake: "default", review: "processing", rejected: "red", pm_refine: "orange",
    design: "cyan", breakdown: "purple", dev_assign: "geekblue", in_progress: "blue",
    testing: "orange", bugfix: "volcano", done: "green",
    todo: "default", closed: "default",
    open: "red", confirmed: "orange", fixing: "processing",
    resolved: "cyan", verified: "green",
};
const stateLabels: Record<string, string> = {
    intake: "意向", review: "评审", rejected: "已驳回", pm_refine: "产品完善",
    design: "UI 设计", breakdown: "拆分估时", dev_assign: "分配开发",
    in_progress: "进行中", testing: "测试中", bugfix: "Bug 修复", done: "已完成",
    todo: "待办", closed: "已关闭",
    open: "打开", confirmed: "已确认", fixing: "修复中",
    resolved: "已解决", verified: "已验证",
};
const stateLabel = (val: string) => stateLabels[val] || val;

const iterStatusColorMap: Record<string, string> = {
    planning: "default", active: "processing", completed: "green",
};
const iterStatusLabel = (s: string) => {
    const m: Record<string, string> = { planning: "规划中", active: "进行中", completed: "已完成" };
    return m[s] || s;
};

const storyProgress = computed(() => {
    const s = stats.value.stories;
    return s.total ? Math.round((s.done / s.total) * 100) : 0;
});
const taskProgress = computed(() => {
    const t = stats.value.tasks;
    return t.total ? Math.round((t.done / t.total) * 100) : 0;
});
const bugCloseRate = computed(() => {
    const b = stats.value.bugs;
    return b.total ? Math.round((b.closed / b.total) * 100) : 0;
});

const ringCircumference = 2 * Math.PI * 18;
const ringDashoffset = (percent: number) => ringCircumference * (1 - percent / 100);

const activeIterations = computed(() =>
    iterations.value.filter((i: any) => i.status === "active"),
);

const ownerName = computed(() => {
    if (!project.value.owner_id) return "-";
    return getMemberNameById(project.value.owner_id) || project.value.owner_id;
});

const formatDate = (iso: string | null | undefined) => {
    if (!iso) return "-";
    return String(iso).split("T")[0];
};

const formatTime = (iso: string | null) => {
    if (!iso) return "-";
    try { return new Date(iso).toLocaleString("zh-CN"); } catch { return iso; }
};

const loadData = async () => {
    loading.value = true;
    try {
        const [projRes, statsRes, storiesRes, tasksRes, bugsRes, membersRes, reposRes, iterRes] = await Promise.all([
            getVortflowProject(projectId.value),
            getVortflowStats(projectId.value),
            getVortflowStories({ project_id: projectId.value, page: 1, page_size: 10 }),
            getVortflowTasks({ project_id: projectId.value, page: 1, page_size: 10 }),
            getVortflowBugs({ project_id: projectId.value, page: 1, page_size: 10 }),
            getVortflowProjectMembers(projectId.value),
            getVortgitRepos({ project_id: projectId.value, page: 1, page_size: 20 }).catch(() => ({ items: [] })),
            getVortflowIterations({ project_id: projectId.value, page: 1, page_size: 50 }),
        ]);
        project.value = projRes || {};
        if (statsRes) {
            const r = statsRes as any;
            stats.value = {
                stories: r.stories ?? { total: 0, done: 0 },
                tasks: r.tasks ?? { total: 0, done: 0 },
                bugs: r.bugs ?? { total: 0, closed: 0 },
            };
        }
        stories.value = (storiesRes as any)?.items || [];
        tasks.value = (tasksRes as any)?.items || [];
        bugs.value = (bugsRes as any)?.items || [];
        members.value = (membersRes as any)?.items || [];
        repos.value = (reposRes as any)?.items || [];
        iterations.value = (iterRes as any)?.items || [];

        const repoIds = repos.value.map((r: any) => r.id);
        if (repoIds.length > 0) {
            try {
                const allTasks: any[] = [];
                for (const rid of repoIds.slice(0, 5)) {
                    const ct: any = await getVortgitCodeTasks({ repo_id: rid, page: 1, page_size: 10 });
                    allTasks.push(...(ct.items || []));
                }
                allTasks.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
                codeTasks.value = allTasks.slice(0, 10);
            } catch { codeTasks.value = []; }
        }

        await nextTick();
        initChart();
    } catch { /* silent */ }
    finally { loading.value = false; }
};

// Member management
const memberDialogVisible = ref(false);
const selectedMemberNames = ref<string[]>([]);
const newMemberRole = ref("member");
const memberSearchKeyword = ref("");
const addingMembers = ref(false);

const existingMemberIds = computed(() => new Set(members.value.map((m: any) => m.member_id)));

const filteredAddGroups = computed(() => {
    const kw = memberSearchKeyword.value.trim().toLowerCase();
    return ownerGroups.value
        .map((group) => ({
            ...group,
            members: group.members.filter((name) => {
                const id = getMemberIdByName(name);
                if (id && existingMemberIds.value.has(id)) return false;
                if (!kw) return true;
                return name.toLowerCase().includes(kw);
            }),
        }))
        .filter((group) => group.members.length > 0);
});

const toggleMemberSelection = (name: string) => {
    const idx = selectedMemberNames.value.indexOf(name);
    if (idx >= 0) {
        selectedMemberNames.value.splice(idx, 1);
    } else {
        selectedMemberNames.value.push(name);
    }
};

const removeMemberSelection = (name: string) => {
    const idx = selectedMemberNames.value.indexOf(name);
    if (idx >= 0) selectedMemberNames.value.splice(idx, 1);
};

const handleAddMember = async () => {
    if (selectedMemberNames.value.length === 0) return;
    addingMembers.value = true;
    try {
        for (const name of selectedMemberNames.value) {
            const memberId = getMemberIdByName(name) || name;
            await addVortflowProjectMember(projectId.value, { member_id: memberId, role: newMemberRole.value });
        }
        selectedMemberNames.value = [];
        newMemberRole.value = "member";
        memberSearchKeyword.value = "";
        memberDialogVisible.value = false;
        const res = await getVortflowProjectMembers(projectId.value);
        members.value = (res as any)?.items || [];
    } finally {
        addingMembers.value = false;
    }
};

const handleRemoveMember = async (memberId: string) => {
    await removeVortflowProjectMember(projectId.value, memberId);
    const res = await getVortflowProjectMembers(projectId.value);
    members.value = (res as any)?.items || [];
};

const codeTaskStatusColor = (s: string) => {
    if (s === "success") return "success";
    if (s === "review") return "warning";
    if (s === "failed") return "error";
    if (s === "running") return "processing";
    return "default";
};

const codeTaskStatusLabel = (s: string) => {
    const m: Record<string, string> = { pending: "等待中", running: "执行中", success: "成功", failed: "失败", review: "待审核" };
    return m[s] || s;
};

const repoNameById = (id: string) => {
    const r = repos.value.find((r: any) => r.id === id);
    return r ? r.full_name || r.name : id;
};

const goBack = () => router.push("/vortflow/board");
const goToIterationDetail = (id: string) => router.push(`/vortflow/iterations?id=${id}`);
const goToAllIterations = () => router.push("/vortflow/iterations");

// ECharts
const chartRef = ref<HTMLDivElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

const initChart = () => {
    if (!chartRef.value) return;
    if (chartInstance) chartInstance.dispose();

    chartInstance = echarts.init(chartRef.value);

    const memberWorkload: Record<string, { stories: number; tasks: number; bugs: number }> = {};
    for (const s of stories.value) {
        const name = s.owner_name || s.assignee || "未指派";
        if (!memberWorkload[name]) memberWorkload[name] = { stories: 0, tasks: 0, bugs: 0 };
        memberWorkload[name].stories++;
    }
    for (const t of tasks.value) {
        const name = t.assignee || t.owner_name || "未指派";
        if (!memberWorkload[name]) memberWorkload[name] = { stories: 0, tasks: 0, bugs: 0 };
        memberWorkload[name].tasks++;
    }
    for (const b of bugs.value) {
        const name = b.assignee || b.owner_name || "未指派";
        if (!memberWorkload[name]) memberWorkload[name] = { stories: 0, tasks: 0, bugs: 0 };
        memberWorkload[name].bugs++;
    }

    const names = Object.keys(memberWorkload);
    if (names.length === 0) {
        chartInstance.setOption({
            title: { text: "暂无数据", left: "center", top: "center", textStyle: { color: "#999", fontSize: 14 } },
        });
        return;
    }

    chartInstance.setOption({
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        legend: { data: ["需求", "任务", "缺陷"], bottom: 0 },
        grid: { left: 40, right: 20, top: 20, bottom: 40 },
        xAxis: { type: "category", data: names, axisLabel: { fontSize: 11, rotate: names.length > 6 ? 30 : 0 } },
        yAxis: { type: "value", minInterval: 1 },
        series: [
            { name: "需求", type: "bar", stack: "total", data: names.map(n => memberWorkload[n].stories), itemStyle: { color: "#3b82f6" } },
            { name: "任务", type: "bar", stack: "total", data: names.map(n => memberWorkload[n].tasks), itemStyle: { color: "#22c55e" } },
            { name: "缺陷", type: "bar", stack: "total", data: names.map(n => memberWorkload[n].bugs), itemStyle: { color: "#ef4444" } },
        ],
    });
};

const handleResize = () => chartInstance?.resize();

watch(projectId, () => loadData());

onMounted(async () => {
    await loadMemberOptions();
    loadData();
    window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
    chartInstance?.dispose();
    chartInstance = null;
    window.removeEventListener("resize", handleResize);
});
</script>

<template>
    <div>
        <vort-spin :spinning="loading">
            <div class="space-y-4">

            <!-- Header with tabs -->
            <div class="bg-white rounded-xl p-6">
                <div class="flex items-center gap-3 mb-4">
                    <a class="text-gray-400 hover:text-gray-600 cursor-pointer" @click="goBack">
                        <ArrowLeft :size="18" />
                    </a>
                    <h3 class="text-lg font-medium text-gray-800">{{ project.name || '项目详情' }}</h3>
                </div>
                <VortTabs v-model:activeKey="activeTab" :hide-content="true">
                    <VortTabPane tab-key="overview" tab="概览" />
                    <VortTabPane tab-key="workitems" tab="工作项" />
                    <VortTabPane tab-key="iterations" tab="迭代" />
                </VortTabs>
            </div>

            <!-- Overview tab -->
            <template v-if="activeTab === 'overview'">
                <!-- Project info + Chart in 2 columns -->
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
                    <!-- Left: project info card -->
                    <div class="bg-white rounded-xl p-6">
                        <h4 class="text-sm font-medium text-gray-800 mb-4">项目信息</h4>
                        <div class="space-y-4">
                            <div>
                                <span class="text-xs text-gray-400">项目负责人</span>
                                <div class="flex items-center gap-2 mt-1">
                                    <div v-if="ownerName !== '-'" class="w-6 h-6 rounded-full flex items-center justify-center text-xs text-white flex-shrink-0"
                                        :style="{ backgroundColor: getAvatarBg(ownerName) }">
                                        <img v-if="getMemberAvatarUrl(ownerName)" :src="getMemberAvatarUrl(ownerName)" class="w-full h-full rounded-full object-cover" />
                                        <template v-else>{{ getAvatarLabel(ownerName) }}</template>
                                    </div>
                                    <span class="text-sm text-gray-800">{{ ownerName }}</span>
                                </div>
                            </div>
                            <div>
                                <span class="text-xs text-gray-400">项目编号</span>
                                <div class="text-sm text-gray-800 mt-1 flex items-center gap-1">
                                    <Hash :size="12" class="text-gray-400" />{{ projectId }}
                                </div>
                            </div>
                            <div>
                                <span class="text-xs text-gray-400">项目周期</span>
                                <div class="text-sm text-gray-800 mt-1">
                                    {{ formatDate(project.start_date) }} ~ {{ formatDate(project.end_date) }}
                                </div>
                            </div>
                            <div v-if="project.product">
                                <span class="text-xs text-gray-400">产品</span>
                                <div class="text-sm text-gray-800 mt-1">{{ project.product }}</div>
                            </div>
                            <div v-if="project.version">
                                <span class="text-xs text-gray-400">版本</span>
                                <div class="text-sm text-gray-800 mt-1">v{{ project.version }}</div>
                            </div>
                            <div v-if="project.description">
                                <span class="text-xs text-gray-400">项目简介</span>
                                <div class="mt-1 text-sm">
                                    <MarkdownView :content="project.description" />
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right: chart area -->
                    <div class="lg:col-span-2 bg-white rounded-xl p-6">
                        <h4 class="text-sm font-medium text-gray-800 mb-4">成员负荷报表</h4>
                        <div ref="chartRef" class="w-full" style="height: 280px;" />
                    </div>
                </div>

                <!-- Stats with SVG ring -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-white rounded-xl p-5 flex items-center gap-4">
                        <div class="relative w-12 h-12 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#3b82f6" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(storyProgress)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-[10px] font-semibold text-blue-600">{{ storyProgress }}%</span>
                            </div>
                        </div>
                        <div>
                            <div class="text-xl font-bold text-gray-800">{{ stats.stories.total }}</div>
                            <div class="text-xs text-gray-400">需求 · 已完成 {{ stats.stories.done }}</div>
                        </div>
                    </div>
                    <div class="bg-white rounded-xl p-5 flex items-center gap-4">
                        <div class="relative w-12 h-12 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#22c55e" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(taskProgress)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-[10px] font-semibold text-green-600">{{ taskProgress }}%</span>
                            </div>
                        </div>
                        <div>
                            <div class="text-xl font-bold text-gray-800">{{ stats.tasks.total }}</div>
                            <div class="text-xs text-gray-400">任务 · 已完成 {{ stats.tasks.done }}</div>
                        </div>
                    </div>
                    <div class="bg-white rounded-xl p-5 flex items-center gap-4">
                        <div class="relative w-12 h-12 flex-shrink-0">
                            <svg viewBox="0 0 40 40" class="w-full h-full -rotate-90">
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#e5e7eb" stroke-width="3" />
                                <circle cx="20" cy="20" r="18" fill="none" stroke="#ef4444" stroke-width="3"
                                    stroke-linecap="round"
                                    :stroke-dasharray="ringCircumference"
                                    :stroke-dashoffset="ringDashoffset(bugCloseRate)"
                                    class="transition-all duration-500"
                                />
                            </svg>
                            <div class="absolute inset-0 flex items-center justify-center">
                                <span class="text-[10px] font-semibold text-red-600">{{ bugCloseRate }}%</span>
                            </div>
                        </div>
                        <div>
                            <div class="text-xl font-bold text-gray-800">{{ stats.bugs.total }}</div>
                            <div class="text-xs text-gray-400">缺陷 · 已关闭 {{ stats.bugs.closed }}</div>
                        </div>
                    </div>
                </div>

                <!-- Iterations section -->
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-medium text-gray-800">
                            <Repeat :size="16" class="inline mr-1.5 text-blue-500" />当前进行中的迭代
                        </h3>
                        <a class="text-sm text-blue-500 hover:text-blue-700 cursor-pointer flex items-center gap-1" @click="goToAllIterations">
                            查看所有迭代 <ArrowRight :size="14" />
                        </a>
                    </div>
                    <div v-if="activeIterations.length === 0 && iterations.length === 0" class="text-center py-6 text-gray-400 text-sm">
                        暂无迭代数据
                    </div>
                    <vort-table
                        v-else
                        :data-source="activeIterations.length > 0 ? activeIterations : iterations.slice(0, 5)"
                        :pagination="false"
                        size="small"
                    >
                        <vort-table-column label="标题" prop="name" :width="200">
                            <template #default="{ row }">
                                <a class="text-sm text-blue-600 hover:underline cursor-pointer" @click.stop="goToIterationDetail(row.id)">
                                    {{ row.name }}
                                </a>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="状态" :width="100">
                            <template #default="{ row }">
                                <vort-tag :color="iterStatusColorMap[row.status] || 'default'" size="small">
                                    {{ iterStatusLabel(row.status) }}
                                </vort-tag>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="起止时间" :width="200">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-500">
                                    {{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}
                                </span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="预估工时" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-600">
                                    {{ row.estimate_hours ? `${row.estimate_hours}h` : '-' }}
                                </span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="目标" :min-width="200">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-400 line-clamp-1">{{ row.goal || '-' }}</span>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>

                <!-- Members -->
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-medium text-gray-800">
                            <Users :size="16" class="inline mr-1" /> 项目成员
                        </h3>
                        <vort-button size="small" @click="memberDialogVisible = true">
                            <Plus :size="12" class="mr-1" /> 添加成员
                        </vort-button>
                    </div>
                    <div v-if="members.length === 0" class="text-sm text-gray-400 py-4 text-center">暂无成员</div>
                    <div v-else class="space-y-2">
                        <div v-for="m in members" :key="m.id" class="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-gray-50">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-full flex items-center justify-center text-sm text-white font-medium"
                                    :style="{ backgroundColor: getAvatarBg(getMemberNameById(m.member_id) || m.member_id) }">
                                    <img v-if="getMemberAvatarUrl(getMemberNameById(m.member_id) || m.member_id)"
                                        :src="getMemberAvatarUrl(getMemberNameById(m.member_id) || m.member_id)"
                                        class="w-full h-full rounded-full object-cover" />
                                    <template v-else>{{ getAvatarLabel(getMemberNameById(m.member_id) || m.member_id) }}</template>
                                </div>
                                <div>
                                    <span class="text-sm text-gray-800">{{ getMemberNameById(m.member_id) || m.member_id }}</span>
                                    <vort-tag size="small" class="ml-2" :color="roleColorMap[m.role] || 'default'">
                                        {{ roleLabels[m.role] || m.role }}
                                    </vort-tag>
                                </div>
                            </div>
                            <vort-popconfirm title="确认移除该成员？" @confirm="handleRemoveMember(m.member_id)">
                                <a class="text-sm text-red-500 cursor-pointer"><Trash2 :size="14" /></a>
                            </vort-popconfirm>
                        </div>
                    </div>
                </div>
            </template>

            <!-- Work items tab -->
            <template v-if="activeTab === 'workitems'">
                <!-- Linked Repos -->
                <div v-if="repos.length > 0" class="bg-white rounded-xl p-6">
                    <h3 class="text-base font-medium text-gray-800 mb-4">
                        <FolderGit2 :size="16" class="inline mr-1" /> 代码仓库
                    </h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                        <div v-for="r in repos" :key="r.id" class="border border-gray-100 rounded-lg p-3 hover:shadow-sm transition-shadow">
                            <div class="flex items-start justify-between mb-1">
                                <h4 class="text-sm font-medium text-gray-800 truncate flex-1">{{ r.name }}</h4>
                                <vort-tag v-if="r.is_private" size="small" color="default">私有</vort-tag>
                            </div>
                            <p class="text-xs text-gray-400 truncate mb-2">{{ r.full_name }}</p>
                            <div class="flex items-center gap-2 flex-wrap">
                                <vort-tag v-if="r.language" size="small" color="processing">{{ r.language }}</vort-tag>
                                <vort-tag size="small" :color="repoTypeColorMap[r.repo_type] || 'default'">{{ repoTypeLabels[r.repo_type] || r.repo_type }}</vort-tag>
                                <span class="text-xs text-gray-400">{{ r.default_branch }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- AI Coding Activity -->
                <div v-if="codeTasks.length > 0" class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-medium text-gray-800">
                            <TerminalSquare :size="16" class="inline mr-1" /> AI 编码活动
                        </h3>
                        <router-link :to="{ name: 'vortgit-code-tasks' }" class="text-sm text-blue-600 hover:underline">
                            查看全部
                        </router-link>
                    </div>
                    <VortTimeline>
                        <VortTimelineItem v-for="ct in codeTasks" :key="ct.id" :color="codeTaskStatusColor(ct.status) === 'error' ? 'red' : codeTaskStatusColor(ct.status) === 'success' ? 'green' : 'blue'">
                            <div class="flex items-start justify-between">
                                <div class="flex-1 min-w-0">
                                    <div class="flex items-center gap-2 flex-wrap">
                                        <span class="text-sm text-gray-800">{{ ct.member_id }}</span>
                                        <span class="text-xs text-gray-400">触发了编码任务</span>
                                        <vort-tag :color="codeTaskStatusColor(ct.status)" size="small">{{ codeTaskStatusLabel(ct.status) }}</vort-tag>
                                    </div>
                                    <div class="text-sm text-gray-600 mt-1 truncate">{{ ct.task_description }}</div>
                                    <div class="flex items-center gap-3 mt-1 text-xs text-gray-400">
                                        <span>{{ repoNameById(ct.repo_id) }}</span>
                                        <span v-if="ct.files_changed?.length">{{ ct.files_changed.length }} 个文件</span>
                                        <span>{{ formatTime(ct.created_at) }}</span>
                                    </div>
                                </div>
                                <a v-if="ct.pr_url" :href="ct.pr_url" target="_blank" class="text-blue-500 hover:text-blue-700 ml-2 shrink-0">
                                    <ExternalLink :size="14" />
                                </a>
                            </div>
                        </VortTimelineItem>
                    </VortTimeline>
                </div>

                <!-- Recent Stories -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-base font-medium text-gray-800 mb-4">最近需求</h3>
                    <div v-if="stories.length === 0" class="text-sm text-gray-400 py-4 text-center">暂无需求</div>
                    <div v-else class="space-y-2">
                        <div v-for="s in stories" :key="s.id" class="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-gray-50">
                            <span class="text-sm text-gray-800 truncate flex-1">{{ s.title }}</span>
                            <vort-tag :color="stateColorMap[s.state] || 'default'" size="small">{{ stateLabel(s.state) }}</vort-tag>
                        </div>
                    </div>
                </div>
            </template>

            <!-- Iterations tab -->
            <template v-if="activeTab === 'iterations'">
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-medium text-gray-800">
                            <Repeat :size="16" class="inline mr-1" /> 全部迭代
                        </h3>
                        <a class="text-sm text-blue-500 hover:text-blue-700 cursor-pointer" @click="goToAllIterations">
                            前往迭代管理
                        </a>
                    </div>
                    <div v-if="iterations.length === 0" class="text-sm text-gray-400 py-8 text-center">暂无迭代</div>
                    <vort-table v-else :data-source="iterations" :pagination="false" size="small">
                        <vort-table-column label="标题" prop="name" :width="200">
                            <template #default="{ row }">
                                <a class="text-sm text-blue-600 hover:underline cursor-pointer" @click.stop="goToIterationDetail(row.id)">
                                    {{ row.name }}
                                </a>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="状态" :width="100">
                            <template #default="{ row }">
                                <vort-tag :color="iterStatusColorMap[row.status] || 'default'" size="small">
                                    {{ iterStatusLabel(row.status) }}
                                </vort-tag>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="起止时间" :width="220">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-500">
                                    {{ formatDate(row.start_date) }} ~ {{ formatDate(row.end_date) }}
                                </span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="预估工时" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-600">{{ row.estimate_hours ? `${row.estimate_hours}h` : '-' }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="目标" :min-width="200">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-400 line-clamp-1">{{ row.goal || '-' }}</span>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>
            </template>

            </div>
        </vort-spin>

        <!-- Add Member Dialog -->
        <vort-dialog :open="memberDialogVisible" title="添加项目成员" :width="480" @update:open="v => { memberDialogVisible = v; if (!v) { selectedMemberNames = []; memberSearchKeyword = ''; } }">
            <div class="space-y-4">
                <div>
                    <span class="text-sm text-gray-600 block mb-2">选择成员</span>
                    <div v-if="selectedMemberNames.length" class="flex flex-wrap gap-1.5 mb-2">
                        <span v-for="name in selectedMemberNames" :key="name"
                            class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 border border-blue-200">
                            <span class="w-4 h-4 rounded-full flex items-center justify-center text-[10px] text-white flex-shrink-0"
                                :style="{ backgroundColor: getAvatarBg(name) }">
                                <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full rounded-full object-cover" />
                                <template v-else>{{ getAvatarLabel(name) }}</template>
                            </span>
                            {{ name }}
                            <button type="button" class="ml-0.5 text-blue-400 hover:text-blue-600" @click="removeMemberSelection(name)">&times;</button>
                        </span>
                    </div>
                    <input v-model="memberSearchKeyword" type="text" placeholder="搜索成员..."
                        class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400 transition-colors" />
                    <div class="mt-2 max-h-[240px] overflow-y-auto border border-gray-100 rounded-lg">
                        <template v-if="filteredAddGroups.length">
                            <div v-for="group in filteredAddGroups" :key="group.label">
                                <div class="px-3 py-1.5 text-xs text-gray-400 bg-gray-50 sticky top-0">{{ group.label }}（{{ group.members.length }}）</div>
                                <div v-for="name in group.members" :key="name"
                                    class="flex items-center gap-2.5 px-3 py-2 cursor-pointer hover:bg-gray-50 transition-colors"
                                    @click="toggleMemberSelection(name)">
                                    <vort-checkbox :checked="selectedMemberNames.includes(name)" @click.stop @update:checked="toggleMemberSelection(name)" />
                                    <span class="w-6 h-6 rounded-full flex items-center justify-center text-xs text-white flex-shrink-0"
                                        :style="{ backgroundColor: getAvatarBg(name) }">
                                        <img v-if="getMemberAvatarUrl(name)" :src="getMemberAvatarUrl(name)" class="w-full h-full rounded-full object-cover" />
                                        <template v-else>{{ getAvatarLabel(name) }}</template>
                                    </span>
                                    <span class="text-sm text-gray-700">{{ name }}</span>
                                </div>
                            </div>
                        </template>
                        <div v-else class="text-sm text-gray-400 text-center py-6">无可添加的成员</div>
                    </div>
                </div>
                <div>
                    <span class="text-sm text-gray-600 block mb-2">角色</span>
                    <vort-select v-model="newMemberRole" class="w-full">
                        <vort-select-option v-for="opt in roleOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                        </vort-select-option>
                    </vort-select>
                </div>
            </div>
            <template #footer>
                <div class="flex justify-end gap-3">
                    <vort-button @click="memberDialogVisible = false">取消</vort-button>
                    <vort-button variant="primary" :disabled="selectedMemberNames.length === 0" :loading="addingMembers" @click="handleAddMember">
                        确定{{ selectedMemberNames.length > 0 ? `（${selectedMemberNames.length}人）` : '' }}
                    </vort-button>
                </div>
            </template>
        </vort-dialog>
    </div>
</template>
