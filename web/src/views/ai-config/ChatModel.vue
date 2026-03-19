<script setup lang="ts">
import { ref, onMounted } from "vue";
import { Plus, Save, Trash2 } from "lucide-vue-next";
import { getModels, getSettings, updateSettings } from "@/api";
import { message } from "@/components/vort";

interface ModelSummary {
    id: string;
    name: string;
    provider: string;
    model: string;
    enabled: boolean;
}

const loading = ref(false);
const saving = ref(false);
const models = ref<ModelSummary[]>([]);

const form = ref({
    llm_primary_model_id: "",
    llm_fallback_model_ids: [] as string[],
});

function modelLabel(item: ModelSummary): string {
    return `${item.name} (${item.provider} / ${item.model})`;
}

function getFallbackOptions(currentId = ""): ModelSummary[] {
    return models.value.filter((m) => m.enabled && m.id !== form.value.llm_primary_model_id || m.id === currentId);
}

async function loadData() {
    loading.value = true;
    try {
        const [settingsRes, modelsRes]: any[] = await Promise.all([getSettings(), getModels()]);
        const settingsData = settingsRes || {};
        form.value.llm_primary_model_id = settingsData.llm_primary_model_id || "";
        form.value.llm_fallback_model_ids = Array.isArray(settingsData.llm_fallback_model_ids)
            ? settingsData.llm_fallback_model_ids
            : [];
        models.value = Array.isArray(modelsRes) ? modelsRes : [];
    } catch {
        message.error("加载设置失败");
    } finally {
        loading.value = false;
    }
}

function addFallback() {
    form.value.llm_fallback_model_ids.push("");
}

function removeFallback(index: number) {
    form.value.llm_fallback_model_ids.splice(index, 1);
}

async function handleSave() {
    if (!form.value.llm_primary_model_id) {
        message.error("请选择主模型");
        return;
    }
    saving.value = true;
    try {
        const cleaned: string[] = [];
        const seen = new Set<string>();
        for (const id of form.value.llm_fallback_model_ids) {
            const value = String(id || "").trim();
            if (!value || value === form.value.llm_primary_model_id || seen.has(value)) continue;
            seen.add(value);
            cleaned.push(value);
        }
        await updateSettings({
            llm_primary_model_id: form.value.llm_primary_model_id,
            llm_fallback_model_ids: cleaned,
        });
        form.value.llm_fallback_model_ids = [...cleaned];
        message.success("保存成功");
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
}

onMounted(loadData);
</script>

<template>
    <VortSpin :spinning="loading">
        <VortForm label-width="130px" class="max-w-2xl">
            <p class="text-sm text-gray-500 mb-4">
                选择 AI 对话使用的主模型，以及主模型失败时的备选模型链。
            </p>

            <VortFormItem label="主模型" required>
                <VortSelect v-model="form.llm_primary_model_id" class="w-full" placeholder="请选择模型">
                    <VortSelectOption v-for="item in models.filter(m => m.enabled)" :key="item.id" :value="item.id">
                        {{ modelLabel(item) }}
                    </VortSelectOption>
                </VortSelect>
            </VortFormItem>

            <VortDivider />

            <div class="flex items-center justify-between mb-4">
                <h4 class="text-sm font-medium text-gray-700">备选模型（按顺序）</h4>
                <VortButton size="small" @click="addFallback">
                    <Plus :size="14" class="mr-1" /> 添加
                </VortButton>
            </div>
            <p class="text-xs text-gray-400 mb-4">主模型失败时，按列表顺序尝试备选模型。</p>

            <div v-for="(fallbackId, i) in form.llm_fallback_model_ids" :key="i" class="border border-gray-200 rounded-lg p-4 mb-3 relative">
                <button class="absolute top-3 right-3 text-gray-400 hover:text-red-500" type="button" @click="removeFallback(i)">
                    <Trash2 :size="14" />
                </button>
                <div class="text-xs text-gray-500 mb-3">备选模型 #{{ i + 1 }}</div>
                <VortSelect v-model="form.llm_fallback_model_ids[i]" class="w-full" placeholder="请选择备选模型">
                    <VortSelectOption v-for="item in getFallbackOptions(fallbackId)" :key="item.id" :value="item.id">
                        {{ modelLabel(item) }}
                    </VortSelectOption>
                </VortSelect>
            </div>

            <div v-if="form.llm_fallback_model_ids.length === 0" class="text-center py-4 text-gray-400 text-sm">
                暂无备选模型
            </div>

            <div v-if="models.length === 0" class="text-center py-4 text-gray-400 text-sm">
                还没有可用模型，请先在"模型库" Tab 添加模型
            </div>

            <VortDivider />

            <VortFormItem>
                <VortButton variant="primary" :loading="saving" @click="handleSave">
                    <Save :size="14" class="mr-1" /> 保存设置
                </VortButton>
            </VortFormItem>
        </VortForm>
    </VortSpin>
</template>
