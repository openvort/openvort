<script setup lang="ts">
import { ref, onMounted, onActivated, computed, watch } from "vue";
import { z } from "zod";
import { useCrudPage } from "@/hooks";
import { getVortgitProviders, createVortgitProvider, updateVortgitProvider, deleteVortgitProvider, getVortgitCodingEnvStatus } from "@/api";
import { Plus, Eye, EyeOff, RefreshCw, CheckCircle2, XCircle, AlertCircle, Terminal, Container } from "lucide-vue-next";
import { message } from "@/components/vort";

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
    {
        label: "Gitee",
        value: "gitee",
        apiBase: "https://gitee.com/api/v5",
        description: "国内领先的代码托管平台",
        tokenGuide: "在 Gitee 个人设置 → 私人令牌 中创建，需要 projects、pull_requests 权限"
    },
    {
        label: "GitHub",
        value: "github",
        apiBase: "https://api.github.com",
        description: "全球最大的代码托管平台",
        tokenGuide: "在 GitHub Settings → Developer settings → Personal access tokens 中创建，需要 repo 权限"
    },
    {
        label: "GitLab",
        value: "gitlab",
        apiBase: "https://gitlab.com/api/v4",
        description: "开源的 DevOps 平台，支持私有部署",
        tokenGuide: "在 GitLab User Settings → Access Tokens 中创建，需要 api、read_repository、write_repository 权限"
    },
];
const platformLabel = (val: string) => platformOptions.find(o => o.value === val)?.label || val;
const platformColorMap: Record<string, string> = { gitee: "red", github: "default", gitlab: "orange" };

const currentPlatformInfo = computed(() => {
    return platformOptions.find(o => o.value === currentRow.value.platform) || null;
});

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
const formRef = ref();
const saving = ref(false);
const showToken = ref(false);

const providerValidationSchema = z.object({
    name: z.string().min(1, '平台名称不能为空'),
    platform: z.string().min(1, '请选择平台类型'),
    api_base: z.string().optional().or(z.literal('')),
    access_token: z.string().optional().or(z.literal('')),
    is_default: z.any().optional(),
});

const handleAdd = () => {
    drawerMode.value = "add";
    drawerTitle.value = "添加 Git 平台";
    const defaultPlatform = platformOptions[0];
    currentRow.value = {
        platform: defaultPlatform.value,
        api_base: defaultPlatform.apiBase,
        is_default: false,
        access_token: ""
    };
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
    try { await formRef.value?.validate(); } catch { return; }
    const data = currentRow.value;
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

const handleRefresh = () => {
    loadData();
};

// ---- Coding Environment ----
const activeTab = ref("providers");
const envStatus = ref<Record<string, any> | null>(null);
const envLoading = ref(false);

async function loadEnvStatus() {
    envLoading.value = true;
    try {
        envStatus.value = await getVortgitCodingEnvStatus() as any;
    } catch {
        envStatus.value = null;
    }
    envLoading.value = false;
}

function envModeLabel(mode: string): string {
    if (mode === "local") return "本地执行";
    if (mode === "docker") return "Docker 容器";
    return "不可用";
}

function envModeColor(mode: string): string {
    if (mode === "local") return "success";
    if (mode === "docker") return "processing";
    return "error";
}

onMounted(() => {
    loadData();
    loadEnvStatus();
});

onActivated(() => {
    loadData();
});

// 监听平台类型变化，自动填充默认 API 地址
watch(() => currentRow.value.platform, (newPlatform) => {
    if (drawerMode.value === "add" || drawerMode.value === "edit") {
        const platformInfo = platformOptions.find(o => o.value === newPlatform);
        if (platformInfo && !currentRow.value.api_base) {
            currentRow.value.api_base = platformInfo.apiBase;
        }
    }
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <VortTabs v-model:activeKey="activeTab">
                <!-- Git 平台 Tab -->
                <VortTabPane tab-key="providers" tab="Git 平台">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <vort-button @click="handleRefresh">
                                <RefreshCw :size="14" class="mr-1" /> 刷新
                            </vort-button>
                            <vort-button variant="primary" @click="handleAdd">
                                <Plus :size="14" class="mr-1" /> 添加平台
                            </vort-button>
                        </div>
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
                </VortTabPane>

                <!-- 编码环境 Tab -->
                <VortTabPane tab-key="coding-env" tab="编码环境">
                    <div class="flex items-center justify-between mb-4">
                        <p class="text-sm text-gray-400">AI 编码环境的运行状态、CLI 工具安装情况、API Key 配置。</p>
                        <vort-button @click="loadEnvStatus">
                            <RefreshCw :size="14" class="mr-1" /> 刷新
                        </vort-button>
                    </div>

                    <VortSpin :spinning="envLoading">
                        <div v-if="envStatus" class="space-y-6">
                            <!-- Mode card -->
                            <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <div class="border rounded-lg p-4">
                                    <div class="flex items-center gap-2 mb-2">
                                        <Terminal :size="16" class="text-gray-500" />
                                        <span class="text-sm font-medium text-gray-700">执行模式</span>
                                    </div>
                                    <vort-tag :color="envModeColor(envStatus.mode)" size="small">
                                        {{ envModeLabel(envStatus.mode) }}
                                    </vort-tag>
                                </div>
                                <div class="border rounded-lg p-4">
                                    <div class="flex items-center gap-2 mb-2">
                                        <Container :size="16" class="text-gray-500" />
                                        <span class="text-sm font-medium text-gray-700">Docker</span>
                                    </div>
                                    <vort-tag v-if="envStatus.docker_available" color="success" size="small">可用</vort-tag>
                                    <vort-tag v-else color="default" size="small">未安装</vort-tag>
                                    <span v-if="envStatus.docker_image_ready" class="text-xs text-green-600 ml-2">镜像已拉取</span>
                                </div>
                                <div class="border rounded-lg p-4">
                                    <div class="flex items-center gap-2 mb-2">
                                        <Terminal :size="16" class="text-gray-500" />
                                        <span class="text-sm font-medium text-gray-700">默认工具</span>
                                    </div>
                                    <span class="text-sm text-gray-700">{{ envStatus.cli_default_tool === 'claude-code' ? 'Claude Code' : envStatus.cli_default_tool }}</span>
                                </div>
                            </div>

                            <!-- CLI tools status -->
                            <div>
                                <h4 class="text-sm font-medium text-gray-700 mb-3">CLI 工具</h4>
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div v-for="tool in (envStatus.cli_tools || [])" :key="tool.name" class="border rounded-lg p-3 flex items-center justify-between">
                                        <div>
                                            <span class="text-sm font-medium text-gray-800">{{ tool.name }}</span>
                                            <span v-if="tool.version" class="text-xs text-gray-400 ml-2">v{{ tool.version }}</span>
                                        </div>
                                        <CheckCircle2 v-if="tool.installed" :size="16" class="text-green-500" />
                                        <XCircle v-else :size="16" class="text-gray-300" />
                                    </div>
                                </div>
                            </div>

                            <!-- API Keys -->
                            <div>
                                <h4 class="text-sm font-medium text-gray-700 mb-3">API Key 配置</h4>
                                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div class="border rounded-lg p-3 flex items-center justify-between">
                                        <span class="text-sm text-gray-700">Claude Code API Key</span>
                                        <vort-tag :color="envStatus.has_claude_key ? 'success' : 'default'" size="small">
                                            {{ envStatus.has_claude_key ? '已配置' : '未配置' }}
                                        </vort-tag>
                                    </div>
                                    <div class="border rounded-lg p-3 flex items-center justify-between">
                                        <span class="text-sm text-gray-700">Aider API Key</span>
                                        <vort-tag :color="envStatus.has_aider_key ? 'success' : 'default'" size="small">
                                            {{ envStatus.has_aider_key ? '已配置' : '未配置' }}
                                        </vort-tag>
                                    </div>
                                </div>
                                <p class="text-xs text-gray-400 mt-2">API Key 可在「插件管理 → VortGit」中配置，或由管理员通过 <code class="bg-gray-100 px-1 rounded">openvort coding setup</code> 命令设置。</p>
                            </div>

                            <!-- Unavailable guide -->
                            <div v-if="envStatus.mode === 'unavailable'" class="border border-orange-200 bg-orange-50 rounded-lg p-4">
                                <div class="flex items-start gap-2">
                                    <AlertCircle :size="16" class="text-orange-500 mt-0.5 shrink-0" />
                                    <div>
                                        <div class="text-sm font-medium text-orange-700 mb-1">编码环境未就绪</div>
                                        <div class="text-sm text-orange-600">
                                            需要管理员在服务器上执行以下命令完成初始化：
                                        </div>
                                        <code class="block mt-2 bg-white px-3 py-2 rounded text-sm text-gray-800 border border-orange-200">openvort coding setup</code>
                                        <div class="text-xs text-orange-500 mt-2">该命令会自动检测环境、拉取 Docker 镜像、引导配置 API Key。</div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div v-else class="text-center text-gray-400 py-12">
                            加载编码环境状态失败，请点击刷新重试
                        </div>
                    </VortSpin>
                </VortTabPane>
            </VortTabs>
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
                <vort-form ref="formRef" :model="currentRow" :rules="providerValidationSchema" label-width="100px">
                    <vort-form-item label="名称" name="name" required has-feedback>
                        <vort-input v-model="currentRow.name" placeholder="如：公司 Gitee" />
                    </vort-form-item>
                    <vort-form-item label="平台类型" name="platform" required has-feedback>
                        <vort-select v-model="currentRow.platform" placeholder="选择平台">
                            <vort-select-option v-for="opt in platformOptions" :key="opt.value" :value="opt.value">
                                {{ opt.label }}
                            </vort-select-option>
                        </vort-select>
                        <div v-if="currentPlatformInfo" class="text-xs text-gray-400 mt-1">
                            {{ currentPlatformInfo.description }}
                        </div>
                    </vort-form-item>
                    <vort-form-item label="API 地址" name="api_base">
                        <vort-input v-model="currentRow.api_base" placeholder="留空使用默认地址" />
                        <div v-if="currentPlatformInfo" class="text-xs text-gray-400 mt-1">
                            默认：{{ currentPlatformInfo.apiBase }}
                        </div>
                    </vort-form-item>
                    <vort-form-item label="Access Token" name="access_token">
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
                        <div v-if="currentPlatformInfo" class="text-xs text-blue-500 mt-1 leading-relaxed">
                            💡 {{ currentPlatformInfo.tokenGuide }}
                        </div>
                    </vort-form-item>
                    <vort-form-item label="默认平台" name="is_default">
                        <vort-switch v-model:checked="currentRow.is_default" />
                        <span class="text-xs text-gray-400 ml-2">设为默认后，新建需求时将优先使用此平台</span>
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
