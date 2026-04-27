<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getCertDomains, deleteCertDomain, getCertDnsProviders, checkSingleDomain } from "@/api";
import { useCrudPage } from "@/hooks";
import { message } from "@openvort/vort-ui";
import { Plus, Upload, RefreshCw } from "lucide-vue-next";
import DomainEditDialog from "./DomainEditDialog.vue";
import ImportDomainsDialog from "./ImportDomainsDialog.vue";
import dayjs from "dayjs";

interface DomainItem {
    id: string;
    domain: string;
    domain_type: string;
    label: string;
    note: string;
    dns_provider_id: string | null;
    last_check_status: string;
    expires_at: string | null;
    issuer: string;
    last_check_at: string | null;
    created_at: string;
}

interface FilterParams {
    page: number;
    size: number;
    keyword: string;
    label: string;
    status: string;
}

const dnsProviders = ref<any[]>([]);
const editDialogOpen = ref(false);
const importDialogOpen = ref(false);
const editData = ref<any>(null);
const checkingId = ref("");

const fetchList = async (params: FilterParams) => {
    const res = await getCertDomains({
        keyword: params.keyword,
        label: params.label,
        status: params.status,
        page: params.page,
        page_size: params.size,
    }) as any;
    return { records: res.items || [], total: res.total || 0 };
};

const {
    listData, loading, total, filterParams, showPagination,
    loadData, onSearchSubmit, resetParams,
} = useCrudPage<DomainItem, FilterParams>({
    api: fetchList,
    defaultParams: { page: 1, size: 20, keyword: "", label: "", status: "" },
});

const loadProviders = async () => {
    try {
        const res = await getCertDnsProviders() as any;
        dnsProviders.value = res.items || [];
    } catch {}
};

const providerName = (id: string | null) => {
    if (!id) return "-";
    const p = dnsProviders.value.find(p => p.id === id);
    return p ? `${p.name} (${p.provider_type})` : id;
};

const handleAdd = () => {
    editData.value = null;
    editDialogOpen.value = true;
};

const handleEdit = (row: DomainItem) => {
    editData.value = row;
    editDialogOpen.value = true;
};

const handleDelete = async (row: DomainItem) => {
    try {
        await deleteCertDomain(row.id);
        message.success("删除成功");
        loadData();
    } catch {
        message.error("删除失败");
    }
};

const handleCheck = async (row: DomainItem) => {
    checkingId.value = row.id;
    try {
        await checkSingleDomain(row.id);
        message.success(`${row.domain} 检查完成`);
        loadData();
    } catch {
        message.error("检查失败");
    } finally {
        checkingId.value = "";
    }
};

const handleDialogSuccess = () => {
    editDialogOpen.value = false;
    loadData();
};

const handleImportSuccess = () => {
    importDialogOpen.value = false;
    loadData();
};

const statusTagColor = (status: string) => {
    const map: Record<string, string> = { ok: "green", warning: "orange", critical: "red", expired: "red", error: "default" };
    return map[status] || "default";
};

const statusLabel = (status: string) => {
    const map: Record<string, string> = { ok: "正常", warning: "即将到期", critical: "即将到期", expired: "已过期", error: "异常", "": "未检查" };
    return map[status] || status;
};

onMounted(() => {
    loadData();
    loadProviders();
});
</script>

<template>
    <div class="space-y-4">
        <!-- Search Card -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">域名管理</h3>
                <div class="flex items-center gap-2">
                    <vort-button @click="importDialogOpen = true">
                        <Upload :size="14" class="mr-1" /> 批量导入
                    </vort-button>
                    <vort-button variant="primary" @click="handleAdd">
                        <Plus :size="14" class="mr-1" /> 添加域名
                    </vort-button>
                </div>
            </div>
            <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">关键词</span>
                    <vort-input-search v-model="filterParams.keyword" placeholder="搜索域名..." allow-clear class="flex-1 sm:w-[220px]" @search="onSearchSubmit" @keyup.enter="onSearchSubmit" />
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto">
                    <span class="text-sm text-gray-500 whitespace-nowrap">状态</span>
                    <vort-select v-model="filterParams.status" placeholder="全部" allow-clear class="w-[130px]" @change="onSearchSubmit">
                        <vort-select-option value="ok">正常</vort-select-option>
                        <vort-select-option value="warning">即将到期</vort-select-option>
                        <vort-select-option value="expired">已过期</vort-select-option>
                        <vort-select-option value="error">异常</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="onSearchSubmit">查询</vort-button>
                    <vort-button @click="resetParams">重置</vort-button>
                </div>
            </div>
        </div>

        <!-- Table Card -->
        <div class="bg-white rounded-xl p-6">
            <vort-table :data-source="listData" :loading="loading" :pagination="false" row-key="id">
                <vort-table-column label="域名" prop="domain" :min-width="220">
                    <template #default="{ row }">
                        <div class="font-medium text-gray-800">{{ row.domain }}</div>
                        <div v-if="row.note" class="text-xs text-gray-400 mt-0.5 line-clamp-1">{{ row.note }}</div>
                    </template>
                </vort-table-column>
                <vort-table-column label="类型" prop="domain_type" :width="90">
                    <template #default="{ row }">
                        <vort-tag :color="row.domain_type === 'wildcard' ? 'blue' : 'default'" size="small">
                            {{ row.domain_type === 'wildcard' ? '通配符' : '单域名' }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="标签" prop="label" :width="120">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ row.label || '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="DNS 服务商" :min-width="160">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ providerName(row.dns_provider_id) }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="状态" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="statusTagColor(row.last_check_status)" size="small">
                            {{ statusLabel(row.last_check_status) }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="到期时间" :width="140">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ row.expires_at ? dayjs(row.expires_at).format("YYYY-MM-DD") : '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="180" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleCheck(row)">
                                {{ checkingId === row.id ? '检查中...' : '检查' }}
                            </a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该域名？" @confirm="handleDelete(row)">
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

        <DomainEditDialog
            :open="editDialogOpen"
            :edit-data="editData"
            @update:open="editDialogOpen = $event"
            @success="handleDialogSuccess"
        />

        <ImportDomainsDialog
            :open="importDialogOpen"
            @update:open="importDialogOpen = $event"
            @success="handleImportSuccess"
        />
    </div>
</template>
