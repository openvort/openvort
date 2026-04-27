<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getCertDeployTargets, deleteCertDeployTarget } from "@/api";
import { useCrudPage } from "@/hooks";
import { message } from "@openvort/vort-ui";
import { Plus } from "lucide-vue-next";
import DeployTargetEditDialog from "./DeployTargetEditDialog.vue";
import dayjs from "dayjs";

interface TargetItem {
    id: string;
    name: string;
    target_type: string;
    config: string;
    has_api_key: boolean;
    api_key_masked: string;
    dns_provider_id: string;
    created_at: string;
    updated_at: string;
}

interface FilterParams {
    page: number;
    size: number;
}

const editDialogOpen = ref(false);
const editData = ref<any>(null);

const targetTypeLabels: Record<string, string> = {
    aliyun_cdn: "阿里云 CDN",
    baota: "宝塔面板",
};

const targetTypeColors: Record<string, string> = {
    aliyun_cdn: "blue",
    baota: "orange",
};

const getConfigSummary = (item: TargetItem) => {
    try {
        const config = JSON.parse(item.config || "{}");
        if (item.target_type === "aliyun_cdn") return config.cdn_domain || "-";
        if (item.target_type === "baota") return `${config.site_name || "-"} @ ${config.panel_url || "-"}`;
    } catch { /* ignore */ }
    return "-";
};

const fetchList = async (params: FilterParams) => {
    const res = await getCertDeployTargets() as any;
    const items = res.items || [];
    return { records: items, total: items.length };
};

const {
    listData, loading, loadData,
} = useCrudPage<TargetItem, FilterParams>({
    api: fetchList,
    defaultParams: { page: 1, size: 50 },
});

const handleAdd = () => {
    editData.value = null;
    editDialogOpen.value = true;
};

const handleEdit = (row: TargetItem) => {
    editData.value = row;
    editDialogOpen.value = true;
};

const handleDelete = async (row: TargetItem) => {
    try {
        await deleteCertDeployTarget(row.id);
        message.success("删除成功");
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "删除失败");
    }
};

const handleDialogSuccess = () => {
    editDialogOpen.value = false;
    loadData();
};

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">部署目标</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 添加目标
                </vort-button>
            </div>

            <p class="text-sm text-gray-500 mb-4">
                管理证书部署目标，签发证书后可一键推送到阿里云 CDN、宝塔面板等平台。
            </p>

            <vort-table :data-source="listData" :loading="loading" :pagination="false" row-key="id">
                <vort-table-column label="名称" prop="name" :min-width="160">
                    <template #default="{ row }">
                        <div class="font-medium text-gray-800">{{ row.name }}</div>
                    </template>
                </vort-table-column>
                <vort-table-column label="类型" prop="target_type" :width="140">
                    <template #default="{ row }">
                        <vort-tag :color="targetTypeColors[row.target_type] || 'default'" size="small">
                            {{ targetTypeLabels[row.target_type] || row.target_type }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="目标" :min-width="220">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ getConfigSummary(row) }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="凭证" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="row.has_api_key || row.dns_provider_id ? 'green' : 'default'" size="small">
                            {{ row.has_api_key || row.dns_provider_id ? '已配置' : '未配置' }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="创建时间" :width="160">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">{{ dayjs(row.created_at).format("YYYY-MM-DD HH:mm") }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="140" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该部署目标？" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>
        </div>

        <DeployTargetEditDialog
            :open="editDialogOpen"
            :edit-data="editData"
            @update:open="editDialogOpen = $event"
            @success="handleDialogSuccess"
        />
    </div>
</template>
