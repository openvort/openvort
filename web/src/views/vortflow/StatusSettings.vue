<script setup lang="ts">
import { ref } from "vue";
import { Pencil, Plus } from "lucide-vue-next";
import StatusIcon from "@/components/vort-biz/work-item/StatusIcon.vue";
import { useCrudPage } from "@/hooks";
import { getVortflowStatuses, deleteVortflowStatus } from "@/api";
import { message } from "@/components/vort/message";
import StatusEditDialog from "./components/StatusEditDialog.vue";

interface StatusItem {
    id: string;
    name: string;
    icon: string;
    icon_color: string;
    command: string;
    work_item_types: string[];
    sort_order: number;
}

type FilterParams = { page: number; size: number; keyword: string; work_item_type: string };

const workItemTypeOptions = [
    { label: "全部", value: "" },
    { label: "需求", value: "需求" },
    { label: "任务", value: "任务" },
    { label: "缺陷", value: "缺陷" },
];

const fetchList = async (params: FilterParams) => {
    const res: any = await getVortflowStatuses({
        keyword: params.keyword || undefined,
        work_item_type: params.work_item_type || undefined,
    });
    const items = (res?.items || []) as StatusItem[];
    const start = (params.page - 1) * params.size;
    return { records: items.slice(start, start + params.size), total: items.length };
};

const {
    listData, loading, total, filterParams, showPagination,
    loadData, onSearchSubmit, resetParams,
} = useCrudPage<StatusItem, FilterParams>({
    api: fetchList,
    defaultParams: { page: 1, size: 20, keyword: "", work_item_type: "" },
});

const editDialogOpen = ref(false);
const editDialogMode = ref<"add" | "edit">("add");
const editDialogData = ref<{ id?: string; name?: string; icon?: string; icon_color?: string; command?: string }>({});

const handleAdd = () => {
    editDialogMode.value = "add";
    editDialogData.value = {};
    editDialogOpen.value = true;
};

const handleEdit = (row: StatusItem) => {
    editDialogMode.value = "edit";
    editDialogData.value = {
        id: row.id,
        name: row.name,
        icon: row.icon,
        icon_color: row.icon_color,
        command: row.command,
    };
    editDialogOpen.value = true;
};

const handleDelete = async (row: StatusItem) => {
    try {
        const res: any = await deleteVortflowStatus(row.id);
        if (res?.error) {
            message.error(res.error);
            return;
        }
        message.success("状态已删除");
        loadData();
    } catch (e: any) {
        message.error(e?.message || "删除失败");
    }
};

const typeColorMap: Record<string, string> = {
    "需求": "blue",
    "任务": "cyan",
    "缺陷": "red",
};

loadData();
</script>

<template>
    <div>
        <div class="flex items-center justify-end mb-4 gap-3">
            <vort-select
                v-model="filterParams.work_item_type"
                :options="workItemTypeOptions"
                placeholder="工作项类型"
                class="w-[140px]"
                @change="loadData"
            />
            <vort-input-search
                v-model="filterParams.keyword"
                placeholder="搜索..."
                allow-clear
                class="w-[200px]"
                @search="onSearchSubmit"
                @keyup.enter="onSearchSubmit"
            />
            <vort-button variant="primary" @click="handleAdd">
                <Plus :size="14" class="mr-1" /> 新建状态
            </vort-button>
        </div>

        <vort-table :data-source="listData" :loading="loading" :pagination="false" row-key="id">
            <vort-table-column label="状态图标" :width="90">
                <template #default="{ row }">
                    <StatusIcon :name="row.icon || 'circle'" :size="20" :color="row.icon_color" />
                </template>
            </vort-table-column>
            <vort-table-column label="状态名" prop="name" :width="160" />
            <vort-table-column label="指令" :width="160">
                <template #default="{ row }">
                    <span class="text-sm text-gray-500">{{ row.command || "" }}</span>
                </template>
            </vort-table-column>
            <vort-table-column label="已使用类型">
                <template #default="{ row }">
                    <div class="flex items-center gap-1.5 flex-wrap">
                        <vort-tag
                            v-for="t in row.work_item_types"
                            :key="t"
                            :color="typeColorMap[t] || 'default'"
                            size="small"
                        >
                            {{ t }}
                        </vort-tag>
                    </div>
                </template>
            </vort-table-column>
            <vort-table-column label="操作" :width="160" fixed="right">
                <template #default="{ row }">
                    <div class="flex items-center gap-2 whitespace-nowrap">
                        <a class="text-sm text-blue-600 cursor-pointer inline-flex items-center gap-1" @click="handleEdit(row)">
                            <Pencil :size="13" /> 编辑
                        </a>
                        <vort-divider type="vertical" />
                        <vort-popconfirm title="确认删除该状态？" @confirm="handleDelete(row)">
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

        <StatusEditDialog
            v-model:open="editDialogOpen"
            :mode="editDialogMode"
            :data="editDialogData"
            @saved="loadData"
        />
    </div>
</template>
