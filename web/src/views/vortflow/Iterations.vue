<script setup lang="ts">
import { ref, onMounted, computed, onBeforeUnmount } from "vue";
import { z } from "zod";
import { useRouter } from "vue-router";
import { Repeat, Plus, Search } from "lucide-vue-next";
import {
    getVortflowIterations, createVortflowIteration, updateVortflowIteration, deleteVortflowIteration,
    getVortflowProjects, getVortflowIterationStories, getMembers,
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

const router = useRouter();
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

const statusColorMap: Record<string, string> = {
    planning: "default", active: "processing", completed: "green"
};
const statusLabels: Record<string, string> = {
    planning: "待开始", active: "进行中", completed: "已结束"
};

const filteredIterations = computed(() => {
    let list = iterations.value;
    if (selectedOwnerId.value) list = list.filter(i => iterationOwnerId(i) === selectedOwnerId.value);
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
        const iterList = ((iterRes as any)?.items || []);
        iterations.value = iterList;
        projects.value = ((projRes as any)?.items || []);

        const settled = await Promise.allSettled(
            iterList.map((it: IterationItem) => getVortflowIterationStories(it.id))
        );
        const metrics: Record<string, { total: number; done: number }> = {};
        settled.forEach((result, idx) => {
            const id = iterList[idx].id;
            if (result.status !== "fulfilled") {
                metrics[id] = { total: 0, done: 0 };
                return;
            }
            const items = ((result.value as any)?.items || []) as Array<{ state?: string }>;
            const done = items.filter(s => ["done", "closed", "accepted", "released"].includes(s.state || "")).length;
            metrics[id] = { total: items.length, done };
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
    name: z.string().min(1, "迭代名称不能为空"),
    goal: z.string().optional(),
    start_date: z.string().optional(),
    end_date: z.string().optional(),
    status: z.string().optional(),
});

const handleAddIteration = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增迭代";
    currentIteration.value = { status: "planning" };
    drawerVisible.value = true;
};

const handleEditIteration = (i: IterationItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑迭代";
    currentIteration.value = {
        ...i,
        start_date: i.start_date ? i.start_date.split("T")[0] : "",
        end_date: i.end_date ? i.end_date.split("T")[0] : "",
    };
    drawerVisible.value = true;
};

const handleSaveIteration = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    const r = currentIteration.value;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowIteration({
                project_id: r.project_id!,
                name: r.name!,
                goal: r.goal || "",
                start_date: r.start_date || undefined,
                end_date: r.end_date || undefined,
                status: r.status || "planning",
            });
        } else {
            await updateVortflowIteration(r.id!, {
                name: r.name,
                goal: r.goal,
                start_date: r.start_date || undefined,
                end_date: r.end_date || undefined,
                status: r.status,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally { formLoading.value = false; }
};

const handleDeleteIteration = async (i: IterationItem) => {
    await deleteVortflowIteration(i.id);
    loadData();
};

const handleViewStories = (i: IterationItem) => {
    router.push(`/vortflow/iterations/${i.id}/stories`);
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

const onDocumentClick = (e: MouseEvent) => {
    if (!ownerDropdownRef.value) return;
    const target = e.target as Node;
    if (!ownerDropdownRef.value.contains(target)) ownerDropdownOpen.value = false;
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
                            class="h-8 w-full px-3 rounded border border-transparent bg-gray-50 hover:bg-gray-100 text-left flex items-center justify-between"
                            :class="{ 'border-blue-500 bg-white': ownerDropdownOpen }"
                            @click.stop="ownerDropdownOpen = !ownerDropdownOpen"
                        >
                            <span class="text-sm text-gray-700 truncate">{{ selectedOwnerText }}</span>
                            <span class="text-gray-400 text-xs">▾</span>
                        </button>
                        <div v-if="ownerDropdownOpen" class="absolute z-30 mt-1 w-[260px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                            <div class="relative mb-2">
                                <input
                                    v-model="ownerKeyword"
                                    placeholder="搜索负责人"
                                    class="w-full h-8 pl-3 pr-8 border border-gray-300 rounded-md text-sm"
                                />
                                <span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 text-sm">⌕</span>
                            </div>
                            <div class="max-h-64 overflow-auto space-y-1">
                                <button
                                    class="w-full text-left px-2 py-1.5 rounded text-sm hover:bg-gray-50"
                                    :class="{ 'bg-blue-50 text-blue-700': !selectedOwnerId }"
                                    @click="clearOwnerFilter"
                                >
                                    全部
                                </button>
                                <button
                                    v-for="member in filteredOwnerOptions"
                                    :key="member.id"
                                    class="w-full text-left px-2 py-1.5 rounded text-sm hover:bg-gray-50 flex items-center gap-2"
                                    :class="{ 'bg-blue-50 text-blue-700': selectedOwnerId === member.id }"
                                    @click="selectOwner(member.id)"
                                >
                                    <span class="w-6 h-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center shrink-0">
                                        {{ member.name.slice(0, 1) }}
                                    </span>
                                    <span class="truncate">{{ member.name }}</span>
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
                <div class="grid grid-cols-[2.4fr_0.9fr_1.1fr_2fr_1.2fr_1.1fr_1fr] px-6 py-3 text-xs text-gray-500 border-b border-gray-100 bg-gray-50">
                    <span>标题</span>
                    <span>状态</span>
                    <span>负责人</span>
                    <span>开始时间/结束时间</span>
                    <span>工作项进度</span>
                    <span>工时报表</span>
                    <span class="text-right">操作</span>
                </div>

                <div v-if="filteredIterations.length > 0">
                    <div
                        v-for="i in filteredIterations"
                        :key="i.id"
                        class="grid grid-cols-[2.4fr_0.9fr_1.1fr_2fr_1.2fr_1.1fr_1fr] px-6 py-4 border-b border-gray-50 items-center text-sm"
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

                        <div>
                            <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div class="h-full bg-gray-300 rounded-full" :style="{ width: `${storyProgressPercent(i)}%` }" />
                            </div>
                            <div class="mt-1 text-xs text-gray-400">{{ storyProgressText(i) }}</div>
                        </div>

                        <div>
                            <div class="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div class="h-full bg-green-500 rounded-full" :style="{ width: `${effortPercent(i)}%` }" />
                            </div>
                            <div class="mt-1 text-xs text-gray-400">{{ effortText(i) }}</div>
                        </div>

                        <div class="flex items-center justify-end gap-2 whitespace-nowrap">
                            <a class="text-xs text-blue-600 cursor-pointer" @click="handleViewStories(i)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-xs text-blue-600 cursor-pointer" @click="handleEditIteration(i)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该迭代？" @confirm="handleDeleteIteration(i)">
                                <a class="text-xs text-red-500 cursor-pointer">删除</a>
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

        <!-- Drawer -->
        <vort-drawer :open="drawerVisible" :title="drawerTitle" :width="500" @update:open="drawerVisible = $event">
            <vort-form ref="formRef" :model="currentIteration" :rules="iterationValidationSchema" label-width="80px">
                <vort-form-item label="所属项目" name="project_id" required>
                    <vort-select v-model="currentIteration.project_id" placeholder="请选择项目" :disabled="drawerMode === 'edit'" class="w-full">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </vort-form-item>
                <vort-form-item label="迭代名称" name="name" required>
                    <vort-input v-model="currentIteration.name" placeholder="如：Sprint 1" />
                </vort-form-item>
                <vort-form-item label="迭代目标" name="goal">
                    <vort-textarea v-model="currentIteration.goal" placeholder="迭代目标描述" :rows="3" />
                </vort-form-item>
                <vort-form-item label="开始日期" name="start_date">
                    <vort-date-picker v-model="currentIteration.start_date" value-format="YYYY-MM-DD" placeholder="请选择开始日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="结束日期" name="end_date">
                    <vort-date-picker v-model="currentIteration.end_date" value-format="YYYY-MM-DD" placeholder="请选择结束日期" class="w-full" />
                </vort-form-item>
                <vort-form-item label="状态" name="status">
                    <vort-select v-model="currentIteration.status" class="w-full">
                        <vort-select-option value="planning">待开始</vort-select-option>
                        <vort-select-option value="active">进行中</vort-select-option>
                        <vort-select-option value="completed">已结束</vort-select-option>
                    </vort-select>
                </vort-form-item>
            </vort-form>
            <div class="flex justify-end gap-3 mt-6">
                <vort-button @click="drawerVisible = false">取消</vort-button>
                <vort-button variant="primary" :loading="formLoading" @click="handleSaveIteration">确定</vort-button>
            </div>
        </vort-drawer>
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
