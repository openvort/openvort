<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from "vue";
import {
    getRemoteNodes,
    createRemoteNode,
    updateRemoteNode,
    deleteRemoteNode,
    testRemoteNode,
    getRemoteNodeMembers,
    startDockerContainer,
    stopDockerContainer,
    restartDockerContainer,
    getContainerLogs,
    getAllDockerStats,
    checkImageStatus,
    getInstallImageUrl,
} from "@/api";
import { useUserStore } from "@/stores/modules/user";
import { message } from "@openvort/vort-ui";
import {
    Plus, CheckCircle, XCircle, HelpCircle, Play,
    RotateCw, Container, Cpu, MemoryStick,
    Trash2, Download, Loader2, AlertTriangle,
} from "lucide-vue-next";
import DockerTerminal from "@/components/DockerTerminal.vue";
import BrowserPreview from "@/components/BrowserPreview.vue";

interface RemoteNodeItem {
    id: string;
    name: string;
    node_type: string;
    description: string;
    gateway_url: string;
    gateway_token: string;
    config: Record<string, any>;
    status: string;
    machine_info: Record<string, any>;
    last_heartbeat_at: string | null;
    bound_member_count: number;
    created_at: string;
    updated_at: string;
}

interface BoundMember {
    id: string;
    name: string;
    post: string;
}

const NODE_TYPE_OPTIONS = [
    { value: "docker", label: "Docker 容器" },
];

const IMAGE_PRESETS = [
    { value: "openvort/worker-sandbox:latest", label: "工作沙箱 (Python + Node + Claude Code + Aider)" },
    { value: "openvort/coding-sandbox:latest", label: "编码沙箱 (Python + Node + Claude Code + Aider)" },
    { value: "openvort/browser-sandbox:latest", label: "浏览器沙箱 (Chromium + noVNC 可视化)" },
    { value: "python:3.11-slim", label: "Python 3.11 (轻量)" },
    { value: "node:22-slim", label: "Node.js 22 (轻量)" },
    { value: "ubuntu:24.04", label: "Ubuntu 24.04 (通用)" },
];

const loading = ref(false);
const nodes = ref<RemoteNodeItem[]>([]);

const dialogOpen = ref(false);
const editing = ref(false);
const editingId = ref("");
const saving = ref(false);
const gatewayTokenEditing = ref(false);
const maskedGatewayToken = ref("");

const form = ref({
    name: "",
    node_type: "openclaw",
    gateway_url: "",
    gateway_token: "",
    image: "python:3.11-slim",
    customImage: "",
    memory_limit: "2g",
    cpu_limit: 2,
    network_mode: "host",
    env_vars: [] as { key: string; value: string }[],
    description: "",
});
const useCustomImage = ref(false);
const userStore = useUserStore();

const imageStatusMap = ref<Record<string, { available: boolean; buildable?: boolean }>>({});
const imageStatusLoading = ref(false);
const installingImage = ref(false);
const installOutput = ref<string[]>([]);
const installSuccess = ref<boolean | null>(null);

const selectedImageStatus = computed(() => {
    if (useCustomImage.value) return null;
    return imageStatusMap.value[form.value.image] || null;
});

async function loadImageStatus() {
    const images = IMAGE_PRESETS.map(p => p.value);
    imageStatusLoading.value = true;
    try {
        const res: any = await checkImageStatus(images);
        imageStatusMap.value = res.images || {};
    } catch { /* ignore */ }
    finally { imageStatusLoading.value = false; }
}

async function handleInstallImage() {
    const image = form.value.image;
    if (!image || installingImage.value) return;
    installingImage.value = true;
    installOutput.value = [];
    installSuccess.value = null;

    const url = getInstallImageUrl(userStore.token);
    try {
        const resp = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${userStore.token}`,
            },
            body: JSON.stringify({ image }),
        });
        if (!resp.ok || !resp.body) {
            message.error("安装请求失败");
            installingImage.value = false;
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
                        installOutput.value.push(evt.text);
                        if (installOutput.value.length > 200) {
                            installOutput.value = installOutput.value.slice(-100);
                        }
                    } else if (evt.type === "done") {
                        installSuccess.value = evt.success;
                        if (evt.success) {
                            message.success("镜像安装成功");
                            imageStatusMap.value[image] = { available: true };
                        } else {
                            message.error("镜像安装失败");
                        }
                    } else if (evt.type === "error") {
                        installSuccess.value = false;
                        message.error(evt.text || "安装出错");
                    }
                } catch { /* ignore parse errors */ }
            }
        }
    } catch {
        message.error("安装请求异常");
        installSuccess.value = false;
    } finally {
        installingImage.value = false;
    }
}

const testing = ref<Record<string, boolean>>({});
const testResults = ref<Record<string, { ok: boolean; message: string }>>({});

const membersDialogOpen = ref(false);
const membersNodeName = ref("");
const boundMembers = ref<BoundMember[]>([]);
const membersLoading = ref(false);

const logsDialogOpen = ref(false);
const logsNodeName = ref("");
const logsContent = ref("");
const logsLoading = ref(false);

const terminalOpen = ref(false);
const terminalNodeId = ref("");
const terminalNodeName = ref("");

const browserPreviewOpen = ref(false);
const browserNodeId = ref("");
const browserNodeName = ref("");

const dockerStats = ref<Record<string, any>>({});
let statsTimer: ReturnType<typeof setInterval> | null = null;

const dockerNodeCount = computed(() => nodes.value.filter(n => n.node_type === "docker").length);
const runningCount = computed(() => nodes.value.filter(n => n.node_type === "docker" && n.status === "running").length);

async function loadData() {
    loading.value = true;
    try {
        const res: any = await getRemoteNodes();
        nodes.value = res.nodes || [];
    } catch { /* ignore */ } finally {
        loading.value = false;
    }
}

async function loadDockerStats() {
    try {
        const res: any = await getAllDockerStats();
        dockerStats.value = res.stats || {};
    } catch { /* ignore */ }
}

function handleAdd() {
    form.value = {
        name: "", node_type: "openclaw",
        gateway_url: "", gateway_token: "",
        image: "python:3.11-slim", customImage: "",
        memory_limit: "2g", cpu_limit: 2, network_mode: "host",
        env_vars: [], description: "",
    };
    useCustomImage.value = false;
    editing.value = false;
    editingId.value = "";
    gatewayTokenEditing.value = true;
    maskedGatewayToken.value = "";
    installOutput.value = [];
    installSuccess.value = null;
    dialogOpen.value = true;
    loadImageStatus();
}

function handleClone(row: RemoteNodeItem) {
    const cfg = row.config || {};
    form.value = {
        name: `${row.name} (副本)`,
        node_type: row.node_type || "openclaw",
        gateway_url: row.node_type !== "docker" ? row.gateway_url : "",
        gateway_token: "",
        image: cfg.image || "python:3.11-slim",
        customImage: "",
        memory_limit: cfg.memory_limit || "2g",
        cpu_limit: cfg.cpu_limit || 2,
        network_mode: cfg.network_mode || "host",
        env_vars: Object.entries(cfg.env_vars || {}).map(([key, value]) => ({ key, value: String(value) })),
        description: row.description,
    };
    const isPreset = IMAGE_PRESETS.some(p => p.value === form.value.image);
    useCustomImage.value = !isPreset && !!cfg.image;
    if (useCustomImage.value) form.value.customImage = cfg.image;
    editing.value = false;
    editingId.value = "";
    gatewayTokenEditing.value = true;
    maskedGatewayToken.value = "";
    installOutput.value = [];
    installSuccess.value = null;
    dialogOpen.value = true;
    if (row.node_type === "docker") loadImageStatus();
}

function handleEdit(row: RemoteNodeItem) {
    const cfg = row.config || {};
    form.value = {
        name: row.name,
        node_type: row.node_type || "openclaw",
        gateway_url: row.gateway_url,
        gateway_token: "",
        image: cfg.image || "python:3.11-slim",
        customImage: "",
        memory_limit: cfg.memory_limit || "2g",
        cpu_limit: cfg.cpu_limit || 2,
        network_mode: cfg.network_mode || "host",
        env_vars: Object.entries(cfg.env_vars || {}).map(([key, value]) => ({ key, value: String(value) })),
        description: row.description,
    };
    useCustomImage.value = false;
    editing.value = true;
    editingId.value = row.id;
    gatewayTokenEditing.value = false;
    maskedGatewayToken.value = row.gateway_token || "";
    dialogOpen.value = true;
}

async function handleSave() {
    if (!form.value.name.trim()) { message.error("节点名称不能为空"); return; }

    if (form.value.node_type === "docker") {
        const finalImage = useCustomImage.value ? form.value.customImage.trim() : form.value.image;
        if (!editing.value && !finalImage) { message.error("请选择或输入 Docker 镜像"); return; }
    } else {
        if (!editing.value && (!form.value.gateway_url.trim() || !form.value.gateway_token.trim())) {
            message.error("Gateway 地址和 Token 不能为空"); return;
        }
    }

    saving.value = true;
    try {
        if (editing.value) {
            const data: any = { name: form.value.name, description: form.value.description };
            if (form.value.node_type !== "docker") {
                if (form.value.gateway_url) data.gateway_url = form.value.gateway_url;
                if (form.value.gateway_token) data.gateway_token = form.value.gateway_token;
            }
            await updateRemoteNode(editingId.value, data);
            message.success("更新成功");
        } else {
            const envObj: Record<string, string> = {};
            for (const item of form.value.env_vars) {
                if (item.key.trim()) envObj[item.key.trim()] = item.value;
            }
            const finalImage = useCustomImage.value ? form.value.customImage.trim() : form.value.image;
            const res: any = await createRemoteNode({
                name: form.value.name,
                node_type: form.value.node_type,
                gateway_url: form.value.gateway_url,
                gateway_token: form.value.gateway_token,
                image: finalImage,
                memory_limit: form.value.memory_limit,
                cpu_limit: form.value.cpu_limit,
                network_mode: form.value.network_mode,
                env_vars: envObj,
                description: form.value.description,
            });
            if (res.success === false) {
                message.error(res.error || "创建失败");
                return;
            }
            message.success("创建成功");
        }
        dialogOpen.value = false;
        await loadData();
    } catch {
        message.error(editing.value ? "更新失败" : "创建失败");
    } finally {
        saving.value = false;
    }
}

async function handleTest(nodeId: string) {
    testing.value[nodeId] = true;
    testResults.value[nodeId] = { ok: false, message: "" };
    try {
        const res: any = await testRemoteNode(nodeId);
        testResults.value[nodeId] = { ok: res.ok, message: res.message };
        if (res.ok) { message.success(res.message); await loadData(); }
        else message.error(res.message);
    } catch {
        testResults.value[nodeId] = { ok: false, message: "请求失败" };
        message.error("测试失败");
    } finally {
        testing.value[nodeId] = false;
    }
}

const dockerActionLoading = ref<Record<string, boolean>>({});

async function handleDockerAction(nodeId: string, action: "start" | "stop" | "restart") {
    if (dockerActionLoading.value[nodeId]) return;
    dockerActionLoading.value[nodeId] = true;
    const fn = action === "start" ? startDockerContainer : action === "stop" ? stopDockerContainer : restartDockerContainer;
    const label = action === "start" ? "启动" : action === "stop" ? "停止" : "重启";
    try {
        const res: any = await fn(nodeId);
        if (res.ok) { message.success(`${label}成功`); await loadData(); }
        else message.error(res.message || `${label}失败`);
    } catch { message.error(`${label}失败`); }
    finally { dockerActionLoading.value[nodeId] = false; }
}

async function handleViewMembers(node: RemoteNodeItem) {
    membersNodeName.value = node.name;
    membersDialogOpen.value = true;
    membersLoading.value = true;
    try {
        const res: any = await getRemoteNodeMembers(node.id);
        boundMembers.value = res.members || [];
    } catch { boundMembers.value = []; } finally { membersLoading.value = false; }
}

async function handleViewLogs(node: RemoteNodeItem) {
    logsNodeName.value = node.name;
    logsDialogOpen.value = true;
    logsLoading.value = true;
    try {
        const res: any = await getContainerLogs(node.id, 200);
        logsContent.value = res.logs || "(无日志)";
    } catch { logsContent.value = "获取日志失败"; } finally { logsLoading.value = false; }
}

function handleOpenTerminal(node: RemoteNodeItem) {
    terminalNodeId.value = node.id;
    terminalNodeName.value = node.name;
    terminalOpen.value = true;
}

function handleOpenBrowser(node: RemoteNodeItem) {
    browserNodeId.value = node.id;
    browserNodeName.value = node.name;
    browserPreviewOpen.value = true;
}

function addEnvVar() {
    form.value.env_vars.push({ key: "", value: "" });
}
function removeEnvVar(idx: number) {
    form.value.env_vars.splice(idx, 1);
}

function nodeTypeLabel(t: string) {
    const opt = NODE_TYPE_OPTIONS.find(o => o.value === t);
    return opt ? opt.label : t;
}

function statusIcon(s: string) {
    if (s === "online" || s === "running") return CheckCircle;
    if (s === "offline" || s === "stopped" || s === "error") return XCircle;
    if (s === "creating") return RotateCw;
    return HelpCircle;
}
function statusColor(s: string) {
    if (s === "online" || s === "running") return "text-green-500";
    if (s === "offline" || s === "stopped" || s === "error") return "text-red-500";
    if (s === "creating") return "text-blue-500";
    return "text-gray-400";
}
function statusLabel(s: string) {
    const m: Record<string, string> = { online: "在线", offline: "离线", running: "运行中", stopped: "已停止", creating: "创建中", error: "错误", unknown: "未知" };
    return m[s] || s;
}

function infoCol(row: RemoteNodeItem) {
    if (row.node_type === "docker") return (row.config || {}).image || "—";
    return row.gateway_url || "—";
}
function infoLabel(row: RemoteNodeItem) {
    return row.node_type === "docker" ? "镜像" : "Gateway";
}

onMounted(async () => {
    await loadData();
    await loadDockerStats();
    statsTimer = setInterval(loadDockerStats, 15000);
});
onBeforeUnmount(() => { if (statsTimer) clearInterval(statsTimer); });
</script>

<template>
    <div class="space-y-4">
        <!-- Resource overview cards -->
        <div v-if="dockerNodeCount > 0" class="grid grid-cols-3 gap-4">
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center">
                    <Container :size="20" class="text-blue-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ dockerNodeCount }}</div>
                    <div class="text-xs text-gray-500">Docker 容器</div>
                </div>
            </div>
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center">
                    <Play :size="20" class="text-green-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ runningCount }}</div>
                    <div class="text-xs text-gray-500">运行中</div>
                </div>
            </div>
            <div class="bg-white rounded-xl p-4 flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg bg-purple-50 flex items-center justify-center">
                    <Cpu :size="20" class="text-purple-500" />
                </div>
                <div>
                    <div class="text-2xl font-semibold text-gray-800">{{ nodes.filter(n => n.node_type !== 'docker').length }}</div>
                    <div class="text-xs text-gray-500">远程节点</div>
                </div>
            </div>
        </div>

        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">工作节点</h3>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 添加节点
                </VortButton>
            </div>
            <p class="text-sm text-gray-500 mb-4">
                管理 AI 员工的工作执行环境。支持 Docker 容器（本地）和 OpenClaw 远程节点。
            </p>

            <VortTable :data-source="nodes" :loading="loading" row-key="id" :pagination="false">
                <VortTableColumn label="节点名称" prop="name" :width="160">
                    <template #default="{ row }">
                        <span class="font-medium">{{ row.name }}</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="类型" :width="140">
                    <template #default="{ row }">
                        <VortTag :color="row.node_type === 'docker' ? 'purple' : 'blue'">{{ nodeTypeLabel(row.node_type) }}</VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="信息" :min-width="220">
                    <template #default="{ row }">
                        <div class="text-sm">
                            <span class="text-gray-400 mr-1">{{ infoLabel(row) }}:</span>
                            <span class="text-gray-600 font-mono">{{ infoCol(row) }}</span>
                        </div>
                        <!-- Docker resource stats inline -->
                        <div v-if="row.node_type === 'docker' && dockerStats[row.id]" class="flex items-center gap-3 mt-1 text-xs text-gray-400">
                            <span class="inline-flex items-center gap-0.5"><Cpu :size="11" /> {{ dockerStats[row.id].cpu }}</span>
                            <span class="inline-flex items-center gap-0.5"><MemoryStick :size="11" /> {{ dockerStats[row.id].mem }}</span>
                        </div>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="状态" :width="100">
                    <template #default="{ row }">
                        <span class="inline-flex items-center gap-1" :class="statusColor(row.status)">
                            <component :is="statusIcon(row.status)" :size="14" />
                            <span class="text-sm">{{ statusLabel(row.status) }}</span>
                        </span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="绑定员工" :width="100">
                    <template #default="{ row }">
                        <a v-if="row.bound_member_count > 0" class="text-blue-600 cursor-pointer hover:underline text-sm" @click="handleViewMembers(row)">{{ row.bound_member_count }} 人</a>
                        <span v-else class="text-gray-400 text-sm">未绑定</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="200" fixed="right">
                    <template #default="{ row }">
                        <TableActions>
                            <template v-if="row.node_type === 'docker'">
                                <TableActionsItem v-if="row.status !== 'running'" @click="handleDockerAction(row.id, 'start')">启动</TableActionsItem>
                                <TableActionsItem v-if="row.status === 'running'" @click="handleDockerAction(row.id, 'stop')">停止</TableActionsItem>
                                <TableActionsItem v-if="row.status === 'running'" @click="handleDockerAction(row.id, 'restart')">重启</TableActionsItem>
                            </template>
                            <template v-else>
                                <TableActionsItem @click="handleTest(row.id)">测试</TableActionsItem>
                            </template>
                            <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
                            <template #more>
                                <TableActionsMoreItem @click="handleClone(row)">复制</TableActionsMoreItem>
                                <template v-if="row.node_type === 'docker' && row.status === 'running'">
                                    <TableActionsMoreItem @click="handleOpenTerminal(row)">终端</TableActionsMoreItem>
                                    <TableActionsMoreItem v-if="(row.config || {}).image?.includes('browser')" @click="handleOpenBrowser(row)">浏览器</TableActionsMoreItem>
                                </template>
                                <TableActionsMoreItem v-if="row.node_type === 'docker'" @click="handleViewLogs(row)">日志</TableActionsMoreItem>
                                <DeleteRecord :request-api="() => deleteRemoteNode(row.id)" :params="{}" @after-delete="loadData">
                                    <TableActionsMoreItem danger>删除</TableActionsMoreItem>
                                </DeleteRecord>
                            </template>
                        </TableActions>
                    </template>
                </VortTableColumn>
            </VortTable>
        </div>

        <!-- Create/Edit dialog -->
        <VortDialog :open="dialogOpen" :title="editing ? '编辑节点' : '添加工作节点'" @update:open="dialogOpen = $event" :width="560">
            <VortForm label-width="130px" class="mt-2">
                <VortFormItem label="节点名称" required>
                    <VortInput v-model="form.name" placeholder="如：编码助手-A" />
                </VortFormItem>
                <VortFormItem v-if="!editing" label="节点类型">
                    <VortSelect v-model="form.node_type" :options="NODE_TYPE_OPTIONS" />
                </VortFormItem>

                <!-- OpenClaw fields -->
                <template v-if="form.node_type === 'openclaw'">
                    <VortFormItem label="Gateway 地址" :required="!editing">
                        <VortInput v-model="form.gateway_url" placeholder="http://192.168.1.100:18789" />
                        <span v-if="editing" class="text-xs text-gray-400 mt-1">留空则不修改</span>
                    </VortFormItem>
                    <VortFormItem label="Gateway Token" :required="!editing">
                        <template v-if="editing && !gatewayTokenEditing">
                            <div class="flex items-center gap-3 min-h-[32px]">
                                <span class="text-base text-gray-700">{{ maskedGatewayToken || "未配置" }}</span>
                                <a class="text-sm text-blue-600 cursor-pointer" @click="gatewayTokenEditing = true">编辑</a>
                            </div>
                        </template>
                        <template v-else>
                            <div class="flex items-center gap-3">
                                <VortInput v-model="form.gateway_token" type="password" :placeholder="editing ? '输入新 Token' : 'Gateway Token'" />
                                <a v-if="editing" class="text-sm text-gray-500 cursor-pointer whitespace-nowrap" @click="gatewayTokenEditing = false; form.gateway_token = ''">取消</a>
                            </div>
                        </template>
                    </VortFormItem>
                </template>

                <!-- Docker fields -->
                <template v-if="form.node_type === 'docker' && !editing">
                    <VortFormItem label="Docker 镜像" required>
                        <template v-if="!useCustomImage">
                            <VortSelect v-model="form.image" placeholder="选择镜像">
                                <VortSelectOption v-for="img in IMAGE_PRESETS" :key="img.value" :value="img.value">
                                    <span class="flex items-center justify-between w-full">
                                        <span>{{ img.label }}</span>
                                        <span v-if="imageStatusMap[img.value]?.available" class="text-green-500 text-xs ml-2">已安装</span>
                                        <span v-else-if="imageStatusMap[img.value] && !imageStatusMap[img.value].available" class="text-gray-400 text-xs ml-2">未安装</span>
                                    </span>
                                </VortSelectOption>
                            </VortSelect>
                            <a class="text-xs text-blue-600 cursor-pointer mt-1 inline-block" @click="useCustomImage = true">使用自定义镜像</a>
                        </template>
                        <template v-else>
                            <VortInput v-model="form.customImage" placeholder="输入完整镜像名，如 myrepo/myimage:tag" />
                            <a class="text-xs text-blue-600 cursor-pointer mt-1 inline-block" @click="useCustomImage = false; form.customImage = ''">选择预设镜像</a>
                        </template>

                        <!-- Image status hint -->
                        <div v-if="!useCustomImage && selectedImageStatus && !selectedImageStatus.available && !installingImage && installSuccess !== true" class="mt-2 flex items-center gap-2 text-xs">
                            <AlertTriangle :size="14" class="text-amber-500 flex-shrink-0" />
                            <span class="text-amber-600">该镜像本地未安装，需要先安装才能创建节点</span>
                            <button
                                class="ml-1 inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-blue-500 text-white hover:bg-blue-600 transition-colors"
                                @click="handleInstallImage"
                            >
                                <Download :size="12" /> 安装镜像
                            </button>
                        </div>
                        <div v-if="!useCustomImage && selectedImageStatus?.available && !installingImage" class="mt-1.5 flex items-center gap-1 text-xs text-green-600">
                            <CheckCircle :size="12" /> 镜像已就绪
                        </div>

                        <!-- Install progress -->
                        <div v-if="installingImage || (installOutput.length > 0 && installSuccess !== true)" class="mt-2 rounded-lg border border-gray-200 overflow-hidden">
                            <div class="flex items-center gap-1.5 px-3 py-1.5 bg-gray-50 text-xs text-gray-500">
                                <Loader2 v-if="installingImage" :size="12" class="animate-spin" />
                                <CheckCircle v-else-if="installSuccess" :size="12" class="text-green-500" />
                                <XCircle v-else :size="12" class="text-red-500" />
                                {{ installingImage ? '正在安装镜像...' : installSuccess ? '安装完成' : '安装失败' }}
                            </div>
                            <div class="max-h-48 overflow-y-auto bg-gray-900 text-gray-300 text-[11px] font-mono px-3 py-2 leading-5">
                                <div v-for="(line, i) in installOutput.slice(-50)" :key="i" class="whitespace-pre-wrap break-all">{{ line }}</div>
                            </div>
                        </div>
                        <div v-if="installSuccess === true && !installingImage" class="mt-1.5 flex items-center gap-1 text-xs text-green-600">
                            <CheckCircle :size="12" /> 安装完成，可以创建节点了
                        </div>
                    </VortFormItem>
                    <VortFormItem label="内存限制">
                        <VortSelect v-model="form.memory_limit">
                            <VortSelectOption value="512m">512 MB</VortSelectOption>
                            <VortSelectOption value="1g">1 GB</VortSelectOption>
                            <VortSelectOption value="2g">2 GB</VortSelectOption>
                            <VortSelectOption value="4g">4 GB</VortSelectOption>
                            <VortSelectOption value="8g">8 GB</VortSelectOption>
                        </VortSelect>
                    </VortFormItem>
                    <VortFormItem label="CPU 限制">
                        <VortSelect v-model="form.cpu_limit">
                            <VortSelectOption :value="0.5">0.5 核</VortSelectOption>
                            <VortSelectOption :value="1">1 核</VortSelectOption>
                            <VortSelectOption :value="2">2 核</VortSelectOption>
                            <VortSelectOption :value="4">4 核</VortSelectOption>
                        </VortSelect>
                    </VortFormItem>
                    <VortFormItem label="网络模式">
                        <VortSelect v-model="form.network_mode">
                            <VortSelectOption value="host">Host (共享主机网络)</VortSelectOption>
                            <VortSelectOption value="bridge">Bridge (隔离网络)</VortSelectOption>
                            <VortSelectOption value="none">None (无网络)</VortSelectOption>
                        </VortSelect>
                    </VortFormItem>
                    <VortFormItem label="环境变量">
                        <div class="space-y-2 w-full">
                            <div v-for="(item, idx) in form.env_vars" :key="idx" class="flex items-center gap-2">
                                <VortInput v-model="item.key" placeholder="KEY" class="flex-1" />
                                <span class="text-gray-400">=</span>
                                <VortInput v-model="item.value" placeholder="VALUE" class="flex-1" />
                                <button class="text-red-400 hover:text-red-600" @click="removeEnvVar(idx)"><Trash2 :size="14" /></button>
                            </div>
                            <a class="text-sm text-blue-600 cursor-pointer" @click="addEnvVar">+ 添加环境变量</a>
                        </div>
                    </VortFormItem>
                </template>

                <VortFormItem label="描述">
                    <VortTextarea v-model="form.description" placeholder="节点描述（可选）" :auto-size="{ minRows: 2, maxRows: 4 }" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="dialogOpen = false">取消</VortButton>
                <VortButton
                    variant="primary"
                    :loading="saving"
                    :disabled="!editing && form.node_type === 'docker' && !useCustomImage && selectedImageStatus !== null && !selectedImageStatus.available"
                    @click="handleSave"
                    class="ml-3"
                >
                    {{ editing ? "保存" : "创建" }}
                </VortButton>
            </template>
        </VortDialog>

        <!-- Bound members dialog -->
        <VortDialog :open="membersDialogOpen" :title="`节点「${membersNodeName}」绑定的 AI 员工`" @update:open="membersDialogOpen = $event">
            <VortSpin :spinning="membersLoading">
                <div v-if="boundMembers.length === 0" class="text-center text-gray-400 py-6">暂无绑定的 AI 员工</div>
                <div v-else class="space-y-2">
                    <div v-for="m in boundMembers" :key="m.id" class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                        <span class="font-medium text-gray-800">{{ m.name }}</span>
                        <VortTag v-if="m.post" color="blue">{{ m.post }}</VortTag>
                    </div>
                </div>
            </VortSpin>
        </VortDialog>

        <!-- Container logs dialog -->
        <VortDialog :open="logsDialogOpen" :title="`容器日志 — ${logsNodeName}`" @update:open="logsDialogOpen = $event" :width="720">
            <VortSpin :spinning="logsLoading">
                <pre class="bg-gray-900 text-green-400 text-xs font-mono px-4 py-3 rounded-lg overflow-auto max-h-[500px] whitespace-pre-wrap">{{ logsContent }}</pre>
            </VortSpin>
        </VortDialog>

        <!-- Terminal dialog (P4) -->
        <VortDialog :open="terminalOpen" :title="`终端 — ${terminalNodeName}`" @update:open="terminalOpen = $event" :width="900" :footer="false">
            <DockerTerminal v-if="terminalOpen" :node-id="terminalNodeId" />
        </VortDialog>

        <!-- Browser preview dialog (P5) -->
        <VortDialog :open="browserPreviewOpen" :title="`浏览器预览 — ${browserNodeName}`" @update:open="browserPreviewOpen = $event" :width="1000" :footer="false">
            <BrowserPreview v-if="browserPreviewOpen" :node-id="browserNodeId" />
        </VortDialog>
    </div>
</template>
