<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import { getVortflowTasks } from "@/api";

interface TaskItem {
    id: string;
    title: string;
    state: string;
    task_type: string;
    estimate_hours: number | null;
    actual_hours: number | null;
    deadline: string | null;
    description?: string;
    created_at?: string | null;
}

type FilterParams = { page: number; size: number; state: string };

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

const typeMap: Record<string, { label: string; color: string }> = {
    frontend: { label: "前端", color: "cyan" },
    backend: { label: "后端", color: "blue" },
    fullstack: { label: "全栈", color: "purple" },
    test: { label: "测试", color: "orange" },
};

const stateLabel = (val: string) => stateOptions.find(o => o.value === val)?.label || val;

const fetchTasks = async (params: FilterParams) => {
    const res = await getVortflowTasks({ state: params.state, page: params.page, page_size: params.size });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, rowSelection, loadData, onSearchSubmit, resetParams } =
    useCrudPage<TaskItem, FilterParams>({
        api: fetchTasks,
        defaultParams: { page: 1, size: 20, state: "" },
    });

// Drawer
const drawerVisible = ref(false);
const currentRow = ref<Partial<TaskItem>>({});

const handleView = (row: TaskItem) => {
    currentRow.value = { ...row };
    drawerVisible.value = true;
};

loadData();
</script>

<template>
    <div class="space-y-4">
        <!-- Search -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">任务管理</h3>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.state" placeholder="全部" allow-clear class="flex-1 sm:w-[160px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in stateOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
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
                <vort-table-column label="操作" :width="80" fixed="right">
                    <template #default="{ row }">
                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                    </template>
                </vort-table-column>
            </vort-table>

            <div v-if="showPagination" class="flex justify-end mt-4">
                <vort-pagination
                    v-model:current="filterParams.page"
                    v-model:page-size="filterParams.size"
                    :total="total"
                    show-total-info
                    show-size-changer
                    @change="loadData"
                />
            </div>
        </div>

        <!-- Drawer -->
        <vort-drawer v-model:open="drawerVisible" title="任务详情" :width="550">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
        </vort-drawer>
    </div>
</template>
