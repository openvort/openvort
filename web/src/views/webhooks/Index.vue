<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import {
    getWebhooks, createWebhook, updateWebhook, deleteWebhook,
    getWebhookPresets, installWebhookPreset, getMembers,
} from "@/api";
import { message } from "@/components/vort";
import {
    Plus, Webhook, ExternalLink, Zap, Check, ChevronDown, ChevronUp,
    Globe, Github, Gitlab, Bot, BookOpen, Unlink,
} from "lucide-vue-next";

interface WebhookItem {
    name: string;
    secret: string;
    action_type: string;
    prompt_template: string;
    channel: string;
    user_id: string;
    member_id: string;
}

interface VirtualMember {
    id: string;
    name: string;
    position: string;
    virtual_role_name?: string;
}

interface PresetGuideStep {
    title: string;
    content: string;
}

interface PresetItem {
    id: string;
    name: string;
    display_name: string;
    icon: string;
    featured: boolean;
    description: string;
    homepage: string;
    installed: boolean;
    config: Record<string, string>;
    guide?: {
        title: string;
        steps: PresetGuideStep[];
        capabilities?: string[];
    };
}

const loading = ref(false);
const list = ref<WebhookItem[]>([]);
const presets = ref<PresetItem[]>([]);
const virtualMembers = ref<VirtualMember[]>([]);
const dialogOpen = ref(false);
const editing = ref(false);
const editingName = ref("");
const saving = ref(false);
const expandedPreset = ref<string | null>(null);

// Preset install dialog
const installDialogOpen = ref(false);
const installDialogPreset = ref<PresetItem | null>(null);
const installForm = ref({ name: "", secret: "", member_id: "" });
const installing = ref(false);

const form = ref<WebhookItem>({
    name: "", secret: "", action_type: "agent_chat",
    prompt_template: "", channel: "webhook", user_id: "webhook", member_id: "",
});

const featuredPresets = computed(() => presets.value.filter(p => p.featured));
const otherPresets = computed(() => presets.value.filter(p => !p.featured));

const memberMap = computed(() => {
    const map: Record<string, VirtualMember> = {};
    for (const m of virtualMembers.value) {
        map[m.id] = m;
    }
    return map;
});

function getPresetIcon(icon: string) {
    const map: Record<string, any> = {
        lobster: Bot, github: Github, gitlab: Gitlab, globe: Globe,
    };
    return map[icon] || Webhook;
}

async function loadData() {
    loading.value = true;
    try {
        const [whRes, presetRes, memberRes] = await Promise.all([
            getWebhooks(),
            getWebhookPresets(),
            getMembers({ is_virtual: true, size: 200 }),
        ]);
        list.value = Array.isArray(whRes) ? whRes : [];
        presets.value = Array.isArray(presetRes) ? presetRes : [];
        const items = (memberRes as any)?.members || (memberRes as any)?.items || (memberRes as any)?.records || [];
        virtualMembers.value = Array.isArray(items) ? items : [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

function togglePresetGuide(id: string) {
    expandedPreset.value = expandedPreset.value === id ? null : id;
}

function openInstallDialog(preset: PresetItem) {
    installDialogPreset.value = preset;
    installForm.value = { name: preset.name, secret: "", member_id: "" };
    installDialogOpen.value = true;
}

async function confirmInstallPreset() {
    const preset = installDialogPreset.value;
    if (!preset) return;
    installing.value = true;
    try {
        const res: any = await installWebhookPreset(preset.id, {
            secret: installForm.value.secret,
            member_id: installForm.value.member_id,
            name: installForm.value.name,
        });
        if (res?.success) {
            message.success(`${preset.display_name} Webhook 已创建`);
            installDialogOpen.value = false;
            await loadData();
        } else {
            message.error(res?.error || "安装失败");
        }
    } catch {
        message.error("安装失败");
    } finally {
        installing.value = false;
    }
}

function handleAdd() {
    editing.value = false;
    editingName.value = "";
    form.value = { name: "", secret: "", action_type: "agent_chat", prompt_template: "", channel: "webhook", user_id: "webhook", member_id: "" };
    dialogOpen.value = true;
}

function handleEdit(row: WebhookItem) {
    editing.value = true;
    editingName.value = row.name;
    form.value = { ...row, member_id: row.member_id || "" };
    dialogOpen.value = true;
}

async function handleSave() {
    if (!form.value.name.trim()) {
        message.error("名称不能为空");
        return;
    }
    saving.value = true;
    try {
        if (editing.value) {
            await updateWebhook(editingName.value, form.value);
        } else {
            await createWebhook(form.value);
        }
        message.success(editing.value ? "更新成功" : "创建成功");
        dialogOpen.value = false;
        await loadData();
    } catch {
        message.error("操作失败");
    } finally { saving.value = false; }
}

onMounted(loadData);
</script>

<template>
    <div class="space-y-5">
        <!-- Featured: OpenClaw Integration Banner -->
        <div v-for="preset in featuredPresets" :key="preset.id"
            class="relative overflow-hidden rounded-xl border-2 transition-all duration-200"
            :class="preset.installed
                ? 'border-green-200 bg-gradient-to-r from-green-50 to-emerald-50'
                : 'border-indigo-200 bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 hover:border-indigo-300'"
        >
            <div class="p-6">
                <div class="flex items-start justify-between">
                    <div class="flex items-start gap-4">
                        <div class="flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-white"
                            :class="preset.installed ? 'bg-green-500' : 'bg-gradient-to-br from-indigo-500 to-purple-600'"
                        >
                            <component :is="getPresetIcon(preset.icon)" :size="24" />
                        </div>
                        <div>
                            <div class="flex items-center gap-2 mb-1">
                                <h3 class="text-lg font-semibold text-gray-900">{{ preset.display_name }}</h3>
                                <VortTag v-if="preset.installed" color="green">已启用</VortTag>
                                <VortTag v-else color="blue">推荐</VortTag>
                            </div>
                            <p class="text-sm text-gray-600 max-w-2xl">{{ preset.description }}</p>
                            <!-- Capabilities -->
                            <div v-if="preset.guide?.capabilities" class="mt-3 flex flex-wrap gap-2">
                                <span v-for="cap in preset.guide.capabilities" :key="cap"
                                    class="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-white/70 text-gray-600 border border-gray-200">
                                    <Zap :size="10" class="text-amber-500" />
                                    {{ cap }}
                                </span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0 ml-4">
                        <a v-if="preset.homepage" :href="preset.homepage" target="_blank"
                            class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors">
                            <ExternalLink :size="12" /> 项目主页
                        </a>
                        <VortButton v-if="!preset.installed" variant="primary" @click="openInstallDialog(preset)">
                            <Zap :size="14" class="mr-1" /> 启用集成
                        </VortButton>
                        <VortButton v-else variant="default" disabled>
                            <Check :size="14" class="mr-1" /> 已启用
                        </VortButton>
                    </div>
                </div>

                <!-- Expandable Guide -->
                <div class="mt-4">
                    <button @click="togglePresetGuide(preset.id)"
                        class="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700 transition-colors">
                        <BookOpen :size="14" />
                        {{ expandedPreset === preset.id ? '收起' : '查看' }}集成指南
                        <component :is="expandedPreset === preset.id ? ChevronUp : ChevronDown" :size="14" />
                    </button>

                    <div v-if="expandedPreset === preset.id && preset.guide" class="mt-4 space-y-3">
                        <h4 class="text-sm font-semibold text-gray-800">{{ preset.guide.title }}</h4>
                        <div v-for="(step, idx) in preset.guide.steps" :key="idx"
                            class="bg-white rounded-lg border border-gray-200 p-4">
                            <div class="flex items-start gap-3">
                                <span class="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-600 text-xs font-bold flex items-center justify-center">
                                    {{ idx + 1 }}
                                </span>
                                <div class="min-w-0">
                                    <div class="text-sm font-medium text-gray-800 mb-1">{{ step.title }}</div>
                                    <div class="text-sm text-gray-600 whitespace-pre-wrap font-mono leading-relaxed">{{ step.content }}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Other Preset Templates -->
        <div v-if="otherPresets.length" class="bg-white rounded-xl p-6">
            <h3 class="text-base font-medium text-gray-800 mb-3">更多集成模板</h3>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                <div v-for="preset in otherPresets" :key="preset.id"
                    class="flex items-center justify-between p-3 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors">
                    <div class="flex items-center gap-3">
                        <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-gray-100 text-gray-600">
                            <component :is="getPresetIcon(preset.icon)" :size="16" />
                        </div>
                        <div>
                            <div class="text-sm font-medium text-gray-800">{{ preset.display_name }}</div>
                            <div class="text-xs text-gray-500">{{ preset.description.slice(0, 40) }}...</div>
                        </div>
                    </div>
                    <VortButton v-if="!preset.installed" size="small" @click="openInstallDialog(preset)">
                        启用
                    </VortButton>
                    <VortTag v-else color="green" class="text-xs">已启用</VortTag>
                </div>
            </div>
        </div>

        <!-- Custom Webhooks Table -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <div>
                    <h3 class="text-base font-medium text-gray-800">自定义 Webhook</h3>
                    <p class="text-sm text-gray-500 mt-1">
                        接收外部 HTTP 请求触发 Agent 动作。调用地址：<code class="text-xs bg-gray-100 px-1.5 py-0.5 rounded">POST /api/webhooks/&lt;name&gt;</code>
                    </p>
                </div>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增 Webhook
                </VortButton>
            </div>

            <VortTable :data-source="list" :loading="loading" row-key="name" :pagination="false">
                <VortTableColumn label="名称" prop="name" :width="160">
                    <template #default="{ row }">
                        <div class="flex items-center gap-1.5">
                            <component :is="getPresetIcon(row.name === 'openclaw' ? 'lobster' : row.name?.startsWith('github') ? 'github' : row.name?.startsWith('gitlab') ? 'gitlab' : 'globe')" :size="14" class="text-gray-400" />
                            <span>{{ row.name }}</span>
                        </div>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="动作类型" prop="action_type" :width="140">
                    <template #default="{ row }">
                        <VortTag :color="row.action_type === 'openclaw_bridge' ? 'purple' : row.action_type === 'agent_chat' ? 'blue' : 'green'">
                            {{ row.action_type === 'openclaw_bridge' ? 'OpenClaw 桥接' : row.action_type === 'agent_chat' ? 'Agent 对话' : '通知' }}
                        </VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="绑定员工" :width="150">
                    <template #default="{ row }">
                        <div v-if="row.member_id && memberMap[row.member_id]" class="flex items-center gap-1.5">
                            <Bot :size="14" class="text-purple-500" />
                            <span class="text-sm">{{ memberMap[row.member_id].name }}</span>
                        </div>
                        <span v-else class="text-xs text-gray-400 flex items-center gap-1">
                            <Unlink :size="12" /> 未绑定
                        </span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="签名密钥" :width="100">
                    <template #default="{ row }">
                        <VortTag :color="row.secret ? 'green' : 'default'">
                            {{ row.secret ? '已配置' : '无' }}
                        </VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="目标通道" prop="channel" :width="120" />
                <VortTableColumn label="Prompt 模板" prop="prompt_template">
                    <template #default="{ row }">
                        <span class="text-gray-500 text-xs">{{ row.prompt_template || '使用默认模板' }}</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="160" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleEdit(row)">编辑</a>
                            <VortDivider type="vertical" />
                            <VortPopconfirm title="确认删除？" @confirm="async () => { await deleteWebhook(row.name); await loadData(); }">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </VortPopconfirm>
                        </div>
                    </template>
                </VortTableColumn>
            </VortTable>
        </div>

        <!-- 新增/编辑弹窗 -->
        <VortDialog :open="dialogOpen" :title="editing ? '编辑 Webhook' : '新增 Webhook'" @update:open="dialogOpen = $event">
            <VortForm label-width="110px" class="mt-2">
                <VortFormItem label="名称" required>
                    <VortInput v-model="form.name" placeholder="如 github-push" :disabled="editing" />
                </VortFormItem>
                <VortFormItem label="动作类型">
                    <VortSelect v-model="form.action_type" class="w-full">
                        <VortSelectOption value="agent_chat">Agent 对话</VortSelectOption>
                        <VortSelectOption value="notify">通知</VortSelectOption>
                        <VortSelectOption value="openclaw_bridge">OpenClaw 桥接</VortSelectOption>
                    </VortSelect>
                </VortFormItem>
                <VortFormItem label="签名密钥">
                    <VortInputPassword v-model="form.secret" placeholder="留空则不验证签名" />
                </VortFormItem>
                <VortFormItem v-if="form.action_type !== 'notify'" label="绑定 AI 员工">
                    <VortSelect v-model="form.member_id" placeholder="不绑定（使用默认 Agent）" allow-clear class="w-full">
                        <VortSelectOption v-for="m in virtualMembers" :key="m.id" :value="m.id">
                            {{ m.name }}{{ m.position ? ` · ${m.position}` : (m.virtual_role_name ? ` · ${m.virtual_role_name}` : '') }}
                        </VortSelectOption>
                    </VortSelect>
                    <p class="text-xs text-gray-400 mt-1">绑定后，此 Webhook 收到的消息将由该 AI 员工的身份和技能响应</p>
                </VortFormItem>
                <VortFormItem label="目标通道">
                    <VortInput v-model="form.channel" placeholder="webhook" />
                </VortFormItem>
                <VortFormItem label="目标用户">
                    <VortInput v-model="form.user_id" placeholder="webhook" />
                </VortFormItem>
                <VortFormItem label="Prompt 模板">
                    <VortTextarea v-model="form.prompt_template" placeholder="支持 {event} {payload} 占位符，留空使用默认" :auto-size="{ minRows: 3, maxRows: 6 }" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="dialogOpen = false">取消</VortButton>
                <VortButton variant="primary" :loading="saving" @click="handleSave" class="ml-3">确定</VortButton>
            </template>
        </VortDialog>

        <!-- 预置模板安装配置弹窗 -->
        <VortDialog :open="installDialogOpen" :title="`配置 ${installDialogPreset?.display_name || ''} 集成`" @update:open="installDialogOpen = $event">
            <VortForm label-width="110px" class="mt-2">
                <VortFormItem label="Webhook 名称" required>
                    <VortInput v-model="installForm.name" placeholder="openclaw" />
                    <p class="text-xs text-gray-400 mt-1">
                        调用地址：<code class="bg-gray-100 px-1 py-0.5 rounded">POST /api/webhooks/{{ installForm.name || '...' }}</code>
                    </p>
                </VortFormItem>
                <VortFormItem label="签名密钥">
                    <VortInputPassword v-model="installForm.secret" placeholder="与外部平台的 token 保持一致" />
                </VortFormItem>
                <VortFormItem label="绑定 AI 员工">
                    <VortSelect v-model="installForm.member_id" placeholder="选择 AI 员工（可选）" allow-clear class="w-full">
                        <VortSelectOption v-for="m in virtualMembers" :key="m.id" :value="m.id">
                            {{ m.name }}{{ m.position ? ` · ${m.position}` : (m.virtual_role_name ? ` · ${m.virtual_role_name}` : '') }}
                        </VortSelectOption>
                    </VortSelect>
                    <p class="text-xs text-gray-400 mt-1">该员工将作为 AI 身份响应来自外部平台的所有消息</p>
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="installDialogOpen = false">取消</VortButton>
                <VortButton variant="primary" :loading="installing" @click="confirmInstallPreset" class="ml-3">启用</VortButton>
            </template>
        </VortDialog>
    </div>
</template>
