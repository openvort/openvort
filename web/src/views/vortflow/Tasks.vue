<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import {
    getVortflowTasks, getVortflowStories, createVortflowTask,
    updateVortflowTask, deleteVortflowTask, transitionVortflowTask,
    getVortflowTaskTransitions,
} from "@/api";
import { Plus, ArrowRight } from "lucide-vue-next";

interface TaskItem {
    id: string;
    title: string;
    description?: string;
    state: string;
    task_type: string;
    story_id: string;
    assignee_id: string | null;
    estimate_hours: number | null;
    actual_hours: number | null;
    deadline: string | null;
    created_at?: string | null;
}

type FilterParams = { page: number; size: number; state: string; task_type: string; keyword: string };

const stateOptions = [
    { label: "全部", value: "" },
    { label: "待办", value: "todo" },
    { label: "进行中", value: "in_progress" },
    { label: "已完成", value: "done" },
    { label: "已关闭", value: "closed" },
];

const stateColorMap: Record<string, string> = {
    todo: "default", in_progress: "processing", done: "green", closed: "default",
};

const typeOptions = [
    { label: "全部", value: "" },
    { label: "前端", value: "frontend" },
    { label: "后端", value: "backend" },
    { label: "全栈", value: "fullstack" },
    { label: "测试", value: "test" },
];

const typeMap: Record<string, { label: string; color: string }> = {
    frontend: { label: "前端", color: "cyan" },
    backend: { label: "后端", color: "blue" },
    fullstack: { label: "全栈", color: "purple" },
    test: { label: "测试", color: "orange" },
};

const stateLabel = (val: string) => stateOptions.find(o => o.value === val)?.label || val;

// Stories for form select
const stories = ref<{ id: string; title: string }[]>([]);
const loadStories = async () => {
    try {
        const res = await getVortflowStories({ page: 1, page_size: 100 });
        stories.value = ((res as any)?.items || []).map((s: any) => ({ id: s.id, title: s.title }));
    } catch { /* silent */ }
};
loadStories();

// CRUD
const fetchTasks = async (params: FilterParams) => {
    const res = await getVortflowTasks({
        state: params.state, task_type: params.task_type,
        keyword: params.keyword, page: params.page, page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, rowSelection, loadData, onSearchSubmit, resetParams } =
    useCrudPage<TaskItem, FilterParams>({
        api: fetchTasks,
        defaultParams: { page: 1, size: 20, state: "", task_type: "", keyword: "" },
    });

// Drawer
const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<TaskItem>>({});
const formLoading = ref(false);

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "新增任务";
    currentRow.value = { task_type: "fullstack", story_id: stories.value[0]?.id || "" };
    drawerVisible.value = true;
};
const handleEdit = (row: TaskItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑任务";
    currentRow.value = { ...row, deadline: row.deadline ? row.deadline.split("T")[0] : "" };
    drawerVisible.value = true;
};
const handleView = (row: TaskItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "任务详情";
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
            await createVortflowTask({
                story_id: r.story_id!, title: r.title!,
                description: r.description, task_type: r.task_type,
                estimate_hours: r.estimate_hours || undefined,
                deadline: r.deadline || undefined,
            });
        } else {
            await updateVortflowTask(r.id!, {
                title: r.title, description: r.description,
                task_type: r.task_type, estimate_hours: r.estimate_hours,
                actual_hours: r.actual_hours, deadline: r.deadline || undefined,
            });
        }
        drawerVisible.value = false;
        loadData();
    } finally {
        formLoading.value = false;
    }
};

const handleDelete = async (row: TaskItem) => {
    await deleteVortflowTask(row.id);
    loadData();
};

// Transitions
const allowedTransitions = ref<string[]>([]);
const transitionLoading = ref(false);

const loadTransitions = async (id: string) => {
    try {
        const res = await getVortflowTaskTransitions(id);
        allowedTransitions.value = (res as any).transitions || [];
    } catch { allowedTransitions.value = []; }
};

const handleTransition = async (row: TaskItem, targetState: string) => {
    transitionLoading.value = true;
    try {
        await transitionVortflowTask(row.id, targetState);
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
                <h3 class="text-base font-medium text-gray-800">任务管理</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增任务
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4 flex-wrap">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索任务..." allow-clear class="flex-1 sm:w-[200px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.state" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">类型</span>
                    <vort-select v-model="filterParams.task_type" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
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
                <vort-table-column label="类型" :width="80">
                    <template #default="{ row }">
                        <vort-tag :color="typeMap[row.task_type]?.color || 'default'">{{ typeMap[row.task_type]?.label || row.task_type }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="状态" :width="90">
                    <template #default="{ row }">
                        <vort-tag :color="stateColorMap[row.state] || 'default'">{{ stateLabel(row.state) }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="预估(h)" :width="80">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ row.estimate_hours ?? '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="实际(h)" :width="80">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ row.actual_hours ?? '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="截止日期" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ row.deadline ? row.deadline.split('T')[0] : '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该任务？" @confirm="handleDelete(row)">
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
                        <span class="text-sm text-gray-400">类型</span>
                        <div class="mt-1"><vort-tag :color="typeMap[currentRow.task_type!]?.color || 'default'">{{ typeMap[currentRow.task_type!]?.label || currentRow.task_type }}</vort-tag></div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">状态</span>
                        <div class="mt-1"><vort-tag :color="stateColorMap[currentRow.state!] || 'default'">{{ stateLabel(currentRow.state || '') }}</vort-tag></div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">预估工时</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.estimate_hours ?? '-' }} h</div>
                    </div>
                    <div>
                        <span class="text-sm text-gray-400">实际工时</span>
                        <div class="text-sm text-gray-800 mt-1">{{ currentRow.actual_hours ?? '-' }} h</div>
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
                <div v-if="allowedTransitions.length" class="border-t pt-4">
                    <span class="text-sm text-gray-500 mb-2 block">状态流转</span>
                    <div class="flex flex-wrap gap-2">
                        <vort-button v-for="t in allowedTransitions" :key="t" size="small" :loading="transitionLoading" @click="handleTransition(currentRow as TaskItem, t)">
                            <ArrowRight :size="12" class="mr-1" /> {{ stateLabel(t) }}
                        </vort-button>
                    </div>
                </div>
            </div>
            <!-- Edit / Add -->
            <template v-else>
                <vort-form label-width="80px">
                    <vort-form-item label="所属需求" required>
                        <vort-select v-model="currentRow.story_id" placeholder="选择需求" :disabled="drawerMode === 'edit'" class="w-full">
                            <vort-select-option v-for="s in stories" :key="s.id" :value="s.id">{{ s.title }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="标题" required>
                        <vort-input v-model="currentRow.title" placeholder="请输入任务标题" />
                    </vort-form-item>
                    <vort-form-item label="类型">
                        <vort-select v-model="currentRow.task_type" class="w-full">
                            <vort-select-option value="frontend">前端</vort-select-option>
                            <vort-select-option value="backend">后端</vort-select-option>
                            <vort-select-option value="fullstack">全栈</vort-select-option>
                            <vort-select-option value="test">测试</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="预估工时">
                        <vort-input-number v-model="currentRow.estimate_hours" placeholder="小时" :min="0" class="w-full" />
                    </vort-form-item>
                    <vort-form-item v-if="drawerMode === 'edit'" label="实际工时">
                        <vort-input-number v-model="currentRow.actual_hours" placeholder="小时" :min="0" class="w-full" />
                    </vort-form-item>
                    <vort-form-item label="截止日期">
                        <vort-date-picker v-model="currentRow.deadline" value-format="YYYY-MM-DD" placeholder="请选择截止日期" class="w-full" />
                    </vort-form-item>
                    <vort-form-item label="描述">
                        <vort-textarea v-model="currentRow.description" placeholder="请输入任务描述" :rows="4" />
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
