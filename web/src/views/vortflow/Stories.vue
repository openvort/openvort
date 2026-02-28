<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import { getVortflowStories } from "@/api";

interface StoryItem {
    id: string;
    title: string;
    state: string;
    priority: number;
    deadline: string | null;
    created_at: string | null;
    description?: string;
}

type FilterParams = { page: number; size: number; state: string };

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

const priorityMap: Record<number, { label: string; color: string }> = {
    1: { label: "紧急", color: "red" },
    2: { label: "高", color: "orange" },
    3: { label: "中", color: "blue" },
    4: { label: "低", color: "default" },
};

const stateLabel = (val: string) => stateOptions.find(o => o.value === val)?.label || val;

const fetchStories = async (params: FilterParams) => {
    const res = await getVortflowStories({ state: params.state, page: params.page, page_size: params.size });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, rowSelection, loadData, onSearchSubmit, resetParams } =
    useCrudPage<StoryItem, FilterParams>({
        api: fetchStories,
        defaultParams: { page: 1, size: 20, state: "" },
    });

// Drawer
const drawerVisible = ref(false);
const currentRow = ref<Partial<StoryItem>>({});

const handleView = (row: StoryItem) => {
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
                <h3 class="text-base font-medium text-gray-800">需求列表</h3>
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
        <vort-drawer v-model:open="drawerVisible" title="需求详情" :width="550">
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
        </vort-drawer>
    </div>
</template>
