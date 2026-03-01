<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import {
    getVortflowBugs, getVortflowStories, createVortflowBug,
    updateVortflowBug, deleteVortflowBug, transitionVortflowBug,
    getVortflowBugTransitions,
} from "@/api";
import { Plus, ArrowRight } from "lucide-vue-next";

interface BugItem {
    id: string;
    title: string;
    description?: string;
    state: string;
    severity: number;
    story_id: string | null;
    task_id: string | null;
    reporter_id: string | null;
    assignee_id: string | null;
    developer_id: string | null;
    created_at: string | null;
}

type FilterParams = { page: number; size: number; state: string; severity: number; keyword: string };

const stateOptions = [
    { label: "全部", value: "" },
    { label: "打开", value: "open" },
    { label: "已确认", value: "confirmed" },
    { label: "修复中", value: "fixing" },
    { label: "已解决", value: "resolved" },
    { label: "已验证", value: "verified" },
    { label: "已关闭", value: "closed" },
];

const stateColorMap: Record<string, string> = {
    open: "red", confirmed: "orange", fixing: "processing",
    resolved: "cyan", verified: "green", closed: "default",
};

const severityOptions = [
    { label: "全部", value: 0 },
    { label: "致命", value: 1 },
    { label: "严重", value: 2 },
    { label: "一般", value: 3 },
    { label: "轻微", value: 4 },
];

const severityMap: Record<number, { label: string; color: string }> = {
    1: { label: "致命", color: "red" },
    2: { label: "严重", color: "orange" },
    3: { label: "一般", color: "blue" },
    4: { label: "轻微", color: "default" },
};

const stateLabel = (val: string) => stateOptions.find(o => o.value === val)?.label || val;

// Stories for form
const stories = ref<{ id: string; title: string }[]>([]);
const loadStories = async () => {
    try {
        const res = await getVortflowStories({ page: 1, page_size: 200 });
        stories.value = ((res as any)?.items || []).map((s: any) => ({ id: s.id, title: s.title }));
    } catch { /* silent */ }
};
loadStories();

// CRUD
const fetchBugs = async (params: FilterParams) => {
    const res = await getVortflowBugs({
        state: params.state, severity: params.severity || undefined,
        keyword: params.keyword, page: params.page, page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, rowSelection, loadData, onSearchSubmit, resetParams } =
    useCrudPage<BugItem, FilterParams>({
        api: fetchBugs,
        defaultParams: { page: 1, size: 20, state: "", severity: 0, keyword: "" },
    });

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<BugItem>>({});
const formLoading = ref(false);

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增缺陷";
    currentRow.value = { severity: 3 };
    drawerVisible.value = true;
};
const handleEdit = (row: BugItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑缺陷";
    currentRow.value = { ...row };
    drawerVisible.value = true;
};
const handleView = (row: BugItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "缺陷详情";
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
            await createVortflowBug({
                story_id: r.story_id || undefined, title: r.title!,
                description: r.description, severity: r.severity,
                assignee_id: r.assignee_id || undefined,
            });
        } else {
            await updateVortflowBug(r.id!, {
                title: r.title, description: r.description,
                severity: r.severity, assignee_id: r.assignee_id || undefined,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally { formLoading.value = false; }
};

const handleDelete = async (row: BugItem) => {
    await deleteVortflowBug(row.id);
    loadData();
};

// Transitions
const allowedTransitions = ref<string[]>([]);
const transitionLoading = ref(false);

const loadTransitions = async (id: string) => {
    try {
        const res = await getVortflowBugTransitions(id);
        allowedTransitions.value = (res as any).transitions || [];
    } catch { allowedTransitions.value = []; }
};

const handleTransition = async (row: BugItem, targetState: string) => {
    transitionLoading.value = true;
    try {
        await transitionVortflowBug(row.id, targetState);
        loadData();
        if (drawerVisible.value && currentRow.value.id === row.id) {
            currentRow.value.state = targetState;
            loadTransitions(row.id);
        }
    } finally { transitionLoading.value = false; }
};

loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- Search -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">缺陷跟踪</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增缺陷
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索缺陷..." allow-clear class="flex-1 sm:w-[200px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.state" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">严重程度</span>
                    <vort-select v-model="filterParams.severity" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in severityOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
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
                <vort-table-column label="严重程度" :width="90">
                    <template #default="{ row }">
                        <vort-tag :color="severityMap[row.severity]?.color || 'default'">{{ severityMap[row.severity]?.label || '-' }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="状态" :width="90">
                    <template #default="{ row }">
                        <vort-tag :color="stateColorMap[row.state] || 'default'">{{ stateLabel(row.state) }}</vort-tag>
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
                            <vort-popconfirm title="确认删除该缺陷？" @confirm="handleDelete(row)">
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
            <!-- View -->
            <div v-if="drawerMode === 'view'">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
                    <div class="sm:col-span-2">
                        <span class="text-sm text-gray-400">标题</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.title }}</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">严重程度</span>
                        <div class="mt-1"><vort-tag :color="severityMap[currentRow.severity!]?.color || 'default'">{{ severityMap[currentRow.severity!]?.label || '-' }}</vort-tag></div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">状态</span>
                        <div class="mt-1"><vort-tag :color="stateColorMap[currentRow.state!] || 'default'">{{ stateLabel(currentRow.state || '') }}</vort-tag></div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">关联需求</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.story_id || '-' }}</div>
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
                <div v-if="allowedTransitions.length" class="border-t pt-4">
                    <span class="text-sm text-gray-500 mb-2 block">状态流转</span>
                    <div class="flex flex-wrap gap-2">
                        <vort-button v-for="t in allowedTransitions" :key="t" size="small" :loading="transitionLoading" @click="handleTransition(currentRow as BugItem, t)">
                            <ArrowRight :size="12" class="mr-1" /> {{ stateLabel(t) }}
                        </vort-button>
                    </div>
                </div>
            </div>
            <!-- Edit / Add -->
            <template v-else>
                <vort-form label-width="80px">
                    <vort-form-item label="关联需求">
                        <vort-select v-model="currentRow.story_id" placeholder="可选，关联需求" allow-clear class="w-full">
                            <vort-select-option v-for="s in stories" :key="s.id" :value="s.id">{{ s.title }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="标题" required>
                        <vort-input v-model="currentRow.title" placeholder="请输入缺陷标题" />
                    </vort-form-item>
                    <vort-form-item label="严重程度">
                        <vort-select v-model="currentRow.severity" class="w-full">
                            <vort-select-option :value="1">致命</vort-select-option>
                            <vort-select-option :value="2">严重</vort-select-option>
                            <vort-select-option :value="3">一般</vort-select-option>
                            <vort-select-option :value="4">轻微</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="描述">
                        <vort-textarea v-model="currentRow.description" placeholder="请输入缺陷描述，包括复现步骤" :rows="5" />
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
