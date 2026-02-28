<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getWebhooks, createWebhook, updateWebhook, deleteWebhook } from "@/api";
import { message } from "@/components/vort/message";
import { Plus, Webhook } from "lucide-vue-next";

interface WebhookItem {
    name: string;
    secret: string;
    action_type: string;
    prompt_template: string;
    channel: string;
    user_id: string;
}

const loading = ref(false);
const list = ref<WebhookItem[]>([]);
const dialogOpen = ref(false);
const editing = ref(false);
const editingName = ref("");
const saving = ref(false);

const form = ref<WebhookItem>({
    name: "", secret: "", action_type: "agent_chat",
    prompt_template: "", channel: "webhook", user_id: "webhook",
});

async function loadData() {
    loading.value = true;
    try {
        const res: any = await getWebhooks();
        list.value = Array.isArray(res) ? res : [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

function handleAdd() {
    editing.value = false;
    editingName.value = "";
    form.value = { name: "", secret: "", action_type: "agent_chat", prompt_template: "", channel: "webhook", user_id: "webhook" };
    dialogOpen.value = true;
}

function handleEdit(row: WebhookItem) {
    editing.value = true;
    editingName.value = row.name;
    form.value = { ...row };
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

async function handleDelete(name: string) {
    try {
        await deleteWebhook(name);
        message.success("删除成功");
        await loadData();
    } catch {
        message.error("删除失败");
    }
}

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">Webhook 管理</h3>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增 Webhook
                </VortButton>
            </div>
            <p class="text-sm text-gray-500 mb-4">
                接收外部 HTTP 请求（CI/CD、GitHub 等），触发 Agent 动作。
                调用地址：<code class="text-xs bg-gray-100 px-1.5 py-0.5 rounded">POST /api/webhooks/&lt;name&gt;</code>
            </p>

            <VortTable :data-source="list" :loading="loading" row-key="name" :pagination="false">
                <VortTableColumn label="名称" prop="name" :width="160" />
                <VortTableColumn label="动作类型" prop="action_type" :width="120">
                    <template #default="{ row }">
                        <VortTag :color="row.action_type === 'agent_chat' ? 'blue' : 'green'">
                            {{ row.action_type === 'agent_chat' ? 'Agent 对话' : '通知' }}
                        </VortTag>
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
                        <TableActions>
                            <TableActionsItem @click="handleEdit(row)">编辑</TableActionsItem>
                            <DeleteRecord
                                :request-api="() => deleteWebhook(row.name)"
                                :params="{}"
                                @after-delete="loadData"
                            >
                                <TableActionsItem danger>删除</TableActionsItem>
                            </DeleteRecord>
                        </TableActions>
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
                    </VortSelect>
                </VortFormItem>
                <VortFormItem label="签名密钥">
                    <VortInputPassword v-model="form.secret" placeholder="留空则不验证签名" />
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
    </div>
</template>
