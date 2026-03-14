<script setup lang="ts">
import { ref, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus } from "lucide-vue-next";
import { DownOutlined } from "@/components/vort/icons";
import { useCrudPage } from "@/hooks";
import { useVortFlowStore } from "@/stores";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import IterationEditDialog from "./components/IterationEditDialog.vue";
import {
    getVortflowIterations, deleteVortflowIteration,
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

type FilterParams = { page: number; size: number; keyword: string; status: string; owner_id: string };

const router = useRouter();
const vortFlowStore = useVortFlowStore();
const filterOwnerDropdownOpen = ref(false);
const filterOwnerKeyword = ref("");

const {
    ownerGroups,
    getAvatarBg,
    getAvatarLabel,
    getMemberAvatarUrl,
    loadMemberOptions,
    getMemberIdByName,
    getMemberNameById,
} = useWorkItemCommon();

const statusOptions = [
    { label: "全部", value: "" },
    { label: "待开始", value: "planning" },
    { label: "进行中", value: "active" },
    { label: "已结束", value: "completed" },
];
const statusColorMap: Record<string, string> = { planning: "default", active: "processing", completed: "green" };
const statusLabels: Record<string, string> = { planning: "待开始", active: "进行中", completed: "已结束" };

const fetchList = async (params: FilterParams) => {
    const projectId = vortFlowStore.selectedProjectId || undefined;
    const res = await getVortflowIterations({
        keyword: params.keyword, status: params.status, owner_id: params.owner_id,
        project_id: projectId,
        page: params.page, page_size: params.size,
    });
    return { records: (res as any).items || [], total: (res as any).total || 0 };
};

const { listData, loading, total, filterParams, showPagination, loadData, onSearchSubmit, resetParams } =
    useCrudPage<IterationItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 20, keyword: "", status: "", owner_id: "" },
    });

watch(() => vortFlowStore.selectedProjectId, () => {
    loadData();
});

const iterationOwnerId = (i: IterationItem) => i.owner_id || i.assignee_id || i.pm_id || "";
const ownerName = (i: IterationItem) => i.owner_name || getMemberNameById(iterationOwnerId(i)) || "未指派";
const iterationOwnerAvatarUrl = (i: IterationItem) => {
    const name = ownerName(i);
    return name === "未指派" ? "" : getMemberAvatarUrl(name);
};
const projectNameById = (id: string) => vortFlowStore.projects.find(p => p.id === id)?.name || id;

const formatDate = (iso: string | null) => {
    if (!iso) return "-";
    return iso.split("T")[0];
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

// Dialog
const drawerVisible = ref(false);
const drawerMode = ref<"add" | "edit">("add");
const currentIteration = ref<Partial<IterationItem & { use_doc_template?: boolean }>>({});

const handleAddIteration = () => {
    drawerMode.value = "add";
    currentIteration.value = {
        project_id: vortFlowStore.selectedProjectId || "",
    };
    drawerVisible.value = true;
};

const handleEditIteration = (i: IterationItem) => {
    drawerMode.value = "edit";
    currentIteration.value = { ...i };
    drawerVisible.value = true;
};

const handleDeleteIteration = async (i: IterationItem) => {
    await deleteVortflowIteration(i.id);
    loadData();
};

const handleFilterOwnerSelect = (name: string) => {
    filterParams.owner_id = getMemberIdByName(name);
    filterOwnerDropdownOpen.value = false;
    filterOwnerKeyword.value = "";
    onSearchSubmit();
};

onMounted(async () => {
    await Promise.all([loadMemberOptions(), loadData()]);
});
</script>

<template>
    <div class="space-y-4">
        <!-- 搜索卡片 -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">迭代管理</h3>
                <vort-button variant="primary" @click="handleAddIteration">
                    <Plus :size="14" class="mr-1" /> 新增迭代
                </vort-button>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search
                        v-model="filterParams.keyword"
                        placeholder="迭代名称/目标"
                        allow-clear
                        class="flex-1 sm:w-[200px]"
                        @search="onSearchSubmit"
                        @keyup.enter="onSearchSubmit"
                    />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.status" placeholder="全部" allow-clear class="flex-1 sm:w-[120px]" @change="onSearchSubmit">
                        <vort-select-option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">负责人</span>
                    <WorkItemMemberPicker
                        mode="owner"
                        :owner="getMemberNameById(filterParams.owner_id)"
                        :groups="ownerGroups"
                        :open="filterOwnerDropdownOpen"
                        v-model:keyword="filterOwnerKeyword"
                        :show-all-option="true"
                        :dropdown-max-height="460"
                        :get-avatar-bg="getAvatarBg"
                        :get-avatar-label="getAvatarLabel"
                        :get-avatar-url="getMemberAvatarUrl"
                        @update:open="(open) => filterOwnerDropdownOpen = open"
                        @update:owner="handleFilterOwnerSelect"
                    >
                        <template #trigger="{ open }">
                            <div
                                class="filter-select-trigger flex-1 sm:w-[140px]"
                                :class="{ active: open }"
                                tabindex="0"
                                @click.stop="filterOwnerDropdownOpen = !filterOwnerDropdownOpen"
                            >
                                <div class="flex items-center w-full gap-2 min-w-0">
                                    <span class="filter-select-value text-sm truncate" :class="filterParams.owner_id ? 'text-[var(--vort-text,rgba(0,0,0,0.88))]' : 'text-[var(--vort-text-quaternary,rgba(0,0,0,0.25))]'">
                                        {{ getMemberNameById(filterParams.owner_id) || "负责人" }}
                                    </span>
                                    <span class="vort-select-arrow ml-auto" :class="{ 'vort-select-arrow-open': open }">
                                        <DownOutlined />
                                    </span>
                                </div>
                            </div>
                        </template>
                    </WorkItemMemberPicker>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- 表格卡片 -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false">
                <vort-table-column label="标题" :min-width="220">
                    <template #default="{ row }">
                        <div class="min-w-0 cursor-pointer" @click="router.push(`/vortflow/iterations/${row.id}`)">
                            <div class="text-sm text-blue-600 hover:underline truncate">{{ row.name }}</div>
                            <div class="text-xs text-gray-400 truncate">{{ projectNameById(row.project_id) }}</div>
                        </div>
                    </template>
                </vort-table-column>

                <vort-table-column label="状态" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="statusColorMap[row.status] || 'default'" size="small">
                            {{ statusLabels[row.status] || row.status }}
                        </vort-tag>
                    </template>
                </vort-table-column>

                <vort-table-column label="负责人" :width="160">
                    <template #default="{ row }">
                        <div class="h-8 max-w-[150px] px-2 rounded-md bg-transparent flex items-center gap-2">
                            <span
                                class="w-6 h-6 rounded-full text-white text-[12px] flex items-center justify-center shrink-0 overflow-hidden"
                                :style="{ backgroundColor: getAvatarBg(ownerName(row)) }"
                            >
                                <img
                                    v-if="iterationOwnerAvatarUrl(row)"
                                    :src="iterationOwnerAvatarUrl(row)"
                                    class="w-full h-full object-cover"
                                >
                                <template v-else>{{ getAvatarLabel(ownerName(row)) }}</template>
                            </span>
                            <span class="text-sm text-gray-700 truncate">{{ ownerName(row) }}</span>
                        </div>
                    </template>
                </vort-table-column>

                <vort-table-column label="计划时间" :width="260">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ formatDate(row.start_date) }} - {{ formatDate(row.end_date) }}</span>
                    </template>
                </vort-table-column>

                <vort-table-column label="工时" :width="160">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2">
                            <div class="w-[80px] h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                <div class="h-full bg-green-500 rounded-full" :style="{ width: `${effortPercent(row)}%` }" />
                            </div>
                            <span class="text-xs text-gray-400 whitespace-nowrap">{{ effortText(row) }}</span>
                        </div>
                    </template>
                </vort-table-column>

                <vort-table-column label="操作" :width="130" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEditIteration(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该迭代？" @confirm="handleDeleteIteration(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
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

        <!-- 新建/编辑迭代弹窗 -->
        <IterationEditDialog
            v-model:open="drawerVisible"
            :mode="drawerMode"
            :iteration="currentIteration"
            @saved="loadData"
        />
    </div>
</template>

<style scoped>
.filter-select-trigger {
    display: flex;
    align-items: center;
    padding: 4px 11px;
    border-radius: 6px;
    border: 1px solid #d9d9d9;
    background: #fff;
    min-height: 32px;
    transition: all 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
    outline: none;
    cursor: pointer;
}

.filter-select-trigger:hover,
.filter-select-trigger.active {
    border-color: var(--vort-primary, #1456f0);
    background: #fff;
}

.filter-select-trigger:focus-within,
.filter-select-trigger:focus {
    border-color: var(--vort-primary, #1456f0);
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

.filter-select-value {
    flex: 1;
    min-width: 0;
}

.vort-select-arrow {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: transform var(--vort-transition-colors, 0.2s);
}

.vort-select-arrow-open {
    transform: rotate(180deg);
}

.ml-auto {
    margin-left: auto;
}
</style>
