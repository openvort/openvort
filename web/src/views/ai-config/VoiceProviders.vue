<script setup lang="ts">
import { onMounted, ref } from "vue";
import { Plus } from "lucide-vue-next";
import { createVoiceProvider, deleteVoiceProvider, getVoiceProviders, updateVoiceProvider } from "@/api";
import { message } from "@/components/vort";

interface VoiceProviderItem {
    id: string;
    name: string;
    platform: string;
    is_default: boolean;
    is_enabled: boolean;
    config: Record<string, any>;
}

const platformOptions = [
    { label: "阿里云百炼", value: "aliyun" },
];

const loading = ref(false);
const saving = ref(false);
const dialogOpen = ref(false);
const editing = ref(false);
const editingId = ref("");
const list = ref<VoiceProviderItem[]>([]);

const form = ref({
    name: "",
    platform: "aliyun",
    api_key: "",
    config_text: JSON.stringify(
        {
            model: "qwen3-asr-flash",
            region: "cn",
        },
        null,
        2,
    ),
    is_default: false,
    is_enabled: true,
});

function resetForm() {
    form.value = {
        name: "",
        platform: "aliyun",
        api_key: "",
        config_text: JSON.stringify(
            {
                model: "qwen3-asr-flash",
                region: "cn",
            },
            null,
            2,
        ),
        is_default: false,
        is_enabled: true,
    };
}

async function loadData() {
    loading.value = true;
    try {
        const res: any = await getVoiceProviders();
        list.value = Array.isArray(res?.providers) ? res.providers : [];
    } catch {
        message.error("加载语音服务商失败");
    } finally {
        loading.value = false;
    }
}

function handleAdd() {
    editing.value = false;
    editingId.value = "";
    resetForm();
    dialogOpen.value = true;
}

function handleEdit(row: VoiceProviderItem) {
    editing.value = true;
    editingId.value = row.id;
    form.value = {
        name: row.name,
        platform: row.platform,
        api_key: "",
        config_text: JSON.stringify(row.config || {}, null, 2),
        is_default: row.is_default,
        is_enabled: row.is_enabled,
    };
    dialogOpen.value = true;
}

async function handleSave() {
    if (!form.value.name.trim()) {
        message.error("名称不能为空");
        return;
    }

    let parsedConfig: Record<string, any> = {};
    try {
        parsedConfig = form.value.config_text?.trim() ? JSON.parse(form.value.config_text) : {};
    } catch {
        message.error("配置 JSON 格式错误");
        return;
    }

    saving.value = true;
    try {
        if (editing.value) {
            const payload: Record<string, any> = {
                name: form.value.name,
                config: parsedConfig,
                is_default: form.value.is_default,
                is_enabled: form.value.is_enabled,
            };
            if (form.value.api_key?.trim()) {
                payload.api_key = form.value.api_key.trim();
            }
            await updateVoiceProvider(editingId.value, payload);
            message.success("更新成功");
        } else {
            await createVoiceProvider({
                name: form.value.name,
                platform: form.value.platform,
                api_key: form.value.api_key,
                config: parsedConfig,
                is_default: form.value.is_default,
            });
            message.success("创建成功");
        }
        dialogOpen.value = false;
        await loadData();
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "保存失败");
    } finally {
        saving.value = false;
    }
}

async function handleToggleEnabled(row: VoiceProviderItem) {
    try {
        await updateVoiceProvider(row.id, { is_enabled: !row.is_enabled });
        message.success("状态已更新");
        await loadData();
    } catch {
        message.error("状态更新失败");
    }
}

async function handleSetDefault(row: VoiceProviderItem) {
    if (row.is_default) return;
    try {
        await updateVoiceProvider(row.id, { is_default: true });
        message.success("已设为默认");
        await loadData();
    } catch {
        message.error("设置默认失败");
    }
}

async function deleteProviderChecked(providerId: string) {
    await deleteVoiceProvider(providerId);
}

onMounted(loadData);
</script>

<template>
    <div>
        <div class="flex items-center justify-between mb-4">
            <p class="text-sm text-gray-500">
                管理语音识别（ASR）服务商配置。收到企业微信语音后会自动转写为文本。
            </p>
            <VortButton variant="primary" @click="handleAdd">
                <Plus :size="14" class="mr-1" /> 新增语音服务商
            </VortButton>
        </div>

        <VortTable :data-source="list" :loading="loading" row-key="id" :pagination="false">
            <VortTableColumn label="名称" prop="name" :min-width="180" />
            <VortTableColumn label="平台" prop="platform" :width="120" />
            <VortTableColumn label="默认" :width="90">
                <template #default="{ row }">
                    <VortTag v-if="row.is_default" color="blue" :bordered="false" size="small">默认</VortTag>
                    <span v-else class="text-gray-400 text-xs">-</span>
                </template>
            </VortTableColumn>
            <VortTableColumn label="启用" :width="80">
                <template #default="{ row }">
                    <VortSwitch :checked="row.is_enabled" @change="handleToggleEnabled(row)" />
                </template>
            </VortTableColumn>
            <VortTableColumn label="配置" :min-width="280">
                <template #default="{ row }">
                    <code class="text-xs text-gray-500 break-all">{{ JSON.stringify(row.config || {}) }}</code>
                </template>
            </VortTableColumn>
            <VortTableColumn label="操作" :width="200" fixed="right">
                <template #default="{ row }">
                    <div class="flex items-center gap-2 whitespace-nowrap">
                        <a
                            class="text-sm cursor-pointer"
                            :class="row.is_default ? 'text-gray-400 pointer-events-none' : 'text-green-600 hover:text-green-700'"
                            @click="handleSetDefault(row)"
                        >
                            设为默认
                        </a>
                        <vort-divider type="vertical" />
                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                        <vort-divider type="vertical" />
                        <DeleteRecord :request-api="() => deleteProviderChecked(row.id)" :params="{}" @after-delete="loadData">
                            <a class="text-sm text-red-500 cursor-pointer">删除</a>
                        </DeleteRecord>
                    </div>
                </template>
            </VortTableColumn>
        </VortTable>

        <VortDialog :open="dialogOpen" :title="editing ? '编辑语音服务商' : '新增语音服务商'" @update:open="dialogOpen = $event">
            <VortForm label-width="110px" class="mt-2">
                <VortFormItem label="名称" required>
                    <VortInput v-model="form.name" placeholder="如 阿里云-ASR" />
                </VortFormItem>
                <VortFormItem label="平台" required>
                    <VortSelect v-model="form.platform" class="w-full" :disabled="editing">
                        <VortSelectOption v-for="opt in platformOptions" :key="opt.value" :value="opt.value">
                            {{ opt.label }}
                        </VortSelectOption>
                    </VortSelect>
                </VortFormItem>
                <VortFormItem label="API Key">
                    <VortInputPassword v-model="form.api_key" placeholder="编辑时留空表示不修改" />
                </VortFormItem>
                <VortFormItem label="配置(JSON)">
                    <VortTextarea
                        v-model="form.config_text"
                        :rows="8"
                        placeholder='{"model":"qwen3-asr-flash","region":"cn"}'
                    />
                </VortFormItem>
                <VortFormItem label="设为默认">
                    <VortSwitch v-model:checked="form.is_default" />
                </VortFormItem>
                <VortFormItem v-if="editing" label="启用">
                    <VortSwitch v-model:checked="form.is_enabled" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="dialogOpen = false">取消</VortButton>
                <VortButton variant="primary" :loading="saving" @click="handleSave" class="ml-3">确定</VortButton>
            </template>
        </VortDialog>
    </div>
</template>
