<script setup lang="ts">
import { ref } from "vue";
import { useCrudPage } from "@/hooks";
import { getVortgitProviders, createVortgitProvider, updateVortgitProvider, deleteVortgitProvider } from "@/api";
import { Plus, Eye, EyeOff } from "lucide-vue-next";
import { message } from "@/components/vort/message";

interface ProviderItem {
    id: string;
    name: string;
    platform: string;
    api_base: string;
    has_token: boolean;
    is_default: boolean;
    created_at: string;
}

type FilterParams = { page: number; size: number };

const platformOptions = [
    { label: "Gitee", value: "gitee" },
    { label: "GitHub", value: "github" },
    { label: "GitLab", value: "gitlab" },
];
const platformLabel = (val: string) => platformOptions.find(o => o.value === val)?.label || val;
const platformColorMap: Record<string, string> = { gitee: "red", github: "default", gitlab: "orange" };

const fetchList = async (params: FilterParams) => {
    const res = await getVortgitProviders();
    const items = (res as any).items || [];
    return { records: items, total: items.length };
};

const { listData, loading, total, filterParams, showPagination, loadData } =
    useCrudPage<ProviderItem, FilterParams>({
        api: fetchList,
        defaultParams: { page: 1, size: 50 },
    });

const drawerVisible = ref(false);
const drawerTitle = ref("");
const drawerMode = ref<"view" | "edit" | "add">("view");
const currentRow = ref<Partial<ProviderItem & { access_token: string }>>({});
const saving = ref(false);
const showToken = ref(false);

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "添加 Git 平台";
    currentRow.value = { platform: "gitee", api_base: "", is_default: false, access_token: "" };
    showToken.value = false;
    drawerVisible.value = true;
};
const handleEdit = (row: ProviderItem) => {
    drawerMode.value = "edit";
    drawerTitle.value = "编辑平台";
    currentRow.value = { ...row, access_token: "" };
    showToken.value = false;
    drawerVisible.value = true;
};
const handleView = (row: ProviderItem) => {
    drawerMode.value = "view";
    drawerTitle.value = "平台详情";
    currentRow.value = { ...row };
    drawerVisible.value = true;
};

const handleSave = async () => {
    const data = currentRow.value;
    if (!data.name?.trim()) {
        message.warning("请输入平台名称");
        return;
    }
    saving.value = true;
    try {
        if (drawerMode.value === "add") {
            await createVortgitProvider({
                name: data.name!,
                platform: data.platform || "gitee",
                api_base: data.api_base || "",
                access_token: data.access_token || "",
                is_default: data.is_default || false,
            });
            message.success("添加成功");
        } else {
            const update: any = { name: data.name, platform: data.platform, api_base: data.api_base, is_default: data.is_default };
            if (data.access_token) update.access_token = data.access_token;
            await updateVortgitProvider(data.id!, update);
            message.success("更新成功");
        }
        drawerVisible.value = false;
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    } finally {
        saving.value = false;
    }
};

const handleDelete = async (row: ProviderItem) => {
    try {
        await deleteVortgitProvider(row.id);
        message.success("已删除");
        loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "删除失败");
    }
};

loadData();
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-base font-medium text-gray-800">Git 平台管理</h3>
                <vort-button variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 添加平台
                </vort-button>
            </div>
            <p class="text-sm text-gray-400 mb-4">接入 Gitee、GitHub、GitLab 等代码托管平台，统一管理多平台仓库与 AI 编码能力。配置平台 Token 后即可导入仓库。</p>

            <vort-table :data-source="listData" :loading="loading" :pagination="false">
                <vort-table-column label="名称" prop="name" />
                <vort-table-column label="平台" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="platformColorMap[row.platform] || 'default'">{{ platformLabel(row.platform) }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="API 地址" prop="api_base" />
                <vort-table-column label="Token" :width="80">
                    <template #default="{ row }">
                        <vort-tag :color="row.has_token ? 'green' : 'default'">{{ row.has_token ? '已配置' : '未配置' }}</vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="默认" :width="60">
                    <template #default="{ row }">
                        <span v-if="row.is_default" class="text-blue-600 text-sm">是</span>
                        <span v-else class="text-gray-400 text-sm">—</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleView(row)">详情</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除？" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>
        </div>

        <vort-drawer v-model:open="drawerVisible" :title="drawerTitle" :width="500">
            <div v-if="drawerMode === 'view'" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div><span class="text-sm text-gray-400">名称</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.name }}</div></div>
                <div><span class="text-sm text-gray-400">平台</span><div class="mt-1"><vort-tag :color="platformColorMap[currentRow.platform!] || 'default'">{{ platformLabel(currentRow.platform || '') }}</vort-tag></div></div>
                <div class="sm:col-span-2"><span class="text-sm text-gray-400">API 地址</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.api_base || '默认' }}</div></div>
                <div><span class="text-sm text-gray-400">Token</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.has_token ? '已配置' : '未配置' }}</div></div>
                <div><span class="text-sm text-gray-400">默认平台</span><div class="text-sm text-gray-800 mt-1">{{ currentRow.is_default ? '是' : '否' }}</div></div>
            </div>
            <template v-else>
                <vort-form label-width="100px">
                    <vort-form-item label="名称" required>
                        <vort-input v-model="currentRow.name" placeholder="如：公司 Gitee" />
                    </vort-form-item>
                    <vort-form-item label="平台类型" required>
                        <vort-select v-model="currentRow.platform" placeholder="选择平台">
                            <vort-select-option v-for="opt in platformOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</vort-select-option>
                        </vort-select>
                    </vort-form-item>
                    <vort-form-item label="API 地址">
                        <vort-input v-model="currentRow.api_base" placeholder="留空使用默认地址" />
                    </vort-form-item>
                    <vort-form-item label="Access Token">
                        <div class="flex items-center gap-2 w-full">
                            <vort-input
                                v-model="currentRow.access_token"
                                :type="showToken ? 'text' : 'password'"
                                :placeholder="drawerMode === 'edit' ? '留空不修改' : '输入平台 Token'"
                                class="flex-1"
                            />
                            <vort-button size="small" @click="showToken = !showToken">
                                <component :is="showToken ? EyeOff : Eye" :size="14" />
                            </vort-button>
                        </div>
                    </vort-form-item>
                    <vort-form-item label="默认平台">
                        <vort-switch v-model:checked="currentRow.is_default" />
                    </vort-form-item>
                </vort-form>
                <div class="flex justify-end gap-3 mt-6">
                    <vort-button @click="drawerVisible = false">取消</vort-button>
                    <vort-button variant="primary" :loading="saving" @click="handleSave">确定</vort-button>
                </div>
            </template>
        </vort-drawer>
    </div>
</template>
