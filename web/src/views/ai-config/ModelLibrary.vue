<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Plus, RefreshCw, Search } from "lucide-vue-next";
import { createModel, deleteModel, getModels, testModel, updateModel, fetchAvailableModels, batchTestModels, getSettings } from "@/api";
import { message } from "@/components/vort/message";

interface ModelItem {
    id: string;
    name: string;
    provider: string;
    model: string;
    api_key: string;
    api_base: string;
    max_tokens: number;
    timeout: number;
    enabled: boolean;
    api_format: string;
}

const providerOptions = [
    { label: "Anthropic (Claude)", value: "anthropic" },
    { label: "OpenAI (GPT)", value: "openai" },
    { label: "DeepSeek", value: "deepseek" },
    { label: "Moonshot (Kimi)", value: "moonshot" },
    { label: "通义千问 (Qwen)", value: "qwen" },
    { label: "智谱 (GLM)", value: "zhipu" },
    { label: "自定义 (OpenAI 兼容)", value: "custom" },
];

const apiFormatOptions = [
    { label: "自动检测", value: "auto" },
    { label: "Chat Completions (标准)", value: "chat_completions" },
    { label: "Responses API (GPT-5/Codex)", value: "responses" },
];

function apiFormatLabel(val: string): string {
    return apiFormatOptions.find((o) => o.value === val)?.label || val;
}

const loading = ref(false);
const saving = ref(false);
const dialogOpen = ref(false);
const editing = ref(false);
const editingId = ref("");
const editingApiKey = ref(false);
const apiKeyBackup = ref("");
const list = ref<ModelItem[]>([]);

const defaultForm = (): ModelItem => ({
    id: "",
    name: "",
    provider: "anthropic",
    model: "",
    api_key: "",
    api_base: "",
    max_tokens: 4096,
    timeout: 120,
    enabled: true,
    api_format: "auto",
});

const form = ref<ModelItem>(defaultForm());

const settings = ref<Record<string, any>>({});

function getModelTags(modelId: string): { label: string; color: string }[] {
    const tags: { label: string; color: string }[] = [];
    if (settings.value.llm_primary_model_id === modelId) {
        tags.push({ label: "主模型", color: "blue" });
    }
    const fallbackIds: string[] = settings.value.llm_fallback_model_ids || [];
    if (fallbackIds.includes(modelId)) {
        tags.push({ label: "备用模型", color: "cyan" });
    }
    if (settings.value.cli_primary_model_id === modelId) {
        tags.push({ label: "编码模型", color: "purple" });
    }
    const cliFallbacks: any[] = settings.value.cli_fallbacks || [];
    if (cliFallbacks.some((fb: any) => fb.model_id === modelId)) {
        tags.push({ label: "编码备用", color: "geekblue" });
    }
    return tags;
}

function maskApiKey(apiKey: string): string {
    if (!apiKey) return "未设置";
    if (apiKey.includes("***")) return apiKey;
    if (apiKey.length <= 8) return "***";
    return `${apiKey.slice(0, 3)}***${apiKey.slice(-4)}`;
}

async function loadData() {
    loading.value = true;
    try {
        const [res, settingsRes]: any[] = await Promise.all([getModels(), getSettings()]);
        list.value = Array.isArray(res) ? res : [];
        settings.value = settingsRes || {};
    } catch {
        message.error("加载模型列表失败");
    } finally {
        loading.value = false;
    }
}

function handleAdd() {
    editing.value = false;
    editingId.value = "";
    editingApiKey.value = true;
    apiKeyBackup.value = "";
    form.value = defaultForm();
    dialogOpen.value = true;
}

function handleEdit(row: ModelItem) {
    editing.value = true;
    editingId.value = row.id;
    editingApiKey.value = false;
    apiKeyBackup.value = row.api_key || "";
    form.value = { ...defaultForm(), ...row };
    dialogOpen.value = true;
}

function handleCopy(row: ModelItem) {
    editing.value = false;
    editingId.value = "";
    editingApiKey.value = true;
    apiKeyBackup.value = "";
    form.value = {
        ...defaultForm(),
        ...row,
        id: "",
        name: `${row.name} (副本)`,
        api_key: "",
    };
    dialogOpen.value = true;
}

function startEditApiKey() {
    apiKeyBackup.value = form.value.api_key;
    editingApiKey.value = true;
    form.value.api_key = "";
}

function cancelEditApiKey() {
    form.value.api_key = apiKeyBackup.value;
    editingApiKey.value = false;
}

async function handleSave() {
    if (!form.value.name.trim()) {
        message.error("名称不能为空");
        return;
    }
    if (!form.value.model.trim()) {
        message.error("模型名称不能为空");
        return;
    }
    saving.value = true;
    try {
        if (editing.value) {
            const payload: Record<string, any> = {
                name: form.value.name,
                provider: form.value.provider,
                model: form.value.model,
                api_base: form.value.api_base,
                max_tokens: form.value.max_tokens,
                timeout: form.value.timeout,
                enabled: form.value.enabled,
                api_format: form.value.api_format,
            };
            if (editingApiKey.value) {
                payload.api_key = form.value.api_key;
            }
            const ret: any = await updateModel(editingId.value, payload);
            if (ret && ret.success === false) {
                message.error(ret.error || "更新失败");
                return;
            }
            message.success("更新成功");
        } else {
            const ret: any = await createModel({
                name: form.value.name,
                provider: form.value.provider,
                model: form.value.model,
                api_key: form.value.api_key,
                api_base: form.value.api_base,
                max_tokens: form.value.max_tokens,
                timeout: form.value.timeout,
                enabled: form.value.enabled,
                api_format: form.value.api_format,
            });
            if (ret && ret.success === false) {
                message.error(ret.error || "创建失败");
                return;
            }
            message.success("创建成功");
        }
        dialogOpen.value = false;
        await loadData();
    } catch {
        message.error("操作失败");
    } finally {
        saving.value = false;
    }
}

async function handleToggle(row: ModelItem) {
    try {
        const ret: any = await updateModel(row.id, { enabled: !row.enabled });
        if (ret && ret.success === false) {
            message.error(ret.error || "更新失败");
            return;
        }
        message.success("状态已更新");
        await loadData();
    } catch {
        message.error("更新失败");
    }
}

async function deleteModelChecked(modelId: string) {
    const ret: any = await deleteModel(modelId);
    if (ret && ret.success === false) {
        throw new Error(ret.error || "删除失败");
    }
}

const testingMap = ref<Record<string, boolean>>({});
const testResults = ref<Record<string, {
    success: boolean;
    latency_ms?: number;
    reply?: string;
    error?: string;
    api_format?: string;
    detected_format?: string;
}>>({});

const availableModels = ref<{ value: string; label: string }[]>([]);
const fetchingModels = ref(false);

async function handleFetchModels() {
    const apiKey = editingApiKey.value ? form.value.api_key : apiKeyBackup.value;
    if (!apiKey && !editingId.value) {
        message.error("请先填写 API Key");
        return;
    }
    fetchingModels.value = true;
    try {
        const ret: any = await fetchAvailableModels({
            provider: form.value.provider,
            api_key: apiKey,
            api_base: form.value.api_base,
            model_id: editingId.value || undefined,
        });
        if (ret.success && Array.isArray(ret.models)) {
            availableModels.value = ret.models.map((m: string) => ({ value: m, label: m }));
            message.success(`已获取 ${ret.models.length} 个可用模型`);
        } else {
            availableModels.value = [];
            message.error(ret.error || "获取模型列表失败");
        }
    } catch {
        message.error("获取模型列表请求失败");
    } finally {
        fetchingModels.value = false;
    }
}

const batchTesting = ref(false);

async function handleBatchTest() {
    if (batchTesting.value) return;
    batchTesting.value = true;
    testResults.value = {};
    for (const row of list.value) {
        testingMap.value[row.id] = true;
    }
    try {
        const results: any = await batchTestModels();
        if (Array.isArray(results)) {
            let successCount = 0;
            let failCount = 0;
            for (const r of results) {
                if (r.id) {
                    testResults.value[r.id] = r;
                    delete testingMap.value[r.id];
                    if (r.success) successCount++;
                    else failCount++;
                }
            }
            if (failCount === 0) {
                message.success(`全部 ${successCount} 个模型测试通过`);
            } else {
                message.warning(`${successCount} 个通过，${failCount} 个失败`);
            }
        }
    } catch {
        message.error("批量测试请求失败");
    } finally {
        batchTesting.value = false;
        for (const row of list.value) {
            delete testingMap.value[row.id];
        }
    }
}

async function handleTest(row: ModelItem) {
    if (testingMap.value[row.id]) return;
    testingMap.value[row.id] = true;
    delete testResults.value[row.id];
    try {
        const ret: any = await testModel(row.id);
        testResults.value[row.id] = ret;
        if (ret.success) {
            let msg = `连接成功，延迟 ${ret.latency_ms}ms`;
            if (ret.detected_format) {
                msg += `（已自动切换为 ${apiFormatLabel(ret.detected_format)}）`;
                await loadData();
            }
            message.success(msg);
        } else {
            message.error(ret.error || "测试失败");
        }
    } catch {
        testResults.value[row.id] = { success: false, error: "请求异常" };
        message.error("测试请求失败");
    } finally {
        delete testingMap.value[row.id];
    }
}

onMounted(loadData);
</script>

<template>
    <div>
        <div class="flex items-center justify-between mb-4">
            <p class="text-sm text-gray-500">
                统一维护模型参数与凭证，在对话模型和编码工具中可直接引用。
            </p>
            <div class="flex items-center gap-2">
                <VortButton :loading="batchTesting" @click="handleBatchTest">
                    <RefreshCw :size="14" class="mr-1" /> 批量测试
                </VortButton>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增模型
                </VortButton>
            </div>
        </div>

        <VortTable :data-source="list" :loading="loading" row-key="id" :pagination="false">
            <VortTableColumn label="名称" :min-width="200">
                <template #default="{ row }">
                    <span>{{ row.name }}</span>
                    <VortTag
                        v-for="tag in getModelTags(row.id)"
                        :key="tag.label"
                        :color="tag.color"
                        :bordered="false"
                        size="small"
                        class="ml-1"
                    >{{ tag.label }}</VortTag>
                </template>
            </VortTableColumn>
            <VortTableColumn label="Provider" prop="provider" :width="120" />
            <VortTableColumn label="模型" prop="model" :width="220" />
            <VortTableColumn label="API Key" :width="140">
                <template #default="{ row }">
                    <span class="text-xs text-gray-500">{{ maskApiKey(row.api_key) }}</span>
                </template>
            </VortTableColumn>
            <VortTableColumn label="API Base" prop="api_base" :width="220">
                <template #default="{ row }">
                    <span class="text-xs text-gray-500">{{ row.api_base || "默认" }}</span>
                </template>
            </VortTableColumn>
            <VortTableColumn label="Max Tokens" prop="max_tokens" :width="100" />
            <VortTableColumn label="超时(秒)" prop="timeout" :width="80" />
            <VortTableColumn label="启用" :width="80">
                <template #default="{ row }">
                    <VortSwitch :checked="row.enabled" @change="handleToggle(row)" />
                </template>
            </VortTableColumn>
            <VortTableColumn label="操作" :width="230" fixed="right">
                <template #default="{ row }">
                    <div class="flex items-center gap-2 whitespace-nowrap">
                        <a
                            class="text-sm cursor-pointer"
                            :class="testingMap[row.id] ? 'text-gray-400 pointer-events-none' : 'text-green-600 hover:text-green-700'"
                            @click="handleTest(row)"
                        >
                            <span v-if="testingMap[row.id]" class="inline-flex items-center gap-1">
                                <svg class="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                                测试中
                            </span>
                            <span v-else>测试</span>
                        </a>
                        <vort-divider type="vertical" />
                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleCopy(row)">复制</a>
                        <vort-divider type="vertical" />
                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                        <vort-divider type="vertical" />
                        <DeleteRecord :request-api="() => deleteModelChecked(row.id)" :params="{}" @after-delete="loadData">
                            <a class="text-sm text-red-500 cursor-pointer">删除</a>
                        </DeleteRecord>
                    </div>
                    <div v-if="testResults[row.id]" class="mt-1 text-xs">
                        <span v-if="testResults[row.id].success" class="text-green-600">
                            ✓ 连接正常 · {{ testResults[row.id].latency_ms }}ms
                            <span v-if="testResults[row.id].api_format" class="text-gray-400 ml-1">
                                · {{ apiFormatLabel(testResults[row.id].api_format!) }}
                            </span>
                        </span>
                        <span v-else class="text-red-500" :title="testResults[row.id].error">
                            ✗ {{ testResults[row.id].error?.slice(0, 60) }}
                        </span>
                    </div>
                </template>
            </VortTableColumn>
        </VortTable>

        <VortDialog :open="dialogOpen" :title="editing ? '编辑模型' : '新增模型'" @update:open="dialogOpen = $event">
            <VortForm label-width="110px" class="mt-2">
                <VortFormItem label="名称" required>
                    <VortInput v-model="form.name" placeholder="如 Claude Sonnet 4" />
                </VortFormItem>
                <VortFormItem label="Provider" required>
                    <VortSelect v-model="form.provider" class="w-full">
                        <VortSelectOption v-for="opt in providerOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                        </VortSelectOption>
                    </VortSelect>
                </VortFormItem>
                <VortFormItem label="API Key">
                    <div class="flex items-center gap-3 w-full">
                        <template v-if="editingApiKey">
                            <VortInputPassword v-model="form.api_key" placeholder="输入 API Key" class="flex-1 min-w-0" />
                            <button v-if="editing" class="text-sm text-gray-500 hover:text-gray-700 shrink-0 whitespace-nowrap" type="button" @click="cancelEditApiKey">
                                取消
                            </button>
                        </template>
                        <template v-else>
                            <span class="text-sm text-gray-500">{{ maskApiKey(form.api_key) }}</span>
                            <button class="text-sm text-blue-600 hover:text-blue-700" type="button" @click="startEditApiKey">
                                编辑
                            </button>
                        </template>
                    </div>
                </VortFormItem>
                <VortFormItem label="API Base">
                    <VortInput v-model="form.api_base" placeholder="留空使用默认地址" />
                </VortFormItem>
                <VortFormItem label="模型" required>
                    <div class="flex items-center gap-2 w-full">
                        <VortAutoComplete
                            v-model="form.model"
                            :options="availableModels"
                            :filter-option="true"
                            placeholder="如 claude-sonnet-4-20250514"
                            class="flex-1 min-w-0"
                            :not-found-content="fetchingModels ? '加载中...' : '请点击右侧按钮获取模型列表'"
                        />
                        <VortButton
                            size="small"
                            :loading="fetchingModels"
                            @click="handleFetchModels"
                            title="自动获取可用模型列表"
                            class="shrink-0"
                        >
                            <Search :size="14" />
                        </VortButton>
                    </div>
                </VortFormItem>
                <VortFormItem v-if="form.provider !== 'anthropic'" label="API 格式">
                    <VortSelect v-model="form.api_format" class="w-full">
                        <VortSelectOption v-for="opt in apiFormatOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                        </VortSelectOption>
                    </VortSelect>
                    <p class="text-xs text-gray-400 mt-1">
                        <template v-if="form.api_format === 'auto'">点击测试按钮时自动检测，检测后自动保存</template>
                        <template v-else-if="form.api_format === 'responses'">适用于 GPT-5/Codex 等使用 /v1/responses 端点的模型</template>
                        <template v-else>适用于大多数 OpenAI 兼容 API（/v1/chat/completions）</template>
                    </p>
                </VortFormItem>
                <VortFormItem label="Max Tokens">
                    <VortInputNumber v-model="form.max_tokens" :min="256" :max="200000" class="w-full" />
                </VortFormItem>
                <VortFormItem label="超时(秒)">
                    <VortInputNumber v-model="form.timeout" :min="10" :max="600" class="w-full" />
                </VortFormItem>
                <VortFormItem label="启用">
                    <VortSwitch v-model:checked="form.enabled" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="dialogOpen = false">取消</VortButton>
                <VortButton variant="primary" :loading="saving" @click="handleSave" class="ml-3">确定</VortButton>
            </template>
        </VortDialog>
    </div>
</template>
