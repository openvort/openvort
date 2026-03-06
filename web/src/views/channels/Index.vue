<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getChannels, getChannelDetail, updateChannel, toggleChannel, testChannel } from "@/api";
import { message } from "@/components/vort";
import { CheckCircle, XCircle, Settings, Zap, Download } from "lucide-vue-next";
import { useUserStore } from "@/stores";
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
}

interface ConnectionInfo {
    mode: string;
    relay_url?: string;
    relay_secret?: string;
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
    connection?: ConnectionInfo;
    setup_guide?: string;
}

const channels = ref<ChannelInfo[]>([]);
const loading = ref(false);

// 抽屉状态
const drawerOpen = ref(false);
const drawerLoading = ref(false);
const saving = ref(false);
const testing = ref(false);
const testResult = ref<{ ok: boolean; message: string } | null>(null);
const currentChannel = ref<ChannelDetail | null>(null);
const configForm = ref<Record<string, any>>({});

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
    try {
        const res: any = await getChannelDetail(name);
        if (!res || !res.name) {
            message.error("获取通道配置失败：响应格式异常");
            return;
        }
        currentChannel.value = res;
        configForm.value = { ...(res.config || {}) };
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
        // 刷新详情
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

function handleDownloadDeploy() {
    if (!currentChannel.value) return;
    const userStore = useUserStore();
    window.open(
        `/api/admin/channels/${currentChannel.value.name}/deploy-package?token=${encodeURIComponent(userStore.token)}`,
        "_blank",
    );
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
    relay: "Relay 中继",
    webhook: "Webhook 回调",
    "poll-db": "数据库轮询",
    "未启动": "未启动",
    unknown: "未知",
};

// Channel icons: local SVG in /icons/ (public folder)
const CHANNEL_ICON_PATHS: Record<string, string> = {
    dingtalk: "/icons/dingtalk.svg",
    feishu: "/icons/feishu.svg",
    wecom: "/icons/wecom.svg",
    openclaw: "/icons/openclaw.svg",
};

function getChannelIconUrl(name: string): string | null {
    const path = CHANNEL_ICON_PATHS[name?.toLowerCase()];
    return path ?? null;
}

onMounted(loadChannels);
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
            :width="480"
            @update:open="drawerOpen = $event"
            @close="drawerOpen = false"
            destroy-on-close
        >
            <VortSpin :spinning="drawerLoading">
                <template v-if="currentChannel">
                    <!-- 配置引导说明 -->
                    <div v-if="currentChannel.setup_guide" class="mb-5 p-4 bg-blue-50 rounded-lg text-sm text-gray-700 leading-relaxed setup-guide" v-html="renderGuide(currentChannel.setup_guide)" />

                    <VortForm label-width="140px">
                        <VortFormItem
                            v-for="field in currentChannel.config_schema"
                            :key="field.key"
                            :label="field.label"
                            :required="field.required"
                        >
                            <div class="w-full">
                                <VortInput
                                    v-model="configForm[field.key]"
                                    :type="field.secret ? 'password' : 'text'"
                                    :placeholder="field.placeholder"
                                />
                                <p v-if="field.description" class="text-xs text-gray-400 mt-1">{{ field.description }}</p>
                            </div>
                        </VortFormItem>
                    </VortForm>

                    <!-- 连接模式 -->
                    <VortDivider />
                    <h4 class="text-sm font-medium text-gray-700 mb-3">连接模式</h4>
                    <div v-if="currentChannel.connection" class="space-y-2 text-sm text-gray-600">
                        <div class="flex">
                            <span class="w-[140px] text-right pr-3 text-gray-500 shrink-0">当前模式</span>
                            <VortTag>{{ modeLabels[currentChannel.connection.mode] || currentChannel.connection.mode }}</VortTag>
                        </div>
                        <template v-if="currentChannel.connection.relay_url">
                            <div class="flex">
                                <span class="w-[140px] text-right pr-3 text-gray-500 shrink-0">Relay 地址</span>
                                <span class="font-mono">{{ currentChannel.connection.relay_url }}</span>
                            </div>
                            <div class="flex">
                                <span class="w-[140px] text-right pr-3 text-gray-500 shrink-0">Relay 密钥</span>
                                <span class="font-mono">{{ currentChannel.connection.relay_secret || '未设置' }}</span>
                            </div>
                        </template>
                        <div class="mt-2">
                            <VortAlert type="info" message="连接模式通过启动参数或环境变量配置，修改后需重启服务" />
                        </div>
                        <div class="mt-3">
                            <VortButton size="small" @click="handleDownloadDeploy">
                                <Download :size="14" class="mr-1" /> 下载 Relay 部署文件
                            </VortButton>
                        </div>
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

                    <!-- 操作按钮 -->
                    <div class="flex items-center gap-3 mt-6">
                        <VortButton variant="primary" :loading="saving" @click="handleSave">
                            保存配置
                        </VortButton>
                        <VortButton :loading="testing" @click="handleTest">
                            <Zap :size="14" class="mr-1" /> 测试连接
                        </VortButton>
                    </div>
                </template>
            </VortSpin>
        </VortDrawer>
    </div>
</template>
