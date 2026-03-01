<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { getModels, getSettings, restartService, updateSettings } from "@/api";
import { message } from "@/components/vort/message";
import { Plus, RotateCw, Save, Trash2 } from "lucide-vue-next";

interface ModelSummary {
    id: string;
    name: string;
    provider: string;
    model: string;
    enabled: boolean;
}

interface CLIToolInfo {
    name: string;
    display_name: string;
    supported_providers: string[];
}

const loading = ref(false);
const saving = ref(false);
const savingCli = ref(false);
const activeTab = ref("llm");
const models = ref<ModelSummary[]>([]);
const cliTools = ref<CLIToolInfo[]>([]);

const form = ref({
    llm_primary_model_id: "",
    llm_fallback_model_ids: [] as string[],
});

const cliForm = ref({
    cli_default_tool: "claude-code",
    cli_primary_model_id: "",
    cli_fallback_model_ids: [] as string[],
});

function modelLabel(item: ModelSummary): string {
    return `${item.name} (${item.provider} / ${item.model})`;
}

function getFallbackOptions(currentId = ""): ModelSummary[] {
    return models.value.filter((m) => m.enabled && m.id !== form.value.llm_primary_model_id || m.id === currentId);
}

const selectedCliTool = computed(() => cliTools.value.find((t) => t.name === cliForm.value.cli_default_tool));

const cliCompatibleModels = computed(() => {
    const providers = selectedCliTool.value?.supported_providers || [];
    if (!providers.length) return models.value.filter((m) => m.enabled);
    return models.value.filter((m) => m.enabled && providers.includes(m.provider));
});

function getCliFallbackOptions(currentId = ""): ModelSummary[] {
    return cliCompatibleModels.value.filter(
        (m) => m.id !== cliForm.value.cli_primary_model_id || m.id === currentId,
    );
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

        // CLI config
        cliForm.value.cli_default_tool = settingsData.cli_default_tool || "claude-code";
        cliForm.value.cli_primary_model_id = settingsData.cli_primary_model_id || "";
        cliForm.value.cli_fallback_model_ids = Array.isArray(settingsData.cli_fallback_model_ids)
            ? settingsData.cli_fallback_model_ids
            : [];
        cliTools.value = Array.isArray(settingsData.cli_tools) ? settingsData.cli_tools : [];
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

function addCliFallback() {
    cliForm.value.cli_fallback_model_ids.push("");
}

function removeCliFallback(index: number) {
    cliForm.value.cli_fallback_model_ids.splice(index, 1);
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

async function handleSaveCli() {
    savingCli.value = true;
    try {
        const cleaned: string[] = [];
        const seen = new Set<string>();
        for (const id of cliForm.value.cli_fallback_model_ids) {
            const value = String(id || "").trim();
            if (!value || value === cliForm.value.cli_primary_model_id || seen.has(value)) continue;
            seen.add(value);
            cleaned.push(value);
        }
        await updateSettings({
            cli_default_tool: cliForm.value.cli_default_tool,
            cli_primary_model_id: cliForm.value.cli_primary_model_id,
            cli_fallback_model_ids: cleaned,
        });
        cliForm.value.cli_fallback_model_ids = [...cleaned];
        message.success("AI 编码设置已保存");
    } catch {
        message.error("保存失败");
    } finally {
        savingCli.value = false;
    }
}

const restarting = ref(false);
async function handleRestart() {
    restarting.value = true;
    try {
        await restartService();
        message.success("服务正在重启，请稍候...");
        setTimeout(() => {
            window.location.reload();
        }, 5000);
    } catch {
        message.error("重启请求失败");
        restarting.value = false;
    }
}

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6 max-w-3xl">
            <h3 class="text-base font-medium text-gray-800 mb-6">系统设置</h3>

            <VortTabs v-model:activeKey="activeTab">
                <VortTabPane tab-key="llm" tab="LLM 配置">
                    <VortSpin :spinning="loading">
                        <VortForm label-width="130px" class="mt-4">
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
                                还没有可用模型，请先到“模型管理”页面添加模型
                            </div>

                            <VortDivider />

                            <VortFormItem>
                                <VortButton variant="primary" :loading="saving" @click="handleSave">
                                    <Save :size="14" class="mr-1" /> 保存设置
                                </VortButton>
                            </VortFormItem>
                        </VortForm>
                    </VortSpin>
                </VortTabPane>

                <VortTabPane tab-key="coding" tab="AI 编码">
                    <VortSpin :spinning="loading">
                        <VortForm label-width="130px" class="mt-4">
                            <p class="text-sm text-gray-500 mb-4">
                                配置 AI 编码任务使用的 CLI 工具和模型。模型列表根据所选工具支持的 Provider 自动过滤。
                            </p>

                            <VortFormItem label="CLI 工具">
                                <VortSelect v-model="cliForm.cli_default_tool" class="w-full" placeholder="选择 CLI 编码工具">
                                    <VortSelectOption v-for="tool in cliTools" :key="tool.name" :value="tool.name">
                                        {{ tool.display_name }}
                                    </VortSelectOption>
                                </VortSelect>
                                <p v-if="selectedCliTool" class="text-xs text-gray-400 mt-1">
                                    支持的 Provider: {{ selectedCliTool.supported_providers.join(', ') }}
                                </p>
                            </VortFormItem>

                            <VortFormItem label="编码模型">
                                <VortSelect v-model="cliForm.cli_primary_model_id" class="w-full" placeholder="选择模型（留空则使用环境变量）" allow-clear>
                                    <VortSelectOption v-for="item in cliCompatibleModels" :key="item.id" :value="item.id">
                                        {{ modelLabel(item) }}
                                    </VortSelectOption>
                                </VortSelect>
                                <p class="text-xs text-gray-400 mt-1">
                                    未配置时将回退到环境变量中的 API Key。
                                </p>
                            </VortFormItem>

                            <VortDivider />

                            <div class="flex items-center justify-between mb-4">
                                <h4 class="text-sm font-medium text-gray-700">备选模型（按顺序）</h4>
                                <VortButton size="small" @click="addCliFallback">
                                    <Plus :size="14" class="mr-1" /> 添加
                                </VortButton>
                            </div>
                            <p class="text-xs text-gray-400 mb-4">编码模型失败时，按顺序尝试备选模型重新执行任务。</p>

                            <div v-for="(_, i) in cliForm.cli_fallback_model_ids" :key="i" class="border border-gray-200 rounded-lg p-4 mb-3 relative">
                                <button class="absolute top-3 right-3 text-gray-400 hover:text-red-500" type="button" @click="removeCliFallback(i)">
                                    <Trash2 :size="14" />
                                </button>
                                <div class="text-xs text-gray-500 mb-3">备选模型 #{{ i + 1 }}</div>
                                <VortSelect v-model="cliForm.cli_fallback_model_ids[i]" class="w-full" placeholder="请选择备选模型">
                                    <VortSelectOption v-for="item in getCliFallbackOptions(cliForm.cli_fallback_model_ids[i])" :key="item.id" :value="item.id">
                                        {{ modelLabel(item) }}
                                    </VortSelectOption>
                                </VortSelect>
                            </div>

                            <div v-if="cliForm.cli_fallback_model_ids.length === 0" class="text-center py-4 text-gray-400 text-sm">
                                暂无备选模型
                            </div>

                            <div v-if="cliCompatibleModels.length === 0" class="text-center py-4 text-amber-500 text-sm">
                                当前 CLI 工具没有兼容的已启用模型，请先到"模型管理"页面添加对应 Provider 的模型
                            </div>

                            <VortDivider />

                            <VortFormItem>
                                <VortButton variant="primary" :loading="savingCli" @click="handleSaveCli">
                                    <Save :size="14" class="mr-1" /> 保存设置
                                </VortButton>
                            </VortFormItem>
                        </VortForm>
                    </VortSpin>
                </VortTabPane>
            </VortTabs>
        </div>

        <div class="bg-white rounded-xl p-6 max-w-3xl">
            <h3 class="text-base font-medium text-gray-800 mb-2">服务管理</h3>
            <p class="text-sm text-gray-500 mb-4">重启后端服务，使配置或代码变更生效。</p>
            <VortButton :loading="restarting" @click="handleRestart">
                <RotateCw :size="14" class="mr-1" /> 重启服务
            </VortButton>
        </div>
    </div>
</template>
