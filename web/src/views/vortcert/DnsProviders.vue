<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getCertDnsProviders, deleteCertDnsProvider } from "@/api";
import { useCrudPage } from "@/hooks";
import { message } from "@openvort/vort-ui";
import { Plus } from "lucide-vue-next";
import DnsProviderEditDialog from "./DnsProviderEditDialog.vue";
import dayjs from "dayjs";

interface ProviderItem {
    id: string;
    name: string;
    provider_type: string;
    has_key: boolean;
    has_secret: boolean;
    created_at: string;
    updated_at: string;
}

interface FilterParams {
    page: number;
    size: number;
}

const editDialogOpen = ref(false);
const editData = ref<any>(null);

const providerTypeLabels: Record<string, string> = {
    aliyun: "阿里云",
    tencent: "腾讯云",
    cloudflare: "Cloudflare",
    namesilo: "NameSilo",
    godaddy: "GoDaddy",
    namecheap: "Namecheap",
    aws: "AWS Route53",
};

const fetchList = async (params: FilterParams) => {
    const res = await getCertDnsProviders() as any;
    const items = res.items || [];
    return { records: items, total: items.length };
};

const {
    listData, loading, loadData,
} = useCrudPage<ProviderItem, FilterParams>({
    api: fetchList,
    defaultParams: { page: 1, size: 50 },
});

const handleAdd = () => {
    editData.value = null;
    editDialogOpen.value = true;
};

const handleEdit = (row: ProviderItem) => {
    editData.value = row;
    editDialogOpen.value = true;
};

const handleDelete = async (row: ProviderItem) => {
    try {
        await deleteCertDnsProvider(row.id);
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
                <h3 class="text-base font-medium text-gray-800">DNS 服务商配置</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 添加服务商
                </vort-button>
            </div>

            <p class="text-sm text-gray-500 mb-4">
                配置 DNS 服务商的 API 凭证，用于 Let's Encrypt DNS-01 验证签发 SSL 证书。凭证使用 Fernet 加密存储。
            </p>

            <vort-table :data-source="listData" :loading="loading" :pagination="false" row-key="id">
                <vort-table-column label="名称" prop="name" :min-width="160">
                    <template #default="{ row }">
                        <div class="font-medium text-gray-800">{{ row.name }}</div>
                    </template>
                </vort-table-column>
                <vort-table-column label="服务商类型" prop="provider_type" :width="140">
                    <template #default="{ row }">
                        <vort-tag color="blue" size="small">
                            {{ providerTypeLabels[row.provider_type] || row.provider_type }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="API Key" :width="120">
                    <template #default="{ row }">
                        <vort-tag :color="row.has_key ? 'green' : 'default'" size="small">
                            {{ row.has_key ? '已配置' : '未配置' }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="API Secret" :width="120">
                    <template #default="{ row }">
                        <vort-tag :color="row.has_secret ? 'green' : 'default'" size="small">
                            {{ row.has_secret ? '已配置' : '未配置' }}
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
                            <vort-popconfirm title="确认删除该服务商？" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>
        </div>

        <DnsProviderEditDialog
            :open="editDialogOpen"
            :edit-data="editData"
            @update:open="editDialogOpen = $event"
            @success="handleDialogSuccess"
        />
    </div>
</template>
