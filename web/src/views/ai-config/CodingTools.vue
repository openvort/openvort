<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Plus, Save, Trash2, Download, XCircle, CheckCircle, Terminal } from "lucide-vue-next";
import { getModels, getSettings, updateSettings } from "@/api";
import { message } from "@/components/vort/message";
import { useUserStore } from "@/stores";

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

interface CLIToolStatus {
    name: string;
    display_name: string;
    binary: string;
    install_cmd: string;
    uninstall_cmd: string;
    supported_providers: string[];
    installed: boolean;
    version: string;
    path: string;
}

const userStore = useUserStore();
const loading = ref(false);
const savingCli = ref(false);
const models = ref<ModelSummary[]>([]);
const cliTools = ref<CLIToolInfo[]>([]);
const cliToolsStatus = ref<CLIToolStatus[]>([]);
const operatingTool = ref<string>("");
const operationOutput = ref<string[]>([]);

interface CLIFallback {
    tool: string;
    model_id: string;
}

interface CLIGlobalSkill {
    id?: string;
    name: string;
    content: string;
    enabled: boolean;
}

const cliForm = ref({
    cli_default_tool: "claude-code",
    cli_primary_model_id: "",
    cli_fallbacks: [] as CLIFallback[],
    cli_global_skills: [] as CLIGlobalSkill[],
});

const autoCheckUpdate = ref(true);

function modelLabel(item: ModelSummary): string {
    return `${item.name} (${item.provider} / ${item.model})`;
}

const selectedCliTool = computed(() => cliTools.value.find((t) => t.name === cliForm.value.cli_default_tool));

const cliCompatibleModels = computed(() => {
    return models.value.filter((m) => m.enabled);
});

function isModelCompatibleWithTool(modelId: string, toolName: string): boolean {
    const model = models.value.find((m) => m.id === modelId);
    if (!model) return false;
    const tool = cliTools.value.find((t) => t.name === toolName);
    const providers = tool?.supported_providers || [];
    if (!providers.length) return true;
    return providers.includes(model.provider);
}

function isModelCompatible(modelId: string): boolean {
    return isModelCompatibleWithTool(modelId, cliForm.value.cli_default_tool);
}

async function loadData() {
    loading.value = true;
    try {
        const [settingsRes, modelsRes]: any[] = await Promise.all([
            getSettings(),
            getModels(),
        ]);
        const settingsData = settingsRes || {};
        models.value = Array.isArray(modelsRes) ? modelsRes : [];

        cliForm.value.cli_default_tool = settingsData.cli_default_tool || "claude-code";
        cliForm.value.cli_primary_model_id = settingsData.cli_primary_model_id || "";
        const rawFallbacks = settingsData.cli_fallbacks;
        if (Array.isArray(rawFallbacks)) {
            cliForm.value.cli_fallbacks = rawFallbacks.map((fb: any) => ({
                tool: fb.tool || settingsData.cli_default_tool || "claude-code",
                model_id: fb.model_id || "",
            }));
        } else if (Array.isArray(settingsData.cli_fallback_model_ids)) {
            cliForm.value.cli_fallbacks = settingsData.cli_fallback_model_ids.map((id: string) => ({
                tool: settingsData.cli_default_tool || "claude-code",
                model_id: id,
            }));
        } else {
            cliForm.value.cli_fallbacks = [];
        }
        cliTools.value = Array.isArray(settingsData.cli_tools) ? settingsData.cli_tools : [];
        cliToolsStatus.value = Array.isArray(settingsData.cli_tools_status) ? settingsData.cli_tools_status : [];

        // System settings
        autoCheckUpdate.value = settingsData.auto_check_update !== false;

        // Global coding skills
        if (Array.isArray(settingsData.cli_global_skills) && settingsData.cli_global_skills.length) {
            cliForm.value.cli_global_skills = settingsData.cli_global_skills.map((s: any) => ({
                id: s.id,
                name: s.name || "Skill",
                content: s.content || "",
                enabled: s.enabled !== false,
            }));
        } else {
            // 默认添加一条中文 Skill
            cliForm.value.cli_global_skills = [
                {
                    name: "中文编码习惯",
                    content: "在进行所有编码相关的思考和回复时，始终使用简体中文进行推理和说明。",
                    enabled: true,
                },
            ];
        }
    } catch {
        message.error("加载设置失败");
    } finally {
        loading.value = false;
    }
}

function addCliFallback() {
    cliForm.value.cli_fallbacks.push({ tool: cliForm.value.cli_default_tool, model_id: "" });
}

function removeCliFallback(index: number) {
    cliForm.value.cli_fallbacks.splice(index, 1);
}

function addGlobalSkill() {
    cliForm.value.cli_global_skills.push({
        name: "新 Skill",
        content: "",
        enabled: true,
    });
}

function removeGlobalSkill(index: number) {
    cliForm.value.cli_global_skills.splice(index, 1);
}

async function handleSaveCli() {
    savingCli.value = true;
    try {
        const cleaned: CLIFallback[] = [];
        for (const fb of cliForm.value.cli_fallbacks) {
            const mid = String(fb.model_id || "").trim();
            if (!mid) continue;
            cleaned.push({ tool: fb.tool || cliForm.value.cli_default_tool, model_id: mid });
        }
        const skillsPayload = cliForm.value.cli_global_skills
            .filter((s) => s.content && s.content.trim())
            .map((s) => ({
                id: s.id,
                name: s.name || "Skill",
                content: s.content.trim(),
                enabled: s.enabled !== false,
            }));
        await updateSettings({
            cli_default_tool: cliForm.value.cli_default_tool,
            cli_primary_model_id: cliForm.value.cli_primary_model_id,
            cli_fallbacks: cleaned,
            cli_global_skills: skillsPayload,
            auto_check_update: autoCheckUpdate.value,
        });
        cliForm.value.cli_fallbacks = [...cleaned];
        cliForm.value.cli_global_skills = skillsPayload;
        message.success("编码工具设置已保存");
    } catch {
        message.error("保存失败");
    } finally {
        savingCli.value = false;
    }
}

async function handleToolAction(toolName: string, action: "install" | "uninstall") {
    if (operatingTool.value) return;
    operatingTool.value = toolName;
    operationOutput.value = [];

    const url = `/api/admin/settings/cli-tools/${toolName}/${action}`;
    try {
        const resp = await fetch(url, {
            method: "POST",
            headers: { Authorization: `Bearer ${userStore.token}` },
        });
        if (!resp.ok || !resp.body) {
            message.error(`${action === "install" ? "安装" : "卸载"}请求失败`);
            operatingTool.value = "";
            return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";
            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                try {
                    const evt = JSON.parse(line.slice(6));
                    if (evt.type === "output") {
                        operationOutput.value.push(evt.text);
                    } else if (evt.type === "done") {
                        if (evt.success) {
                            message.success(`${action === "install" ? "安装" : "卸载"}成功`);
                        } else {
                            message.error(`${action === "install" ? "安装" : "卸载"}失败 (exit ${evt.exit_code})`);
                        }
                    } else if (evt.type === "error") {
                        message.error(evt.text);
                    }
                } catch { /* skip malformed */ }
            }
        }
    } catch (e: any) {
        message.error(e.message || "操作失败");
    } finally {
        operatingTool.value = "";
        try {
            const res: any = await getSettings();
            cliToolsStatus.value = Array.isArray(res?.cli_tools_status) ? res.cli_tools_status : [];
        } catch { /* ignore */ }
    }
}

onMounted(loadData);
</script>

<template>
    <VortSpin :spinning="loading">
        <!-- CLI Tool Management -->
        <div class="mb-6">
            <h4 class="text-sm font-medium text-gray-700 mb-3">CLI 工具管理</h4>
            <p class="text-xs text-gray-400 mb-4">管理编码任务使用的 CLI 工具。可在线安装和卸载。</p>
            <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                <div
                    v-for="tool in cliToolsStatus"
                    :key="tool.name"
                    class="border border-gray-200 rounded-lg p-4 flex flex-col justify-between"
                >
                    <div class="flex items-start gap-3">
                        <Terminal :size="20" class="text-gray-400 mt-0.5 shrink-0" />
                        <div class="min-w-0">
                            <div class="font-medium text-sm text-gray-800">{{ tool.display_name }}</div>
                            <div class="text-xs text-gray-400 mt-0.5">
                                <code class="bg-gray-100 px-1 rounded">{{ tool.binary }}</code>
                                <template v-if="tool.installed">
                                    <span class="mx-1">·</span>
                                    <span class="text-green-600">{{ tool.version || '已安装' }}</span>
                                </template>
                                <template v-else>
                                    <span class="mx-1">·</span>
                                    <span class="text-gray-400">未安装</span>
                                </template>
                            </div>
                            <div class="text-xs text-gray-400 mt-0.5 truncate">
                                {{ tool.install_cmd }}
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center justify-end gap-2 mt-3 pt-3 border-t border-gray-100">
                        <span v-if="tool.installed" class="inline-flex items-center gap-1 text-xs text-green-600 mr-auto">
                            <CheckCircle :size="14" /> 已安装
                        </span>
                        <span v-else class="inline-flex items-center gap-1 text-xs text-gray-400 mr-auto">
                            <XCircle :size="14" /> 未安装
                        </span>
                        <VortButton
                            v-if="!tool.installed"
                            size="small"
                            variant="primary"
                            :loading="operatingTool === tool.name"
                            @click="handleToolAction(tool.name, 'install')"
                        >
                            <Download :size="14" class="mr-1" /> 安装
                        </VortButton>
                        <VortButton
                            v-else
                            size="small"
                            :loading="operatingTool === tool.name"
                            @click="handleToolAction(tool.name, 'uninstall')"
                        >
                            <Trash2 :size="14" class="mr-1" /> 卸载
                        </VortButton>
                    </div>
                </div>
            </div>

            <!-- Operation output -->
            <div v-if="operationOutput.length > 0" class="mt-3 bg-gray-900 rounded-lg p-3 max-h-48 overflow-y-auto">
                <pre class="text-xs text-green-400 font-mono whitespace-pre-wrap"><template v-for="(line, i) in operationOutput" :key="i">{{ line }}
</template></pre>
            </div>
        </div>

        <VortDivider />

        <!-- System settings -->
        <div class="max-w-2xl mt-4">
            <p class="text-sm text-gray-500 mb-4">系统运行相关配置。</p>

            <div class="flex items-center justify-between py-3 border-b border-gray-100">
                <div>
                    <div class="text-sm font-medium text-gray-700">自动检查更新</div>
                    <div class="text-xs text-gray-400 mt-0.5">关闭后可避免 GitHub API 调用频率限制</div>
                </div>
                <VortSwitch v-model:checked="autoCheckUpdate" />
            </div>
        </div>

        <VortDivider />

        <!-- Coding tool config -->
        <VortForm label-width="130px" class="max-w-2xl mt-4">
            <p class="text-sm text-gray-500 mb-4">
                配置 AI 编码任务使用的 CLI 工具和模型。
            </p>

            <VortFormItem label="默认 CLI 工具">
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
                <div v-if="cliForm.cli_primary_model_id && !isModelCompatible(cliForm.cli_primary_model_id)" class="mt-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
                    <p class="text-xs text-amber-700">
                        当前模型的 Provider 不在所选 CLI 工具的支持列表中，可能无法正常工作。
                    </p>
                </div>
            </VortFormItem>

            <VortDivider />

            <div class="flex items-center justify-between mb-4">
                <h4 class="text-sm font-medium text-gray-700">备选方案（按顺序）</h4>
                <VortButton size="small" @click="addCliFallback">
                    <Plus :size="14" class="mr-1" /> 添加
                </VortButton>
            </div>
            <p class="text-xs text-gray-400 mb-4">编码任务失败时，按顺序尝试备选的 CLI 工具和模型组合重新执行。</p>

            <div v-for="(fb, i) in cliForm.cli_fallbacks" :key="i" class="border border-gray-200 rounded-lg p-4 mb-3 relative">
                <button class="absolute top-3 right-3 text-gray-400 hover:text-red-500" type="button" @click="removeCliFallback(i)">
                    <Trash2 :size="14" />
                </button>
                <div class="text-xs text-gray-500 mb-3">备选方案 #{{ i + 1 }}</div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                        <div class="text-xs text-gray-500 mb-1">CLI 工具</div>
                        <VortSelect v-model="cliForm.cli_fallbacks[i].tool" class="w-full" placeholder="选择 CLI 工具">
                            <VortSelectOption v-for="tool in cliTools" :key="tool.name" :value="tool.name">
                                {{ tool.display_name }}
                            </VortSelectOption>
                        </VortSelect>
                    </div>
                    <div>
                        <div class="text-xs text-gray-500 mb-1">编码模型</div>
                        <VortSelect v-model="cliForm.cli_fallbacks[i].model_id" class="w-full" placeholder="选择编码模型">
                            <VortSelectOption v-for="item in cliCompatibleModels" :key="item.id" :value="item.id">
                                {{ modelLabel(item) }}
                            </VortSelectOption>
                        </VortSelect>
                    </div>
                </div>
                <div v-if="fb.model_id && !isModelCompatibleWithTool(fb.model_id, fb.tool)" class="mt-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg">
                    <p class="text-xs text-amber-700">
                        此模型的 Provider 不在所选 CLI 工具的支持列表中，可能无法正常工作。
                    </p>
                </div>
            </div>

            <div v-if="cliForm.cli_fallbacks.length === 0" class="text-center py-4 text-gray-400 text-sm">
                暂无备选方案
            </div>

            <VortDivider />

            <!-- Global Coding Skills -->
            <div class="flex items-center justify-between mb-4">
                <h4 class="text-sm font-medium text-gray-700">全局编码规范</h4>
                <VortButton size="small" @click="addGlobalSkill">
                    <Plus :size="14" class="mr-1" /> 添加
                </VortButton>
            </div>
            <p class="text-xs text-gray-400 mb-4">
                配置全局编码规范（如「始终使用中文回复」），所有编码模型执行任务时会自动遵循这些规范。
            </p>

            <div v-for="(skill, i) in cliForm.cli_global_skills" :key="i" class="border border-gray-200 rounded-lg p-4 mb-3 relative">
                <button class="absolute top-3 right-3 text-gray-400 hover:text-red-500" type="button" @click="removeGlobalSkill(i)">
                    <Trash2 :size="14" />
                </button>
                <div class="grid grid-cols-1 gap-3">
                    <div class="flex items-center gap-3">
                        <div class="flex-1">
                            <div class="text-xs text-gray-500 mb-1">名称</div>
                            <VortInput v-model="skill.name" placeholder="Skill 名称" />
                        </div>
                        <div class="flex items-center h-full pt-5">
                            <vort-switch v-model:checked="skill.enabled" />
                            <span class="ml-2 text-xs text-gray-500">{{ skill.enabled ? '启用' : '禁用' }}</span>
                        </div>
                    </div>
                    <div>
                        <div class="text-xs text-gray-500 mb-1">规范内容</div>
                        <VortTextarea v-model="skill.content" placeholder="例如：使用简体中文进行思考和回复" :rows="2" />
                    </div>
                </div>
            </div>

            <div v-if="cliForm.cli_global_skills.length === 0" class="text-center py-4 text-gray-400 text-sm">
                暂无全局编码规范
            </div>

            <VortDivider />

            <VortFormItem>
                <VortButton variant="primary" :loading="savingCli" @click="handleSaveCli">
                    <Save :size="14" class="mr-1" /> 保存设置
                </VortButton>
            </VortFormItem>
        </VortForm>
    </VortSpin>
</template>
