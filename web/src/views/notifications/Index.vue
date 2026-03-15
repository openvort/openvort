<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { Bell, CheckCircle, Clock, AlertTriangle, Filter, CheckCheck, Settings } from "lucide-vue-next";
import { getNotifications, batchReadNotifications } from "@/api";
import { message } from "@/components/vort";

const router = useRouter();

interface NotificationItem {
    id: number;
    source: string;
    source_id: string;
    session_id: string;
    title: string;
    summary: string;
    status: string;
    im_channel: string;
    created_at: string;
    read_at: string;
}

const notifications = ref<NotificationItem[]>([]);
const loading = ref(false);
const page = ref(1);
const total = ref(0);
const statusFilter = ref("all");
const sourceFilter = ref("");
const limit = 20;

const statusOptions = [
    { label: "全部", value: "all" },
    { label: "未读", value: "pending" },
    { label: "已发送", value: "sent" },
    { label: "已读", value: "read" },
];

const sourceOptions = [
    { label: "全部", value: "" },
    { label: "计划任务", value: "schedule" },
    { label: "AI 消息", value: "ai_message" },
    { label: "系统", value: "system" },
];

async function loadNotifications() {
    loading.value = true;
    try {
        const res: any = await getNotifications({
            status: statusFilter.value,
            source: sourceFilter.value,
            page: page.value,
            limit,
        });
        notifications.value = res?.notifications || [];
        total.value = res?.total || 0;
    } catch {
        notifications.value = [];
    } finally {
        loading.value = false;
    }
}

async function handleBatchRead() {
    try {
        await batchReadNotifications([], true);
        message.success("已全部标为已读");
        await loadNotifications();
    } catch {
        message.error("操作失败");
    }
}

function goToChat(sessionId: string) {
    if (sessionId) {
        router.push({ path: "/chat", query: { session: sessionId } });
    }
}

function goToSettings() {
    router.push({ path: "/profile", query: { tab: "notification" } });
}

function formatTime(iso: string): string {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return "刚刚";
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    return d.toLocaleDateString();
}

function getStatusColor(status: string): string {
    switch (status) {
        case "pending": return "text-orange-500";
        case "sent": return "text-blue-500";
        case "read": return "text-gray-400";
        case "cancelled": return "text-gray-300";
        default: return "text-gray-400";
    }
}

function getStatusLabel(status: string): string {
    switch (status) {
        case "pending": return "待处理";
        case "sent": return "已发送";
        case "read": return "已读";
        case "cancelled": return "已取消";
        default: return status;
    }
}

onMounted(() => {
    loadNotifications();
});
</script>

<template>
    <div class="max-w-4xl mx-auto">
        <div class="flex items-center justify-between mb-6">
            <div class="flex items-center gap-2">
                <Bell :size="20" class="text-gray-600" />
                <h2 class="text-lg font-semibold text-gray-800">通知中心</h2>
            </div>
            <div class="flex items-center gap-2">
                <button
                    class="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                    @click="handleBatchRead"
                >
                    <CheckCheck :size="14" />
                    全部已读
                </button>
                <button
                    class="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                    @click="goToSettings"
                >
                    <Settings :size="14" />
                    通知设置
                </button>
            </div>
        </div>

        <!-- Filters -->
        <div class="flex items-center gap-3 mb-4">
            <div class="flex items-center gap-1 text-xs">
                <Filter :size="12" class="text-gray-400" />
                <span class="text-gray-400">状态:</span>
                <button
                    v-for="opt in statusOptions" :key="opt.value"
                    class="px-2 py-0.5 rounded text-xs transition-colors"
                    :class="statusFilter === opt.value ? 'bg-blue-100 text-blue-600' : 'text-gray-500 hover:bg-gray-100'"
                    @click="statusFilter = opt.value; page = 1; loadNotifications()"
                >{{ opt.label }}</button>
            </div>
            <div class="flex items-center gap-1 text-xs">
                <span class="text-gray-400">来源:</span>
                <button
                    v-for="opt in sourceOptions" :key="opt.value"
                    class="px-2 py-0.5 rounded text-xs transition-colors"
                    :class="sourceFilter === opt.value ? 'bg-blue-100 text-blue-600' : 'text-gray-500 hover:bg-gray-100'"
                    @click="sourceFilter = opt.value; page = 1; loadNotifications()"
                >{{ opt.label }}</button>
            </div>
        </div>

        <!-- Notification list -->
        <div v-if="loading" class="py-12 text-center text-gray-400 text-sm">加载中...</div>
        <div v-else-if="notifications.length === 0" class="py-12 text-center text-gray-400 text-sm">
            暂无通知
        </div>
        <div v-else class="space-y-1">
            <div
                v-for="n in notifications" :key="n.id"
                class="flex items-start gap-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                :class="n.status === 'pending' || n.status === 'sent' ? 'bg-blue-50/30' : ''"
                @click="goToChat(n.session_id)"
            >
                <div class="flex-shrink-0 mt-0.5">
                    <AlertTriangle v-if="n.source === 'schedule'" :size="16" class="text-amber-500" />
                    <Bell v-else :size="16" class="text-gray-400" />
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                        <span class="text-sm font-medium text-gray-800 truncate">{{ n.title }}</span>
                        <span class="text-[10px] px-1.5 py-0.5 rounded-full" :class="getStatusColor(n.status)">
                            {{ getStatusLabel(n.status) }}
                        </span>
                    </div>
                    <p v-if="n.summary" class="text-xs text-gray-500 mt-0.5 line-clamp-2">{{ n.summary }}</p>
                </div>
                <span class="text-[11px] text-gray-400 flex-shrink-0 whitespace-nowrap">{{ formatTime(n.created_at) }}</span>
            </div>
        </div>

        <!-- Pagination -->
        <div v-if="total > limit" class="flex justify-center gap-2 mt-6">
            <button
                class="px-3 py-1 text-xs rounded border"
                :disabled="page <= 1"
                @click="page--; loadNotifications()"
            >上一页</button>
            <span class="text-xs text-gray-400 leading-7">{{ page }} / {{ Math.ceil(total / limit) }}</span>
            <button
                class="px-3 py-1 text-xs rounded border"
                :disabled="page >= Math.ceil(total / limit)"
                @click="page++; loadNotifications()"
            >下一页</button>
        </div>
    </div>
</template>
