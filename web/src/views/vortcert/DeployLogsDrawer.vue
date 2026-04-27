<script setup lang="ts">
import { ref, watch } from "vue";
import { getCertDeployLogs } from "@/api";
import dayjs from "dayjs";

const props = defineProps<{
    open: boolean;
    domainName?: string;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
}>();

interface DeployLogItem {
    id: string;
    certificate_id: string;
    deploy_target_id: string;
    target_name: string;
    domain: string;
    status: string;
    error_message: string;
    deployed_at: string | null;
    created_at: string | null;
}

const loading = ref(false);
const logs = ref<DeployLogItem[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);

const statusTagColor = (status: string) => {
    const map: Record<string, string> = {
        success: "green",
        failed: "red",
        pending: "default",
    };
    return map[status] || "default";
};

const statusLabel = (status: string) => {
    const map: Record<string, string> = {
        success: "成功",
        failed: "失败",
        pending: "进行中",
    };
    return map[status] || status;
};

const loadLogs = async () => {
    if (!props.domainName) return;
    loading.value = true;
    try {
        const res = (await getCertDeployLogs({
            domain: props.domainName,
            page: page.value,
            page_size: pageSize.value,
        })) as any;
        logs.value = res.items || [];
        total.value = res.total || 0;
    } catch {
        logs.value = [];
    } finally {
        loading.value = false;
    }
};

watch(
    () => props.open,
    (val) => {
        if (val) {
            page.value = 1;
            loadLogs();
        }
    },
);

const onPageChange = () => {
    loadLogs();
};
</script>

<template>
    <vort-drawer
        :open="open"
        title="部署日志"
        :width="640"
        @update:open="emit('update:open', $event)"
    >
        <div class="mb-3 text-sm text-gray-500">
            域名：<span class="font-medium text-gray-800">{{ domainName }}</span>
        </div>

        <vort-spin :spinning="loading">
            <div v-if="logs.length === 0 && !loading" class="py-12 text-center text-gray-400 text-sm">
                暂无部署记录
            </div>

            <div v-else class="space-y-3">
                <div
                    v-for="log in logs"
                    :key="log.id"
                    class="border border-gray-100 rounded-lg p-4"
                >
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-medium text-gray-800">{{ log.target_name }}</span>
                            <vort-tag :color="statusTagColor(log.status)" size="small">
                                {{ statusLabel(log.status) }}
                            </vort-tag>
                        </div>
                        <span class="text-xs text-gray-400">
                            {{ log.created_at ? dayjs(log.created_at).format("YYYY-MM-DD HH:mm:ss") : "-" }}
                        </span>
                    </div>
                    <div class="text-xs text-gray-500">
                        <span>域名：{{ log.domain }}</span>
                        <template v-if="log.deployed_at">
                            <span class="ml-4">部署时间：{{ dayjs(log.deployed_at).format("YYYY-MM-DD HH:mm:ss") }}</span>
                        </template>
                    </div>
                    <div v-if="log.error_message" class="mt-2 text-xs text-red-500 bg-red-50 rounded p-2 break-all">
                        {{ log.error_message }}
                    </div>
                </div>
            </div>

            <div v-if="total > pageSize" class="flex justify-end mt-4">
                <vort-pagination
                    v-model:current="page"
                    v-model:page-size="pageSize"
                    :total="total"
                    show-total-info
                    @change="onPageChange"
                />
            </div>
        </vort-spin>
    </vort-drawer>
</template>
