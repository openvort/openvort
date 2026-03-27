<script setup lang="ts">
import { ref, onMounted } from "vue";
import {
    getOpenClawNodes,
    createOpenClawNode,
    updateOpenClawNode,
    deleteOpenClawNode,
    testOpenClawNode,
    getOpenClawNodeMembers,
} from "@/api";
import { message } from "@openvort/vort-ui";
import { Plus, CheckCircle, XCircle, HelpCircle, Wifi } from "lucide-vue-next";

interface OpenClawNode {
    id: string;
    name: string;
    description: string;
    gateway_url: string;
    gateway_token: string;
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

const loading = ref(false);
const nodes = ref<OpenClawNode[]>([]);

const dialogOpen = ref(false);
const editing = ref(false);
const editingId = ref("");
const saving = ref(false);

const form = ref({
    name: "",
    gateway_url: "",
    gateway_token: "",
    description: "",
});

const testing = ref<Record<string, boolean>>({});
const testResults = ref<Record<string, { ok: boolean; message: string }>>({});

const membersDialogOpen = ref(false);
const membersNodeName = ref("");
const boundMembers = ref<BoundMember[]>([]);
const membersLoading = ref(false);

async function loadData() {
    loading.value = true;
    try {
        const res: any = await getOpenClawNodes();
        nodes.value = res.nodes || [];
    } catch {
        /* ignore */
    } finally {
        loading.value = false;
    }
}

function handleAdd() {
    form.value = { name: "", gateway_url: "", gateway_token: "", description: "" };
    editing.value = false;
    editingId.value = "";
    dialogOpen.value = true;
}

function handleEdit(row: OpenClawNode) {
    form.value = {
        name: row.name,
        gateway_url: row.gateway_url,
        gateway_token: "",
        description: row.description,
    };
    editing.value = true;
    editingId.value = row.id;
    dialogOpen.value = true;
}

async function handleSave() {
    if (!form.value.name.trim()) {
        message.error("节点名称不能为空");
        return;
    }
    if (!editing.value && (!form.value.gateway_url.trim() || !form.value.gateway_token.trim())) {
        message.error("Gateway 地址和 Gateway Token 不能为空");
        return;
    }
    saving.value = true;
    try {
        if (editing.value) {
            const data: any = {
                name: form.value.name,
                description: form.value.description,
            };
            if (form.value.gateway_url) data.gateway_url = form.value.gateway_url;
            if (form.value.gateway_token) data.gateway_token = form.value.gateway_token;
            await updateOpenClawNode(editingId.value, data);
            message.success("更新成功");
        } else {
            await createOpenClawNode({
                name: form.value.name,
                gateway_url: form.value.gateway_url,
                gateway_token: form.value.gateway_token,
                description: form.value.description,
            });
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
        const res: any = await testOpenClawNode(nodeId);
        testResults.value[nodeId] = { ok: res.ok, message: res.message };
        if (res.ok) {
            message.success(res.message);
            await loadData();
        } else {
            message.error(res.message);
        }
    } catch {
        testResults.value[nodeId] = { ok: false, message: "请求失败" };
        message.error("测试连接失败");
    } finally {
        testing.value[nodeId] = false;
    }
}

async function handleViewMembers(node: OpenClawNode) {
    membersNodeName.value = node.name;
    membersDialogOpen.value = true;
    membersLoading.value = true;
    try {
        const res: any = await getOpenClawNodeMembers(node.id);
        boundMembers.value = res.members || [];
    } catch {
        boundMembers.value = [];
    } finally {
        membersLoading.value = false;
    }
}

function statusIcon(status: string) {
    if (status === "online") return CheckCircle;
    if (status === "offline") return XCircle;
    return HelpCircle;
}

function statusColor(status: string) {
    if (status === "online") return "text-green-500";
    if (status === "offline") return "text-red-500";
    return "text-gray-400";
}

function statusLabel(status: string) {
    if (status === "online") return "在线";
    if (status === "offline") return "离线";
    return "未知";
}

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">OpenClaw 远程工作节点</h3>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 添加节点
                </VortButton>
            </div>
            <p class="text-sm text-gray-500 mb-4">
                管理远程电脑上的 OpenClaw 实例。AI 员工可绑定节点，通过 WebSocket Gateway 协议在远程机器上执行工作任务。
            </p>

            <VortTable :data-source="nodes" :loading="loading" row-key="id" :pagination="false">
                <VortTableColumn label="节点名称" prop="name" :width="160">
                    <template #default="{ row }">
                        <span class="font-medium">{{ row.name }}</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="Gateway 地址" prop="gateway_url" :width="260">
                    <template #default="{ row }">
                        <span class="text-gray-600 text-sm font-mono">{{ row.gateway_url }}</span>
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
                        <a
                            v-if="row.bound_member_count > 0"
                            class="text-blue-600 cursor-pointer hover:underline text-sm"
                            @click="handleViewMembers(row)"
                        >
                            {{ row.bound_member_count }} 人
                        </a>
                        <span v-else class="text-gray-400 text-sm">未绑定</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="描述" prop="description" :min-width="150">
                    <template #default="{ row }">
                        <span class="text-gray-500 text-sm">{{ row.description || "—" }}</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="220" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2">
                            <VortButton size="small" @click="handleTest(row.id)" :loading="testing[row.id]">
                                <Wifi :size="12" class="mr-1" /> 测试
                            </VortButton>
                            <VortButton size="small" @click="handleEdit(row)">编辑</VortButton>
                            <TableActions>
                                <DeleteRecord
                                    :request-api="() => deleteOpenClawNode(row.id)"
                                    :params="{}"
                                    @after-delete="loadData"
                                >
                                    <TableActionsItem danger>删除</TableActionsItem>
                                </DeleteRecord>
                            </TableActions>
                        </div>
                    </template>
                </VortTableColumn>
            </VortTable>
        </div>

        <!-- 新增/编辑弹窗 -->
        <VortDialog :open="dialogOpen" :title="editing ? '编辑节点' : '添加 OpenClaw 节点'" @update:open="dialogOpen = $event">
            <VortForm label-width="130px" class="mt-2">
                <VortFormItem label="节点名称" required>
                    <VortInput v-model="form.name" placeholder="如：开发机-A" />
                </VortFormItem>
                <VortFormItem label="Gateway 地址" :required="!editing">
                    <VortInput v-model="form.gateway_url" placeholder="http://192.168.1.100:18789" />
                    <span v-if="editing" class="text-xs text-gray-400 mt-1">留空则不修改</span>
                </VortFormItem>
                <VortFormItem label="Gateway Token" :required="!editing">
                    <VortInput v-model="form.gateway_token" type="password" placeholder="OpenClaw gateway.auth.token" />
                    <span v-if="editing" class="text-xs text-gray-400 mt-1">留空则不修改</span>
                </VortFormItem>
                <VortFormItem label="描述">
                    <VortTextarea v-model="form.description" placeholder="节点描述（可选）" :auto-size="{ minRows: 2, maxRows: 4 }" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="dialogOpen = false">取消</VortButton>
                <VortButton variant="primary" :loading="saving" @click="handleSave" class="ml-3">
                    {{ editing ? "保存" : "创建" }}
                </VortButton>
            </template>
        </VortDialog>

        <!-- 绑定员工列表弹窗 -->
        <VortDialog :open="membersDialogOpen" :title="`节点「${membersNodeName}」绑定的 AI 员工`" @update:open="membersDialogOpen = $event">
            <VortSpin :spinning="membersLoading">
                <div v-if="boundMembers.length === 0" class="text-center text-gray-400 py-6">
                    暂无绑定的 AI 员工
                </div>
                <div v-else class="space-y-2">
                    <div v-for="m in boundMembers" :key="m.id" class="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                        <div>
                            <span class="font-medium text-gray-800">{{ m.name }}</span>
                            <VortTag v-if="m.post" color="blue" class="ml-2">{{ m.post }}</VortTag>
                        </div>
                    </div>
                </div>
            </VortSpin>
        </VortDialog>
    </div>
</template>
