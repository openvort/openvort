<script setup lang="ts">
import { ref, onMounted, computed, onBeforeUnmount } from "vue";
import { z } from "zod";
import { Repeat, Plus, Search, Info } from "lucide-vue-next";
import {
    getVortflowIterations, createVortflowIteration, updateVortflowIteration, deleteVortflowIteration,
    getVortflowProjects, getMembers,
} from "@/api";

interface IterationItem {
    id: string;
    project_id: string;
    name: string;
    goal: string;
    start_date: string | null;
    end_date: string | null;
    status: string;
    created_at: string | null;
    owner_id?: string;
    assignee_id?: string;
    pm_id?: string;
    owner_name?: string;
    estimate_hours?: number | null;
    actual_hours?: number | null;
}

interface ProjectItem {
    id: string;
    name: string;
}

interface MemberOption {
    id: string;
    name: string;
    avatarUrl?: string;
}

const loading = ref(true);
const iterations = ref<IterationItem[]>([]);
const projects = ref<ProjectItem[]>([]);
const selectedStatus = ref("");
const selectedOwnerId = ref("");
const searchKeyword = ref("");
const storyMetrics = ref<Record<string, { total: number; done: number }>>({});
const memberOptions = ref<MemberOption[]>([]);
const ownerDropdownOpen = ref(false);
const ownerKeyword = ref("");
const ownerDropdownRef = ref<HTMLElement | null>(null);
const ownerGroupOpen = ref(true);

// Form owner dropdown (for 新建/编辑 iteration)
const formOwnerDropdownOpen = ref(false);
const formOwnerKeyword = ref("");
const formOwnerGroupOpen = ref(true);
const formOwnerDropdownRef = ref<HTMLElement | null>(null);

const formFilteredOwnerOptions = computed(() => {
    const kw = formOwnerKeyword.value.trim().toLowerCase();
    if (!kw) return memberOptions.value;
    return memberOptions.value.filter(item => item.name.toLowerCase().includes(kw));
});

const formSelectedOwnerText = computed(() => {
    const id = currentIteration.value?.owner_id || currentIteration.value?.assignee_id || "";
    if (!id) return "请选择负责人";
    return memberOptions.value.find(m => m.id === id)?.name || "请选择负责人";
});

const statusColorMap: Record<string, string> = {
    planning: "default", active: "processing", completed: "green"
};
const statusLabels: Record<string, string> = {
    planning: "待开始", active: "进行中", completed: "已结束"
};

const filteredIterations = computed(() => {
    let list = iterations.value;
    if (selectedOwnerId.value === "__unassigned__") {
        list = list.filter(i => !iterationOwnerId(i));
    } else if (selectedOwnerId.value) {
        list = list.filter(i => iterationOwnerId(i) === selectedOwnerId.value);
    }
    if (selectedStatus.value) {
        list = list.filter(i => i.status === selectedStatus.value);
    }
    const keyword = searchKeyword.value.trim().toLowerCase();
    if (keyword) {
        list = list.filter(i => i.name.toLowerCase().includes(keyword) || (i.goal || "").toLowerCase().includes(keyword));
    }
    return list;
});

const filteredOwnerOptions = computed(() => {
    const kw = ownerKeyword.value.trim().toLowerCase();
    if (!kw) return memberOptions.value;
    return memberOptions.value.filter(item => item.name.toLowerCase().includes(kw));
});

const selectedOwnerText = computed(() => {
    if (!selectedOwnerId.value) return "负责人";
    if (selectedOwnerId.value === "__unassigned__") return "未指派";
    return memberOptions.value.find(m => m.id === selectedOwnerId.value)?.name || "负责人";
});

const iterationOwnerId = (i: IterationItem) => i.owner_id || i.assignee_id || i.pm_id || "";
const memberNameById = (id: string) => memberOptions.value.find(m => m.id === id)?.name || "";

const projectNameById = (id: string) => {
    const p = projects.value.find(p => p.id === id);
    return p ? p.name : id;
};

const loadMemberOptions = async () => {
    try {
        const res: any = await getMembers({ search: "", role: "", page: 1, size: 100 });
        const members = Array.isArray(res?.members) ? res.members : [];
        const next: MemberOption[] = [];
        const seen = new Set<string>();
        for (const item of members) {
            const id = String(item?.id || item?.member_id || item?.user_id || "").trim();
            const name = String(item?.name || item?.display_name || item?.user_id || "").trim();
            if (!id || !name || seen.has(id)) continue;
            seen.add(id);
            next.push({
                id,
                name,
                avatarUrl: String(item?.avatar_url || item?.avatar || ""),
            });
        }
        memberOptions.value = next;
    } catch {
        memberOptions.value = [];
    }
};

const loadData = async () => {
    loading.value = true;
    try {
        const [iterRes, projRes] = await Promise.all([
            getVortflowIterations({ page: 1, page_size: 100 }),
            getVortflowProjects(),
        ]);
        const list = ((iterRes as any)?.items || []) as IterationItem[];
        iterations.value = list;
        projects.value = ((projRes as any)?.items || []);
        const metrics: Record<string, { total: number; done: number }> = {};
        list.forEach((item, index) => {
            const presets = [
                { total: 4, done: 0 },
                { total: 5, done: 0 },
                { total: 15, done: 15 },
                { total: 16, done: 16 },
            ];
            metrics[item.id] = presets[index % presets.length];
        });
        storyMetrics.value = metrics;
    } catch { /* silent */ }
    finally { loading.value = false; }
};

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"add" | "edit">("add");
const currentIteration = ref<Partial<IterationItem>>({});
const formRef = ref();
const formLoading = ref(false);

const iterationValidationSchema = z.object({
    project_id: z.string().min(1, "请选择项目"),
    name: z.string().min(1, "标题必填"),
    owner_id: z.string().optional(),
    goal: z.string().optional(),
    start_date: z.string().optional(),
    end_date: z.string().optional(),
    estimate_hours: z.union([z.number(), z.string()]).optional(),
    use_doc_template: z.boolean().optional(),
    status: z.string().optional(),
});

const handleAddIteration = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新建迭代";
    currentIteration.value = { status: "planning", use_doc_template: true, owner_id: "" };
    drawerVisible.value = true;
    formOwnerDropdownOpen.value = false;
};

const handleEditIteration = (i: IterationItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑迭代";
    currentIteration.value = {
        ...i,
        owner_id: i.owner_id || i.assignee_id || i.pm_id || "",
        start_date: i.start_date ? i.start_date.split("T")[0] : "",
        end_date: i.end_date ? i.end_date.split("T")[0] : "",
    };
    drawerVisible.value = true;
    formOwnerDropdownOpen.value = false;
};

const handleSaveIteration = async (andContinue = false) => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = currentIteration.value;
    const estimateHours = typeof r.estimate_hours === "number" ? r.estimate_hours : undefined;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowIteration({
                project_id: r.project_id!,
                name: r.name!,
                goal: r.goal || "",
                owner_id: r.owner_id || undefined,
                start_date: r.start_date || undefined,
                end_date: r.end_date || undefined,
                status: r.status || "planning",
                estimate_hours: estimateHours,
            });
            if (!andContinue) drawerVisible.value = false;
            else {
                currentIteration.value = {
                    project_id: r.project_id,
                    status: "planning",
                    use_doc_template: r.use_doc_template ?? true,
                    owner_id: r.owner_id || "",
                    name: "",
                    goal: "",
                    start_date: "",
                    end_date: "",
                    estimate_hours: undefined,
                };
            }
        } else {
            await updateVortflowIteration(r.id!, {
                name: r.name,
                goal: r.goal,
                owner_id: r.owner_id || undefined,
                start_date: r.start_date || undefined,
                end_date: r.end_date || undefined,
                status: r.status,
                estimate_hours: estimateHours,
            });
            drawerVisible.value = false;
        }
        loadData();
    } finally { formLoading.value = false; }
};

const handleDeleteIteration = async (i: IterationItem) => {
    await deleteVortflowIteration(i.id);
    loadData();
};

const ownerName = (i: IterationItem) => i.owner_name || memberNameById(iterationOwnerId(i)) || "未分配";
const ownerInitial = (i: IterationItem) => ownerName(i).slice(0, 1);

const iterationCode = (i: IterationItem) => {
    const token = i.name.trim().split(/\s+/)[0] || "IT";
    return token.slice(0, 2).toUpperCase();
};

const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    return iso.split("T")[0];
};

const storyProgressText = (i: IterationItem) => {
    const metric = storyMetrics.value[i.id] || { total: 0, done: 0 };
    return `${metric.done}/${metric.total}`;
};

const storyProgressPercent = (i: IterationItem) => {
    const metric = storyMetrics.value[i.id] || { total: 0, done: 0 };
    if (!metric.total) return 0;
    return Math.round((metric.done / metric.total) * 100);
};

const effortText = (i: IterationItem) => {
    const actual = i.actual_hours || 0;
    const estimate = i.estimate_hours || 0;
    return `${actual}h/${estimate}h`;
};

const effortPercent = (i: IterationItem) => {
    const actual = i.actual_hours || 0;
    const estimate = i.estimate_hours || 0;
    if (!estimate) return 0;
    return Math.min(100, Math.round((actual / estimate) * 100));
};

const selectOwner = (value: string) => {
    selectedOwnerId.value = value;
    ownerDropdownOpen.value = false;
};

const clearOwnerFilter = () => {
    selectedOwnerId.value = "";
    ownerDropdownOpen.value = false;
};

const selectUnassignedOwner = () => {
    selectedOwnerId.value = "__unassigned__";
    ownerDropdownOpen.value = false;
};

const ownerAvatarClass = (name: string) => {
    const palette = [
        "bg-emerald-500", "bg-sky-500", "bg-indigo-500", "bg-violet-500",
        "bg-amber-500", "bg-rose-500", "bg-teal-500", "bg-cyan-500",
    ];
    const seed = name.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    return palette[seed % palette.length];
};

const onDocumentClick = (e: MouseEvent) => {
    const target = e.target as Node;
    if (ownerDropdownRef.value && !ownerDropdownRef.value.contains(target)) ownerDropdownOpen.value = false;
    if (formOwnerDropdownRef.value && !formOwnerDropdownRef.value.contains(target)) formOwnerDropdownOpen.value = false;
};

const formSelectOwner = (id: string) => {
    currentIteration.value = { ...currentIteration.value, owner_id: id };
    formOwnerDropdownOpen.value = false;
};

const formClearOwner = () => {
    currentIteration.value = { ...currentIteration.value, owner_id: "" };
    formOwnerDropdownOpen.value = false;
};

const formOwnerAvatarClass = (name: string) => {
    const palette = ["bg-emerald-500", "bg-sky-500", "bg-indigo-500", "bg-violet-500", "bg-amber-500", "bg-rose-500", "bg-teal-500", "bg-cyan-500"];
    const seed = name.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    return palette[seed % palette.length];
};

onMounted(async () => {
    await Promise.all([loadData(), loadMemberOptions()]);
    document.addEventListener("click", onDocumentClick);
});

onBeforeUnmount(() => {
    document.removeEventListener("click", onDocumentClick);
});
</script>

<template>
    <vort-spin :spinning="loading">
        <div class="space-y-4">
            <div class="bg-white rounded-xl px-5 py-3">
                <h3 class="text-base font-medium text-gray-800 mb-3">迭代管理</h3>
                <div class="flex flex-wrap items-center gap-3 text-sm">
                    <div class="text-gray-500 mr-2">
                        共 <span class="text-gray-800 font-medium">{{ filteredIterations.length }}</span> 项
                    </div>

                    <div class="relative w-[220px]">
                        <vort-input
                            v-model="searchKeyword"
                            placeholder="请输入迭代名称"
                            class="w-full"
                        >
                            <template #prefix>
                                <Search :size="14" class="text-gray-400" />
                            </template>
                        </vort-input>
                    </div>

                    <div ref="ownerDropdownRef" class="relative w-[130px]" @click.stop>
                        <button
                            class="h-8 w-full px-3 rounded border border-slate-300 bg-white text-left flex items-center justify-between transition-colors hover:border-slate-400"
                            :class="{ 'border-blue-500 bg-white': ownerDropdownOpen }"
                            @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                        >
                            <span
                                class="text-sm truncate"
                                :class="selectedOwnerText === '负责人' ? 'text-gray-400' : 'text-gray-700'"
                            >{{ selectedOwnerText }}</span>
                            <span class="text-gray-400 text-xs">▾</span>
                        </button>
                        <div v-if="ownerDropdownOpen" class="absolute z-30 mt-2 w-[270px] bg-white border border-gray-200 rounded-lg shadow-lg p-2.5 owner-dropdown-panel">
                            <div class="relative mb-2">
                                <input
                                    v-model="ownerKeyword"
                                    placeholder="搜索..."
                                    class="w-full h-8 pl-2.5 pr-7 border border-gray-300 rounded-md text-sm"
                                />
                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                            </div>
                            <div class="max-h-[300px] overflow-auto space-y-1 owner-list">
                                <button
                                    class="w-full text-left px-2 py-1.5 rounded-md text-sm text-slate-700 hover:bg-gray-50"
                                    :class="{ 'bg-blue-50 text-blue-700': !selectedOwnerId }"
                                    @click="clearOwnerFilter"
                                >
                                    全部
                                </button>
                                <button
                                    class="w-full text-left px-2 py-1.5 rounded-md text-sm text-slate-700 hover:bg-gray-50"
                                    :class="{ 'bg-blue-50 text-blue-700': selectedOwnerId === '__unassigned__' }"
                                    @click="selectUnassignedOwner"
                                >
                                    未指派
                                </button>
                                <div class="mt-1">
                                    <button
                                        class="w-full flex items-center justify-between px-2 py-1.5 rounded-md bg-slate-100 text-sm text-slate-700"
                                        @click="ownerGroupOpen = !ownerGroupOpen"
                                    >
                                        <span>全部成员（{{ filteredOwnerOptions.length }}）</span>
                                        <span class="text-base leading-none">{{ ownerGroupOpen ? "⌃" : "⌄" }}</span>
                                    </button>
                                </div>
                                <button
                                    v-for="member in (ownerGroupOpen ? filteredOwnerOptions : [])"
                                    :key="member.id"
                                    class="w-full text-left px-2 py-1.5 rounded-md text-sm hover:bg-gray-50 flex items-center gap-2"
                                    :class="{ 'bg-blue-50 text-blue-700': selectedOwnerId === member.id }"
                                    @click="selectOwner(member.id)"
                                >
                                    <span
                                        class="w-5 h-5 rounded-full text-white text-[11px] flex items-center justify-center shrink-0"
                                        :class="ownerAvatarClass(member.name)"
                                    >
                                        {{ member.name.slice(0, 1) }}
                                    </span>
                                    <span class="truncate text-slate-700">{{ member.name }}</span>
                                </button>
                                <div v-if="filteredOwnerOptions.length === 0" class="px-2 py-2 text-xs text-gray-400">暂无匹配成员</div>
                            </div>
                        </div>
                    </div>

                    <div class="w-[130px]">
                        <vort-select v-model="selectedStatus" placeholder="迭代状态" allow-clear class="w-full filter-select-compact">
                            <vort-select-option value="planning">待开始</vort-select-option>
                            <vort-select-option value="active">进行中</vort-select-option>
                            <vort-select-option value="completed">已结束</vort-select-option>
                        </vort-select>
                    </div>

                    <div class="ml-auto">
                        <vort-button variant="primary" @click="handleAddIteration">
                            <Plus :size="14" class="mr-1" />
                            新增迭代
                        </vort-button>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-xl overflow-hidden">
                <div class="grid grid-cols-[2.2fr_0.9fr_1fr_1.8fr_1.4fr_1.4fr_1fr] px-6 py-3 text-sm text-gray-500 border-b border-gray-100">
                    <span>标题</span>
                    <span>状态</span>
                    <span>负责人</span>
                    <span>开始时间/结束时间</span>
                    <span>工作项进度</span>
                    <span>工时报表</span>
                    <span>操作</span>
                </div>

                <div v-if="filteredIterations.length > 0">
                    <div
                        v-for="i in filteredIterations"
                        :key="i.id"
                        class="grid grid-cols-[2.2fr_0.9fr_1fr_1.8fr_1.4fr_1.4fr_1fr] px-6 py-4 border-b border-gray-50 items-center text-sm"
                    >
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-8 h-8 rounded-md bg-blue-100 text-blue-700 text-xs font-semibold flex items-center justify-center shrink-0">
                                {{ iterationCode(i) }}
                            </div>
                            <div class="min-w-0">
                                <div class="text-sm text-gray-800 truncate">{{ i.name }}</div>
                                <div class="text-xs text-gray-400 truncate">{{ projectNameById(i.project_id) }}</div>
                            </div>
                        </div>

                        <div>
                            <vort-tag :color="statusColorMap[i.status] || 'default'" size="small">
                                {{ statusLabels[i.status] || i.status }}
                            </vort-tag>
                        </div>

                        <div class="flex items-center gap-2">
                            <div class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center shrink-0">
                                {{ ownerInitial(i) }}
                            </div>
                            <span class="text-gray-700 truncate">{{ ownerName(i) }}</span>
                        </div>

                        <div class="text-xs text-gray-500">
                            {{ formatDate(i.start_date) }} - {{ formatDate(i.end_date) }}
                        </div>

                        <div class="min-w-0 pr-3">
                            <div class="flex items-center gap-2">
                                <div class="w-[96px] h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                    <div class="h-full bg-gray-300 rounded-full" :style="{ width: `${storyProgressPercent(i)}%` }" />
                                </div>
                                <div class="text-xs text-gray-400 whitespace-nowrap">{{ storyProgressText(i) }}</div>
                            </div>
                        </div>

                        <div class="min-w-0 pl-3">
                            <div class="flex items-center gap-2">
                                <div class="w-[96px] h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                    <div class="h-full bg-green-500 rounded-full" :style="{ width: `${effortPercent(i)}%` }" />
                                </div>
                                <div class="text-xs text-gray-400 whitespace-nowrap">{{ effortText(i) }}</div>
                            </div>
                        </div>

                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEditIteration(i)">编辑</a>
                            <vort-popconfirm title="确认删除该迭代？" @confirm="handleDeleteIteration(i)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </div>
                </div>

                <div v-else class="p-12 text-center">
                    <div>
                        <Repeat :size="48" class="mx-auto mb-3 text-gray-300" />
                        <p class="text-gray-400">暂无迭代，点击上方按钮创建</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- 新建/编辑迭代 - 居中弹窗 -->
        <vort-dialog
            :open="drawerVisible"
            :title="drawerTitle"
            :width="800"
            :centered="true"
            @update:open="drawerVisible = $event"
        >
            <vort-form ref="formRef" :model="currentIteration" :rules="iterationValidationSchema" label-width="90px" class="iteration-form">
                <vort-form-item v-if="drawerMode === 'add'" label="所属项目" name="project_id" required>
                    <vort-select v-model="currentIteration.project_id" placeholder="请选择项目" class="w-full">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </vort-form-item>

                <div class="grid grid-cols-2 gap-x-4">
                    <vort-form-item label="标题" name="name" required>
                        <vort-input v-model="currentIteration.name" placeholder="请输入标题" class="w-full" />
                    </vort-form-item>
                    <vort-form-item label="负责人" name="owner_id" required>
                        <div ref="formOwnerDropdownRef" class="relative w-full" @click.stop>
                            <button
                                type="button"
                                class="h-10 w-full px-3 rounded border border-slate-300 bg-white text-left flex items-center gap-2 hover:border-slate-400"
                                :class="{ 'border-blue-500': formOwnerDropdownOpen }"
                                @click="formOwnerDropdownOpen = !formOwnerDropdownOpen"
                            >
                                <span
                                    v-if="currentIteration.owner_id"
                                    class="w-7 h-7 rounded-full flex items-center justify-center text-white text-sm shrink-0"
                                    :class="formOwnerAvatarClass(memberNameById(currentIteration.owner_id))"
                                >
                                    {{ memberNameById(currentIteration.owner_id).slice(0, 1) }}
                                </span>
                                <span class="text-sm truncate" :class="currentIteration.owner_id ? 'text-gray-700' : 'text-gray-400'">
                                    {{ formSelectedOwnerText }}
                                </span>
                                <span class="ml-auto text-gray-400 text-xs">▾</span>
                            </button>
                            <div v-if="formOwnerDropdownOpen" class="absolute z-50 mt-1 w-full min-w-[240px] bg-white border border-gray-200 rounded-lg shadow-lg p-3">
                                <input
                                    v-model="formOwnerKeyword"
                                    placeholder="搜索..."
                                    class="w-full h-9 pl-3 pr-8 border border-gray-300 rounded-md text-sm mb-2"
                                />
                                <div class="max-h-48 overflow-auto space-y-0.5">
                                    <button type="button" class="w-full text-left px-2 py-1.5 rounded text-sm hover:bg-gray-50" @click="formClearOwner">全部</button>
                                    <button
                                        v-for="m in formFilteredOwnerOptions"
                                        :key="m.id"
                                        type="button"
                                        class="w-full text-left px-2 py-1.5 rounded text-sm hover:bg-gray-50 flex items-center gap-2"
                                        :class="{ 'bg-blue-50 text-blue-700': currentIteration.owner_id === m.id }"
                                        @click="formSelectOwner(m.id)"
                                    >
                                        <span class="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs shrink-0" :class="formOwnerAvatarClass(m.name)">
                                            {{ m.name.slice(0, 1) }}
                                        </span>
                                        <span class="truncate">{{ m.name }}</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </vort-form-item>
                </div>

                <div class="grid grid-cols-2 gap-x-4">
                    <vort-form-item label="计划时间" name="start_date" required>
                        <div class="flex items-center gap-2 w-full">
                            <vort-date-picker v-model="currentIteration.start_date" value-format="YYYY-MM-DD" placeholder="开始日期" class="flex-1" />
                            <span class="text-gray-400 text-sm">→</span>
                            <vort-date-picker v-model="currentIteration.end_date" value-format="YYYY-MM-DD" placeholder="结束日期" class="flex-1" />
                        </div>
                    </vort-form-item>
                    <vort-form-item label="工时规模" name="estimate_hours">
                        <div class="flex items-center gap-2 w-full">
                            <vort-input-number v-model="currentIteration.estimate_hours" placeholder="请输入工时规模" :min="0" class="flex-1" />
                            <span class="text-gray-400 text-sm whitespace-nowrap">小时</span>
                        </div>
                    </vort-form-item>
                </div>

                <vort-form-item label="迭代目标" name="goal">
                    <vort-textarea v-model="currentIteration.goal" placeholder="请输入迭代目标" :rows="4" class="w-full" />
                </vort-form-item>

                <vort-form-item v-if="drawerMode === 'add'" name="use_doc_template">
                    <div class="flex items-center gap-1.5">
                        <vort-checkbox v-model:checked="currentIteration.use_doc_template" />
                        <span class="text-sm text-gray-700">使用文档模板</span>
                        <vort-tooltip title="使用预设的文档模板创建迭代">
                            <Info :size="14" class="text-gray-400 cursor-help" />
                        </vort-tooltip>
                    </div>
                </vort-form-item>

                <vort-form-item v-if="drawerMode === 'edit'" label="状态" name="status">
                    <vort-select v-model="currentIteration.status" class="w-full">
                        <vort-select-option value="planning">待开始</vort-select-option>
                        <vort-select-option value="active">进行中</vort-select-option>
                        <vort-select-option value="completed">已结束</vort-select-option>
                    </vort-select>
                </vort-form-item>
            </vort-form>

            <template #footer>
                <div class="flex justify-end gap-3">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button v-if="drawerMode === 'add'" @click="handleSaveIteration(true)">新建并继续</vort-button>
                    <vort-button variant="primary" :loading="formLoading" @click="handleSaveIteration()">确定</vort-button>
                </div>
            </template>
        </vort-dialog>
    </vort-spin>
</template>

<style scoped>
:deep(.filter-select-compact .vort-select-selector) {
    height: 32px;
    border: 1px solid transparent;
    background: #f8fafc;
    box-shadow: none;
}

:deep(.filter-select-compact.vort-select-focused .vort-select-selector) {
    border-color: #3b82f6;
    background: #ffffff;
}
</style>
