<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Plus } from "lucide-vue-next";
import { createModel, deleteModel, getModels, updateModel } from "@/api";
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
}

const providerOptions = [
    { label: "Anthropic (Claude)", value: "anthropic" },
    { label: "OpenAI (GPT)", value: "openai" },
    { label: "DeepSeek", value: "deepseek" },
    { label: "Moonshot (Kimi)", value: "moonshot" },
    { label: "通义千问 (Qwen)", value: "qwen" },
    { label: "智谱 (GLM)", value: "zhipu" },
];

const loading = ref(false);
const saving = ref(false);
const dialogOpen = ref(false);
const editing = ref(false);
const editingId = ref("");
const editingApiKey = ref(false);
const apiKeyBackup = ref("");
const list = ref<ModelItem[]>([]);

const form = ref<ModelItem>({
    id: "",
    name: "",
    provider: "anthropic",
    model: "",
    api_key: "",
    api_base: "",
    max_tokens: 4096,
    timeout: 120,
    enabled: true,
});

function maskApiKey(apiKey: string): string {
    if (!apiKey) return "未设置";
    if (apiKey.includes("***")) return apiKey;
    if (apiKey.length <= 8) return "***";
    return `${apiKey.slice(0, 3)}***${apiKey.slice(-4)}`;
}

async function loadData() {
    loading.value = true;
    try {
        const res: any = await getModels();
        list.value = Array.isArray(res) ? res : [];
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
    form.value = {
        id: "",
        name: "",
        provider: "anthropic",
        model: "",
        api_key: "",
        api_base: "",
        max_tokens: 4096,
        timeout: 120,
        enabled: true,
    };
    dialogOpen.value = true;
}

function handleEdit(row: ModelItem) {
    editing.value = true;
    editingId.value = row.id;
    editingApiKey.value = false;
    apiKeyBackup.value = row.api_key || "";
    form.value = { ...row };
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

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">模型管理</h3>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增模型
                </VortButton>
            </div>
            <p class="text-sm text-gray-500 mb-4">
                统一维护模型参数与凭证，系统设置中可直接选择主模型和备选模型。
            </p>

            <VortTable :data-source="list" :loading="loading" row-key="id" :pagination="false">
                <VortTableColumn label="名称" prop="name" :width="180" />
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
                <VortTableColumn label="Max Tokens" prop="max_tokens" :width="120" />
                <VortTableColumn label="超时(秒)" prop="timeout" :width="100" />
                <VortTableColumn label="启用" :width="80">
                    <template #default="{ row }">
                        <VortSwitch :checked="row.enabled" @change="handleToggle(row)" />
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="140" fixed="right">
                    <template #default="{ row }">
                        <TableActions>
                            <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
                            <DeleteRecord class="ml-2" :request-api="() => deleteModelChecked(row.id)" :params="{}" @after-delete="loadData">
                                <TableActionsItem danger>删除</TableActionsItem>
                            </DeleteRecord>
                        </TableActions>
                    </template>
                </VortTableColumn>
            </VortTable>
        </div>

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
                <VortFormItem label="模型" required>
                    <VortInput v-model="form.model" placeholder="如 claude-sonnet-4-20250514" />
                </VortFormItem>
                <VortFormItem label="API Key">
                    <div class="flex items-center gap-3 w-full">
                        <template v-if="editingApiKey">
                            <VortInputPassword v-model="form.api_key" placeholder="输入 API Key" class="flex-1 min-w-0" />
                            <button class="text-sm text-gray-500 hover:text-gray-700 shrink-0 whitespace-nowrap" type="button" @click="cancelEditApiKey">
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
