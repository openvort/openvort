<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getAgentRoutes, createAgentRoute, deleteAgentRoute } from "@/api";
import { message } from "@/components/vort/message";
import { Plus } from "lucide-vue-next";

interface AgentRoute {
    name: string;
    model: string;
    channels: string[];
    users: string[];
    system_prompt?: string;
    max_tokens?: number;
    group_ids?: string[];
}

const loading = ref(false);
const list = ref<AgentRoute[]>([]);
const dialogOpen = ref(false);
const saving = ref(false);

const form = ref({
    name: "",
    model: "",
    system_prompt: "",
    max_tokens: 0,
    channels: "",
    user_ids: "",
    group_ids: "",
});

async function loadData() {
    loading.value = true;
    try {
        const res: any = await getAgentRoutes();
        list.value = Array.isArray(res) ? res : [];
    } catch { /* ignore */ }
    finally { loading.value = false; }
}

function handleAdd() {
    form.value = { name: "", model: "", system_prompt: "", max_tokens: 0, channels: "", user_ids: "", group_ids: "" };
    dialogOpen.value = true;
}

function splitTrim(s: string): string[] {
    return s.split(",").map(v => v.trim()).filter(Boolean);
}

async function handleSave() {
    if (!form.value.name.trim()) {
        message.error("名称不能为空");
        return;
    }
    saving.value = true;
    try {
        await createAgentRoute({
            name: form.value.name,
            model: form.value.model || undefined,
            system_prompt: form.value.system_prompt || undefined,
            max_tokens: form.value.max_tokens || undefined,
            channels: splitTrim(form.value.channels),
            user_ids: splitTrim(form.value.user_ids),
            group_ids: splitTrim(form.value.group_ids),
        });
        message.success("创建成功");
        dialogOpen.value = false;
        await loadData();
    } catch {
        message.error("创建失败");
    } finally { saving.value = false; }
}

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">Agent 路由</h3>
                <VortButton variant="primary" @click="handleAdd">
                    <Plus :size="14" class="mr-1" /> 新增路由
                </VortButton>
            </div>
            <p class="text-sm text-gray-500 mb-4">
                按通道、用户、群组将消息路由到不同的 Agent 实例，每个 Agent 可有独立的模型和 System Prompt。
            </p>

            <VortTable :data-source="list" :loading="loading" row-key="name" :pagination="false">
                <VortTableColumn label="名称" prop="name" :width="160">
                    <template #default="{ row }">
                        <span class="font-medium">{{ row.name }}</span>
                        <VortTag v-if="row.name === 'default'" color="blue" class="ml-2">默认</VortTag>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="模型" prop="model" :width="220" />
                <VortTableColumn label="匹配通道" :width="160">
                    <template #default="{ row }">
                        <template v-if="row.channels?.length">
                            <VortTag v-for="ch in row.channels" :key="ch" color="cyan" class="mr-1">{{ ch }}</VortTag>
                        </template>
                        <span v-else class="text-gray-400 text-xs">全部</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="匹配用户" :width="160">
                    <template #default="{ row }">
                        <template v-if="row.users?.length">
                            <VortTag v-for="u in row.users" :key="u" color="purple" class="mr-1">{{ u }}</VortTag>
                        </template>
                        <span v-else class="text-gray-400 text-xs">全部</span>
                    </template>
                </VortTableColumn>
                <VortTableColumn label="操作" :width="100" fixed="right">
                    <template #default="{ row }">
                        <TableActions v-if="row.name !== 'default'">
                            <DeleteRecord
                                :request-api="() => deleteAgentRoute(row.name)"
                                :params="{}"
                                @after-delete="loadData"
                            >
                                <TableActionsItem danger>删除</TableActionsItem>
                            </DeleteRecord>
                        </TableActions>
                        <span v-else class="text-gray-400 text-xs">—</span>
                    </template>
                </VortTableColumn>
            </VortTable>
        </div>

        <!-- 新增弹窗 -->
        <VortDialog :open="dialogOpen" title="新增 Agent 路由" @update:open="dialogOpen = $event">
            <VortForm label-width="120px" class="mt-2">
                <VortFormItem label="名称" required>
                    <VortInput v-model="form.name" placeholder="如 vip-agent" />
                </VortFormItem>
                <VortFormItem label="模型">
                    <VortInput v-model="form.model" placeholder="留空使用全局模型" />
                </VortFormItem>
                <VortFormItem label="Max Tokens">
                    <VortInputNumber v-model="form.max_tokens" :min="0" :max="200000" class="w-full" />
                    <span class="text-xs text-gray-400 mt-1">0 表示使用全局配置</span>
                </VortFormItem>
                <VortFormItem label="匹配通道">
                    <VortInput v-model="form.channels" placeholder="逗号分隔，如 wecom,dingtalk（留空匹配全部）" />
                </VortFormItem>
                <VortFormItem label="匹配用户">
                    <VortInput v-model="form.user_ids" placeholder="逗号分隔用户 ID（留空匹配全部）" />
                </VortFormItem>
                <VortFormItem label="匹配群组">
                    <VortInput v-model="form.group_ids" placeholder="逗号分隔群组 ID（留空匹配全部）" />
                </VortFormItem>
                <VortFormItem label="System Prompt">
                    <VortTextarea v-model="form.system_prompt" placeholder="留空使用全局 Prompt" :auto-size="{ minRows: 3, maxRows: 8 }" />
                </VortFormItem>
            </VortForm>
            <template #footer>
                <VortButton @click="dialogOpen = false">取消</VortButton>
                <VortButton variant="primary" :loading="saving" @click="handleSave" class="ml-3">确定</VortButton>
            </template>
        </VortDialog>
    </div>
</template>
