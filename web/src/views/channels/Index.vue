<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { getChannels, getChannelDetail, updateChannel, toggleChannel, testChannel, getChannelBots, getChannelBotSummary, type ChannelBotItem } from "@/api";
import { message } from "@openvort/vort-ui";
import { CheckCircle, XCircle, Settings, Zap, ChevronRight, Bot, Users } from "lucide-vue-next";
import AiAssistButton from "@/components/vort-biz/ai-assist-button/AiAssistButton.vue";

interface ConfigField {
    key: string;
    label: string;
    type: string;
    required: boolean;
    secret: boolean;
    placeholder: string;
    description?: string;
    help_url?: string;
    group?: string;
    mode?: string;
}

interface ConfigMode {
    key: string;
    label: string;
    description?: string;
    recommended?: boolean;
}

interface ConnectionInfo {
    mode: string;
}

interface ChannelInfo {
    name: string;
    display_name: string;
    description: string;
    type: string;
    status: string;
    enabled: boolean;
}

interface ChannelDetail extends ChannelInfo {
    config_schema: ConfigField[];
    config: Record<string, any>;
    config_modes?: ConfigMode[];
    connection?: ConnectionInfo;
    setup_guide?: string;
}

const channels = ref<ChannelInfo[]>([]);
const loading = ref(false);

const drawerOpen = ref(false);
const drawerLoading = ref(false);
const saving = ref(false);
const testing = ref(false);
const testResult = ref<{ ok: boolean; message: string } | null>(null);
const currentChannel = ref<ChannelDetail | null>(null);
const configForm = ref<Record<string, any>>({});

const selectedMode = ref("bot");
const showAdvanced = ref(false);
const showAppOptional = ref(false);

const hasModes = computed(() => (currentChannel.value?.config_modes?.length ?? 0) > 0);

const isOtherModeGroup = (f: ConfigField) => f.group === "app" && selectedMode.value !== "app";

const visibleFields = computed(() => {
    const schema = currentChannel.value?.config_schema || [];
    if (!hasModes.value) return schema.filter((f) => f.group !== "advanced");
    return schema.filter(
        (f) =>
            f.group !== "advanced" &&
            !isOtherModeGroup(f) &&
            (f.mode === "all" || f.mode === selectedMode.value),
    );
});

const appOptionalFields = computed(() => {
    if (!hasModes.value || selectedMode.value === "app") return [];
    const schema = currentChannel.value?.config_schema || [];
    return schema.filter((f) => f.group === "app" && f.mode === "all");
});

const advancedFields = computed(() => {
    const schema = currentChannel.value?.config_schema || [];
    if (!hasModes.value) return schema.filter((f) => f.group === "advanced");
    return schema.filter(
        (f) => f.group === "advanced" && (f.mode === "all" || f.mode === selectedMode.value),
    );
});

function detectMode(config: Record<string, any>): string {
    if (config.bot_id || config.bot_secret) return "bot";
    if (config.app_secret || config.agent_id) return "app";
    return "bot";
}

async function loadChannels() {
    loading.value = true;
    try {
        const res: any = await getChannels();
        channels.value = res?.channels || [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

async function openConfig(name: string) {
    drawerOpen.value = true;
    drawerLoading.value = true;
    testResult.value = null;
    currentChannel.value = null;
    configForm.value = {};
    showAdvanced.value = false;
    showAppOptional.value = false;
    try {
        const res: any = await getChannelDetail(name);
        if (!res || !res.name) {
            message.error("获取通道配置失败：响应格式异常");
            return;
        }
        currentChannel.value = res;
        configForm.value = { ...(res.config || {}) };
        if (res.config_modes?.length) {
            selectedMode.value = detectMode(res.config || {});
        }
    } catch {
        message.error("获取通道配置失败");
    } finally {
        drawerLoading.value = false;
    }
}

async function handleSave() {
    if (!currentChannel.value) return;
    saving.value = true;
    try {
        await updateChannel(currentChannel.value.name, configForm.value);
        message.success("保存成功");
        await loadChannels();
        const res: any = await getChannelDetail(currentChannel.value.name);
        currentChannel.value = res;
        configForm.value = { ...(res?.config || {}) };
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
}

async function handleTest() {
    if (!currentChannel.value) return;
    testing.value = true;
    testResult.value = null;
    try {
        const res: any = await testChannel(currentChannel.value.name);
        testResult.value = res;
    } catch {
        testResult.value = { ok: false, message: "请求失败" };
    } finally {
        testing.value = false;
    }
}

async function handleToggle(row: ChannelInfo) {
    try {
        const res: any = await toggleChannel(row.name);
        row.enabled = res.enabled;
        message.success(res.enabled ? "已启用" : "已禁用");
    } catch {
        message.error("操作失败");
    }
}

function renderGuide(md: string): string {
    return md
        .replace(/### (.+)/g, '<h4 class="text-sm font-semibold text-gray-800 mb-2">$1</h4>')
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-blue-100 rounded text-xs">$1</code>')
        .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" target="_blank" class="text-blue-600 underline">$1</a>')
        .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>')
        .replace(/(<li.*<\/li>\n?)+/g, '<ol class="space-y-1 mb-2">$&</ol>');
}

const modeLabels: Record<string, string> = {
    bot: "智能机器人",
    stream: "Stream 长连接",
    websocket: "WebSocket 长连接",
    webhook: "Webhook 回调",
    event_subscription: "事件订阅",
    "未启动": "未启动",
    unknown: "未知",
};

const CHANNEL_ICON_PATHS: Record<string, string> = {
    dingtalk: "/icons/dingtalk.svg",
    feishu: "/icons/feishu.svg",
    wecom: "/icons/wecom.svg",
    openclaw: "/icons/openclaw.svg",
};

function getChannelIconUrl(name: string): string | null {
    return CHANNEL_ICON_PATHS[name?.toLowerCase()] ?? null;
}

const setupGuides: Record<string, Record<string, string>> = {
    wecom: {
        bot: '1. 登录<a href="https://work.weixin.qq.com/wework_admin/frame" target="_blank" class="text-blue-600 underline">企业微信管理后台</a>，复制<strong>企业 ID</strong><br>2. 进入「智能机器人」→ 创建 AI 同事，获取 <strong>Bot ID</strong> 和 <strong>Secret</strong><br>3. 保存后自动使用 WebSocket 长连接（无需公网 IP）',
        app: '1. 登录<a href="https://work.weixin.qq.com/wework_admin/frame" target="_blank" class="text-blue-600 underline">企业微信管理后台</a>，复制<strong>企业 ID</strong><br>2. 进入「应用管理」→「自建」→ 创建应用，获取 <strong>AgentId</strong> 和 <strong>Secret</strong><br>3. 如需 Webhook：设置接收服务器，获取 <strong>Token</strong> 和 <strong>AES Key</strong>',
    },
};

const currentGuideHtml = computed(() => {
    const ch = currentChannel.value;
    if (!ch) return "";
    const channelGuides = setupGuides[ch.name];
    if (channelGuides?.[selectedMode.value]) return channelGuides[selectedMode.value];
    if (ch.setup_guide) return renderGuide(ch.setup_guide);
    return "";
});

// ---- Bot summary ----

const botCounts = ref<Record<string, number>>({});
const botListOpen = ref(false);
const botListChannel = ref("");
const botListLoading = ref(false);
const botListItems = ref<(ChannelBotItem & { member_name?: string })[]>([]);

async function loadBotSummary() {
    try {
        const res: any = await getChannelBotSummary();
        botCounts.value = res?.counts || {};
    } catch { /* ignore */ }
}

async function openBotList(channelName: string) {
    botListChannel.value = channelName;
    botListOpen.value = true;
    botListLoading.value = true;
    try {
        const res: any = await getChannelBots({ channel_type: channelName });
        botListItems.value = res?.bots || [];
    } catch { botListItems.value = []; }
    finally { botListLoading.value = false; }
}

const CHANNEL_LABELS: Record<string, string> = {
    wecom: "企业微信",
    dingtalk: "钉钉",
    feishu: "飞书",
    openclaw: "OpenClaw",
};

onMounted(() => {
    loadChannels();
    loadBotSummary();
});
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-2">
                <h3 class="text-base font-medium text-gray-800">通道管理</h3>
                <AiAssistButton
                    label="AI 助手配置"
                    prompt="我需要配置 IM 通道，请帮我了解可用的通道并引导我完成配置。请先列出所有可用通道和它们的状态，然后根据我的选择逐步引导配置。"
                />
            </div>
            <p class="text-sm text-gray-400 mb-4">管理 IM 通道的连接配置，每个通道对应一个消息平台。配置完成后 AI 可通过该通道收发消息。</p>

            <VortTable :data-source="channels" :loading="loading" row-key="name" :pagination="false">
                <VortTableColumn label="通道名称" prop="display_name">
                    <template #default="{ row }">
                        <div class="flex items-center">
                            <span class="w-5 h-5 shrink-0 mr-2 flex items-center justify-center">
                                <img
                                    v-if="getChannelIconUrl(row.name)"
                                    :src="getChannelIconUrl(row.name)!"
                                    :alt="row.display_name"
                                    class="w-full h-full object-contain"
                                />
                                <img
                                    v-else
                                    src="/icons/openclaw.svg"
                                    :alt="row.display_name"
                                    class="w-full h-full object-contain"
                                />
                            </span>
                            <div>
                                <span class="font-medium">{{ row.display_name }}</span>
                                <p v-if="row.description" class="text-xs text-gray-400 mt-0.5">{{ row.description }}</p>
                            </div>
                        </div>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="标识" prop="name" :width="120" />
                <VortTableColumn label="独立 Bot" :width="120">
                    <template #default="{ row }">
                        <div class="flex items-center gap-1.5">
                            <template v-if="botCounts[row.name]">
                                <vort-tag color="blue" size="small">
                                    <Bot :size="11" class="mr-0.5" />
                                    {{ botCounts[row.name] }}
                                </vort-tag>
                                <a class="text-xs text-blue-600 cursor-pointer hover:underline" @click.stop="openBotList(row.name)">查看</a>
                            </template>
                            <span v-else class="text-xs text-gray-300">-</span>
                        </div>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="状态" prop="status" :width="100">
                    <template #default="{ row }">
                        <span class="flex items-center text-sm" :class="row.status === 'connected' ? 'text-green-600' : 'text-gray-400'">
                            <CheckCircle v-if="row.status === 'connected'" :size="14" class="mr-1" />
                            <XCircle v-else :size="14" class="mr-1" />
                            {{ row.status === 'connected' ? '已连接' : '未连接' }}
                        </span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="启用" prop="enabled" :width="80">
                    <template #default="{ row }">
                        <VortSwitch :checked="row.enabled" @change="handleToggle(row)" />
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="160">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2">
                            <VortButton size="small" @click="openConfig(row.name)">
                                <Settings :size="14" class="mr-1" /> 配置
                            </VortButton>
                        </div>
                    </template>
                </VortTableColumn>
            </VortTable>
        </div>

        <!-- 配置抽屉 -->
        <VortDrawer
            :open="drawerOpen"
            :title="currentChannel ? currentChannel.display_name + ' 配置' : '通道配置'"
            :width="520"
            @update:open="drawerOpen = $event"
            @close="drawerOpen = false"
            destroy-on-close
        >
            <VortSpin :spinning="drawerLoading">
                <template v-if="currentChannel">
                    <!-- 模式选择 -->
                    <div v-if="hasModes" class="mb-5">
                        <div class="text-sm font-medium text-gray-700 mb-2">连接方式</div>
                        <div class="grid grid-cols-2 gap-3">
                            <div
                                v-for="m in currentChannel.config_modes"
                                :key="m.key"
                                class="cursor-pointer rounded-lg border-2 p-3 transition-colors"
                                :class="selectedMode === m.key
                                    ? 'border-blue-500 bg-blue-50'
                                    : 'border-gray-200 hover:border-gray-300'"
                                @click="selectedMode = m.key"
                            >
                                <div class="flex items-center gap-1.5">
                                    <span class="text-sm font-medium" :class="selectedMode === m.key ? 'text-blue-700' : 'text-gray-700'">{{ m.label }}</span>
                                    <vort-tag v-if="m.recommended" color="blue" size="small">推荐</vort-tag>
                                </div>
                                <div class="text-xs text-gray-400 mt-1">{{ m.description }}</div>
                            </div>
                        </div>
                    </div>

                    <!-- 精简引导 -->
                    <div v-if="currentGuideHtml" class="mb-5 px-3 py-2.5 bg-blue-50 rounded-lg text-sm text-gray-600 leading-relaxed" v-html="currentGuideHtml" />

                    <!-- 表单 -->
                    <VortForm label-width="120px">
                        <VortFormItem
                            v-for="field in visibleFields"
                            :key="field.key"
                            :label="field.label"
                            :required="field.required || (field.group === 'app' && selectedMode === 'app')"
                            :tooltip="field.description"
                        >
                            <vort-input-password
                                v-if="field.secret"
                                v-model="configForm[field.key]"
                                :placeholder="field.placeholder"
                            />
                            <vort-input
                                v-else
                                v-model="configForm[field.key]"
                                :placeholder="field.placeholder"
                            />
                        </VortFormItem>
                    </VortForm>

                    <!-- 自建应用配置（Bot 模式下可选） -->
                    <div v-if="appOptionalFields.length" class="mt-1">
                        <button
                            class="flex items-center text-sm text-gray-400 hover:text-gray-600 transition-colors"
                            @click="showAppOptional = !showAppOptional"
                        >
                            <ChevronRight
                                :size="14"
                                class="mr-1 transition-transform duration-200"
                                :class="showAppOptional ? 'rotate-90' : ''"
                            />
                            自建应用配置（可选）
                        </button>
                        <p v-if="showAppOptional" class="text-xs text-gray-400 mt-2 mb-3">填写后可启用通讯录同步等功能</p>
                        <div v-show="showAppOptional" class="mt-1">
                            <VortForm label-width="120px">
                                <VortFormItem
                                    v-for="field in appOptionalFields"
                                    :key="field.key"
                                    :label="field.label"
                                    :tooltip="field.description"
                                >
                                    <vort-input-password
                                        v-if="field.secret"
                                        v-model="configForm[field.key]"
                                        :placeholder="field.placeholder"
                                    />
                                    <vort-input
                                        v-else
                                        v-model="configForm[field.key]"
                                        :placeholder="field.placeholder"
                                    />
                                </VortFormItem>
                            </VortForm>
                        </div>
                    </div>

                    <!-- 高级设置 -->
                    <div v-if="advancedFields.length" class="mt-1">
                        <button
                            class="flex items-center text-sm text-gray-400 hover:text-gray-600 transition-colors"
                            @click="showAdvanced = !showAdvanced"
                        >
                            <ChevronRight
                                :size="14"
                                class="mr-1 transition-transform duration-200"
                                :class="showAdvanced ? 'rotate-90' : ''"
                            />
                            高级设置
                        </button>
                        <div v-show="showAdvanced" class="mt-3">
                            <VortForm label-width="120px">
                                <VortFormItem
                                    v-for="field in advancedFields"
                                    :key="field.key"
                                    :label="field.label"
                                    :tooltip="field.description"
                                >
                                    <vort-input
                                        v-model="configForm[field.key]"
                                        :placeholder="field.placeholder"
                                    />
                                </VortFormItem>
                            </VortForm>
                        </div>
                    </div>

                    <!-- 连接状态 -->
                    <div v-if="currentChannel.connection" class="mt-4 flex items-center gap-2 text-sm text-gray-500">
                        <span>当前运行模式：</span>
                        <vort-tag>{{ modeLabels[currentChannel.connection.mode] || currentChannel.connection.mode }}</vort-tag>
                    </div>

                    <!-- 测试结果 -->
                    <div v-if="testResult" class="mt-4">
                        <VortAlert
                            :type="testResult.ok ? 'success' : 'error'"
                            :message="testResult.ok ? '连接成功' : '连接失败'"
                            :description="testResult.message"
                            show-icon
                        />
                    </div>
                </template>
            </VortSpin>

            <template #footer>
                <div class="flex justify-end gap-3">
                    <VortButton :loading="testing" @click="handleTest">
                        <Zap :size="14" class="mr-1" /> 测试连接
                    </VortButton>
                    <VortButton variant="primary" :loading="saving" @click="handleSave">
                        保存配置
                    </VortButton>
                </div>
            </template>
        </VortDrawer>
        <!-- Bot 列表抽屉 -->
        <VortDrawer
            v-model:open="botListOpen"
            :title="`${CHANNEL_LABELS[botListChannel] || botListChannel} 独立 Bot`"
            :width="480"
        >
            <VortSpin :spinning="botListLoading">
                <div v-if="botListItems.length" class="space-y-2">
                    <div
                        v-for="bot in botListItems" :key="bot.id"
                        class="flex items-center justify-between p-3 rounded-lg border border-gray-100 hover:bg-gray-50"
                    >
                        <div class="flex items-center gap-3 min-w-0">
                            <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
                                <Bot :size="16" class="text-blue-600" />
                            </div>
                            <div class="min-w-0">
                                <div class="text-sm font-medium text-gray-700">{{ bot.member_id }}</div>
                                <div class="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
                                    <span
                                        class="w-1.5 h-1.5 rounded-full"
                                        :class="bot.last_test_ok ? 'bg-green-500' : 'bg-gray-300'"
                                    />
                                    {{ bot.last_test_ok ? '已连接' : '未测试' }}
                                </div>
                            </div>
                        </div>
                        <vort-tag size="small" :color="bot.status === 'active' ? 'green' : 'default'">
                            {{ bot.status === 'active' ? '启用' : '停用' }}
                        </vort-tag>
                    </div>
                </div>
                <div v-else class="text-center py-12 text-sm text-gray-400">
                    <Users :size="32" class="mx-auto text-gray-300 mb-3" />
                    该通道暂无独立 Bot 绑定
                </div>
                <div class="mt-4 text-xs text-gray-400 text-center">
                    Bot 绑定在「AI 员工」详情中管理
                </div>
            </VortSpin>
        </VortDrawer>
    </div>
</template>
