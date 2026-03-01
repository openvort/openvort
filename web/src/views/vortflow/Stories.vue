<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import {
    getVortflowStories, getVortflowProjects, createVortflowStory,
    updateVortflowStory, deleteVortflowStory, transitionVortflowStory,
    getVortflowStoryTransitions,
} from "@/api";
import { Plus, ArrowRight } from "lucide-vue-next";

interface StoryItem {
    id: string;
    title: string;
    description?: string;
    state: string;
    priority: number;
    project_id: string;
    deadline: string | null;
    created_at: string | null;
}

type FilterParams = { page: number; size: number; state: string; keyword: string; project_id: string; priority: number };

const stateOptions = [
    { label: "全部", value: "" },
    { label: "录入", value: "intake" },
    { label: "评审", value: "review" },
    { label: "已驳回", value: "rejected" },
    { label: "产品完善", value: "pm_refine" },
    { label: "UI 设计", value: "design" },
    { label: "拆分估时", value: "breakdown" },
    { label: "分配开发", value: "dev_assign" },
    { label: "开发中", value: "in_progress" },
    { label: "测试中", value: "testing" },
    { label: "Bug 修复", value: "bugfix" },
    { label: "已完成", value: "done" },
];

const stateColorMap: Record<string, string> = {
    intake: "default", review: "processing", rejected: "red",
    pm_refine: "orange", design: "cyan", breakdown: "purple",
    dev_assign: "geekblue", in_progress: "blue", testing: "orange",
    bugfix: "volcano", done: "green",
};

const priorityOptions = [
    { label: "全部", value: 0 },
    { label: "紧急", value: 1 },
    { label: "高", value: 2 },
    { label: "中", value: 3 },
    { label: "低", value: 4 },
];

const priorityMap: Record<number, { label: string; color: string }> = {
    1: { label: "紧急", color: "red" },
    2: { label: "高", color: "orange" },
    3: { label: "中", color: "blue" },
    4: { label: "低", color: "default" },
};

const stateLabel = (val: string) => stateOptions.find(o => o.value === val)?.label || val;

// Projects for filter & form
const projects = ref<{ id: string; name: string }[]>([]);
const loadProjects = async () => {
    try {
        const res = await getVortflowProjects();
        projects.value = (res as any)?.items || [];
    } catch { /* silent */ }
};
loadProjects();

// CRUD
const fetchStories = async (params: FilterParams) => {
    const res = await getVortflowStories({
        state: params.state, keyword: params.keyword,
        project_id: params.project_id, priority: params.priority || undefined,
        page: params.page, page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, rowSelection, loadData, onSearchSubmit, resetParams } =
    useCrudPage<StoryItem, FilterParams>({
        api: fetchStories,
        defaultParams: { page: 1, size: 20, state: "", keyword: "", project_id: "", priority: 0 },
    });

// Drawer — view / edit / add
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<StoryItem>>({});
const formLoading = ref(false);

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增需求";
    currentRow.value = { priority: 3, project_id: projects.value[0]?.id || "" };
    drawerVisible.value = true;
};
const handleEdit = (row: StoryItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑需求";
    currentRow.value = { ...row, deadline: row.deadline ? row.deadline.split("T")[0] : "" };
    drawerVisible.value = true;
};
const handleView = (row: StoryItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "需求详情";
    currentRow.value = { ...row };
    drawerVisible.value = true;
    loadTransitions(row.id);
};

const handleSave = async () => {
    const r = currentRow.value;
    if (!r.title?.trim()) return;
    formLoading.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortflowStory({
                project_id: r.project_id!, title: r.title!,
                description: r.description, priority: r.priority,
                deadline: r.deadline || undefined,
            });
        } else {
            await updateVortflowStory(r.id!, {
                title: r.title, description: r.description,
                priority: r.priority, deadline: r.deadline || undefined,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally {
        formLoading.value = false;
    }
};

const handleDelete = async (row: StoryItem) => {
    await deleteVortflowStory(row.id);
    loadData();
};

// State transitions
const allowedTransitions = ref<string[]>([]);
const transitionLoading = ref(false);

const loadTransitions = async (id: string) => {
    try {
        const res = await getVortflowStoryTransitions(id);
        allowedTransitions.value = (res as any).transitions || [];
    } catch {
        allowedTransitions.value = [];
    }
};

const handleTransition = async (row: StoryItem, targetState: string) => {
    transitionLoading.value = true;
    try {
        await transitionVortflowStory(row.id, targetState);
        loadData();
        // Refresh detail if drawer is open
        if (drawerVisible.value && currentRow.value.id === row.id) {
            currentRow.value.state = targetState;
            loadTransitions(row.id);
        }
    } finally {
        transitionLoading.value = false;
    }
};

loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- Search -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">需求列表</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增需求
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索需求..." allow-clear class="flex-1 sm:w-[200px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">项目</span>
                    <vort-select v-model="filterParams.project_id" placeholder="全部项目" allow-clear class="flex-1 sm:w-[160px]" @change="onSearchSubmit">
                        <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.state" placeholder="全部" allow-clear class="flex-1 sm:w-[130px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">优先级</span>
                    <vort-select v-model="filterParams.priority" placeholder="全部" allow-clear class="flex-1 sm:w-[110px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in priorityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false" :row-selection="rowSelection">
                <vort-table-column label="标题" prop="title" />
                <vort-table-column label="状态" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="stateColorMap[row.state] || 'default'">{{ stateLabel(row.state) }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="优先级" :width="80">
                    <template #default="{ row }">
                        <vort-tag :color="priorityMap[row.priority]?.color || 'default'">{{ priorityMap[row.priority]?.label || '-' }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="截止日期" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ row.deadline ? row.deadline.split('T')[0] : '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="创建时间" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-400">{{ row.created_at ? row.created_at.split('T')[0] : '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除？关联的任务和缺陷也会被删除。" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination v-model:current="filterParams.page" v-model:page-size="filterParams.size" :total="total" show-total-info show-size-changer @change="loadData" />
            </div>
        </div>

        <!-- Drawer -->
        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="600">
            <!-- View mode -->
            <div v-if="drawerMode === 'view'">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                    <div class="sm:col-span-2">
                        <span class="text-sm text-gray-400">标题</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.title }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">状态</span>
                        <div class="mt-1"><vort-tag :color="stateColorMap[currentRow.state!] || 'default'">{{ stateLabel(currentRow.state || '') }}</vort-tag></div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">优先级</span>
                        <div class="mt-1"><vort-tag :color="priorityMap[currentRow.priority!]?.color || 'default'">{{ priorityMap[currentRow.priority!]?.label || '-' }}</vort-tag></div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">截止日期</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.deadline ? currentRow.deadline.split('T')[0] : '-' }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">创建时间</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.created_at ? currentRow.created_at.split('T')[0] : '-' }}</div>
                    </div>
                    <div v-if="currentRow.description" class="sm:col-span-2">
                        <span class="text-sm text-gray-400">描述</span>
                        <div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">{{ currentRow.description }}</div>
                    </div>
                </div>
                <!-- Transition buttons -->
                <div v-if="allowedTransitions.length" class="border-t pt-4">
                    <span class="text-sm text-gray-500 mb-2 block">状态流转</span>
                    <div class="flex flex-wrap gap-2">
                        <vort-button v-for="t in allowedTransitions" :key="t" size="small" :loading="transitionLoading" @click="handleTransition(currentRow as StoryItem, t)">
                            <ArrowRight :size="12" class="mr-1" /> {{ stateLabel(t) }}
                        </vort-button>
                    </div>
                </div>
            </div>
            <!-- Edit / Add mode -->
            <template v-else>
                <vort-form label-width="80px">
                    <vort-form-item label="项目" required>
                        <vort-select v-model="currentRow.project_id" placeholder="选择项目" :disabled="drawerMode === 'edit'" class="w-full">
                            <vort-select-option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="标题" required>
                        <vort-input v-model="currentRow.title" placeholder="请输入需求标题" />
                    </vort-form-item>
                    <vort-form-item label="优先级">
                        <vort-select v-model="currentRow.priority" class="w-full">
                            <vort-select-option :value="1">紧急</vort-select-option>
                            <vort-select-option :value="2">高</vort-select-option>
                            <vort-select-option :value="3">中</vort-select-option>
                            <vort-select-option :value="4">低</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="截止日期">
                        <vort-date-picker v-model="currentRow.deadline" value-format="YYYY-MM-DD" placeholder="请选择截止日期" class="w-full" />
                    </vort-form-item>
                    <vort-form-item label="描述">
                        <vort-textarea v-model="currentRow.description" placeholder="请输入需求描述" :rows="4" />
                    </vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button variant="primary" :loading="formLoading" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>
