<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, Ellipsis } from "lucide-vue-next";
import { useCrudPage } from "@/hooks";
import { useVortFlowStore } from "@/stores";
import { Dropdown, DropdownMenuItem } from "@/components/vort";
import { message } from "@/components/vort/message";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import TestPlanEditDialog from "./components/TestPlanEditDialog.vue";
import {
    getVortflowTestPlans,
    deleteVortflowTestPlan,
    updateVortflowTestPlan,
    copyVortflowTestPlan,
} from "@/api";

interface TestPlanItem {
    id: string;
    project_id: string;
    title: string;
    description: string;
    status: string;
    owner_id: string | null;
    owner_name: string;
    iteration_id: string | null;
    iteration_name: string;
    version_id: string | null;
    version_name: string;
    start_date: string | null;
    end_date: string | null;
    total_cases: number;
    executed_cases: number;
    passed: number;
    failed: number;
    blocked: number;
    skipped: number;
    created_at: string | null;
}

type FilterParams = { page: number; size: number; keyword: string; status: string };

const router = useRouter();
const vortFlowStore = useVortFlowStore();

const {
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
} = useWorkItemCommon();

const statusOptions = [
    { label: "全部", value: "" },
    { label: "进行中", value: "in_progress" },
    { label: "已完成", value: "completed" },
    { label: "已挂起", value: "suspended" },
];
const statusColorMap: Record<string, string> = {
    in_progress: "processing",
    completed: "green",
    suspended: "default",
    planning: "default",
};
const statusLabels: Record<string, string> = {
    planning: "待开始",
    in_progress: "进行中",
    completed: "已完成",
    suspended: "已挂起",
};

const fetchList = async (params: FilterParams) => {
    const projectId = vortFlowStore.selectedProjectId || undefined;
    const res = await getVortflowTestPlans({
        keyword: params.keyword,
        status: params.status,
        project_id: projectId,
        page: params.page,
        page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData, onSearchSubmit, resetParams } =
    useCrudPage<TestPlanItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20, keyword: "", status: "" },
    });

watch(() => vortFlowStore.selectedProjectId, () => {
    loadData();
});

// Result distribution bar
const resultBarStyle = (item: TestPlanItem) => {
    const t = item.total_cases;
    if (!t) return { passed: "0%", failed: "0%", blocked: "0%", skipped: "0%" };
    return {
        passed: `${(item.passed / t) * 100}%`,
        failed: `${(item.failed / t) * 100}%`,
        blocked: `${(item.blocked / t) * 100}%`,
        skipped: `${((t - item.passed - item.failed - item.blocked) / t) * 100}%`,
    };
};

const resultPercent = (item: TestPlanItem) => {
    if (!item.total_cases) return "0%";
    return `${Math.round((item.executed_cases / item.total_cases) * 100)}%`;
};

// Dialog
const dialogOpen = ref(false);
const editData = ref<Partial<TestPlanItem> | null>(null);

const handleAdd = () => {
    editData.value = null;
    dialogOpen.value = true;
};

const handleEdit = (row: TestPlanItem) => {
    editData.value = { ...row };
    dialogOpen.value = true;
};

const handleDelete = async (row: TestPlanItem) => {
    await deleteVortflowTestPlan(row.id);
    message.success("已删除");
    loadData();
};

const handleCopy = async (row: TestPlanItem) => {
    await copyVortflowTestPlan(row.id);
    message.success("已复制");
    loadData();
};

const handleFinish = async (row: TestPlanItem) => {
    await updateVortflowTestPlan(row.id, { status: "completed" });
    message.success("已结束");
    loadData();
};

const handleSuspend = async (row: TestPlanItem) => {
    await updateVortflowTestPlan(row.id, { status: "suspended" });
    message.success("已挂起");
    loadData();
};

onMounted(async () => {
    await Promise.all([loadMemberOptions(), loadData()]);
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">
                    测试计划
                    <span v-if="total" class="text-gray-400 font-normal text-sm ml-1">({{ total }})</span>
                </h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新建测试计划
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select
                        v-model="filterParams.status"
                        placeholder="全部"
                        allow-clear
                        class="flex-1 sm:w-[120px]"
                        @change="onSearchSubmit"
                    >
                        <vort-select-option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                        </vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <vort-input-search
                        v-model="filterParams.keyword"
                        placeholder="请输入关键字"
                        allow-clear
                        class="flex-1 sm:w-[220px]"
                        @search="onSearchSubmit"
                        @keyup.enter="onSearchSubmit"
                    />
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false">
                <vort-table-column label="标题" :min-width="200">
                    <template #default="{ row }">
                        <a
                            class="text-sm text-blue-600 cursor-pointer hover:underline"
                            @click="router.push(`/vortflow/test-plans/${row.id}`)"
                        >
                            {{ row.title }}
                        </a>
                    </template>
                </vort-table-column>

                <vort-table-column label="状态" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="statusColorMap[row.status] || 'default'">
                            {{ statusLabels[row.status] || row.status }}
                        </vort-tag>
                    </template>
                </vort-table-column>

                <vort-table-column label="已测" :width="80">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ row.executed_cases }} / {{ row.total_cases }}</span>
                    </template>
                </vort-table-column>

                <vort-table-column label="最新结果分布" :width="200">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2">
                            <div class="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden flex">
                                <div class="h-full bg-green-500" :style="{ width: resultBarStyle(row).passed }" />
                                <div class="h-full bg-red-500" :style="{ width: resultBarStyle(row).failed }" />
                                <div class="h-full bg-orange-400" :style="{ width: resultBarStyle(row).blocked }" />
                            </div>
                            <span class="text-xs text-gray-400 whitespace-nowrap">{{ resultPercent(row) }}</span>
                        </div>
                    </template>
                </vort-table-column>

                <vort-table-column label="关联迭代" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ row.iteration_name || "无" }}</span>
                    </template>
                </vort-table-column>

                <vort-table-column label="关联版本" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ row.version_name || "无" }}</span>
                    </template>
                </vort-table-column>

                <vort-table-column label="负责人" :width="140">
                    <template #default="{ row }">
                        <div v-if="row.owner_name" class="flex items-center gap-2">
                            <span
                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0 overflow-hidden"
                                :style="{ backgroundColor: getAvatarBg(row.owner_name) }"
                            >
                                <img
                                    v-if="getMemberAvatarUrl(row.owner_name)"
                                    :src="getMemberAvatarUrl(row.owner_name)"
                                    class="w-full h-full object-cover"
                                >
                                <template v-else>{{ getAvatarLabel(row.owner_name) }}</template>
                            </span>
                            <span class="text-sm text-gray-700 truncate">{{ row.owner_name }}</span>
                        </div>
                        <span v-else class="text-sm text-gray-400">无</span>
                    </template>
                </vort-table-column>

                <vort-table-column label="设置" :width="60" fixed="right">
                    <template #default="{ row }">
                        <Dropdown trigger="click" placement="bottomRight">
                            <a class="text-gray-400 hover:text-gray-600 cursor-pointer inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-50">
                                <Ellipsis :size="16" />
                            </a>
                            <template #overlay>
                                <DropdownMenuItem @click="handleEdit(row)">设置</DropdownMenuItem>
                                <DropdownMenuItem v-if="row.status !== 'completed'" @click="handleFinish(row)">结束计划</DropdownMenuItem>
                                <DropdownMenuItem v-if="row.status !== 'suspended'" @click="handleSuspend(row)">挂起</DropdownMenuItem>
                                <DropdownMenuItem danger @click="handleDelete(row)">删除</DropdownMenuItem>
                                <DropdownMenuItem @click="handleCopy(row)">复制</DropdownMenuItem>
                            </template>
                        </Dropdown>
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

        <TestPlanEditDialog
            v-model:open="dialogOpen"
            :edit-data="editData"
            @saved="loadData"
        />
    </div>
</template>
