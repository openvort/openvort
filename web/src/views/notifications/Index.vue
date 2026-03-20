<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { Bell, Clock, Bot, CheckCheck, Settings, BellOff } from "lucide-vue-next";
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
const pageSize = ref(20);
const total = ref(0);
const statusFilter = ref("all");
const sourceFilter = ref("");

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
    { label: "VortFlow", value: "vortflow" },
];

const statusTagColor: Record<string, string> = {
    pending: "orange",
    sent: "blue",
    read: "default",
    cancelled: "default",
};

const statusLabelMap: Record<string, string> = {
    pending: "待处理",
    sent: "已发送",
    read: "已读",
    cancelled: "已取消",
};

async function loadNotifications() {
    loading.value = true;
    try {
        const res: any = await getNotifications({
            status: statusFilter.value,
            source: sourceFilter.value,
            page: page.value,
            limit: pageSize.value,
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

function isUnread(status: string) {
    return status === "pending" || status === "sent";
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
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    const h = String(d.getHours()).padStart(2, "0");
    const min = String(d.getMinutes()).padStart(2, "0");
    if (y === now.getFullYear()) return `${m}-${day} ${h}:${min}`;
    return `${y}-${m}-${day} ${h}:${min}`;
}

function handlePageChange() {
    loadNotifications();
}

function applyFilter(type: "status" | "source", value: string) {
    if (type === "status") statusFilter.value = value;
    else sourceFilter.value = value;
    page.value = 1;
    loadNotifications();
}

onMounted(() => {
    loadNotifications();
});
</script>

<template>
    <div class="space-y-4 max-w-4xl mx-auto">
        <!-- Header card -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-5">
                <h3 class="text-base font-medium text-gray-800">通知中心</h3>
                <div class="flex items-center gap-2">
                    <vort-button size="small" @click="handleBatchRead">
                        <CheckCheck :size="14" class="mr-1" />全部已读
                    </vort-button>
                    <vort-button size="small" @click="goToSettings">
                        <Settings :size="14" class="mr-1" />通知设置
                    </vort-button>
                </div>
            </div>
            <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
                <div class="flex items-center gap-1.5 text-sm">
                    <span class="text-gray-400 text-xs">状态</span>
                    <div class="flex items-center gap-0.5 ml-1">
                        <button
                            v-for="opt in statusOptions" :key="opt.value"
                            class="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
                            :class="statusFilter === opt.value ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'"
                            @click="applyFilter('status', opt.value)"
                        >{{ opt.label }}</button>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 text-sm">
                    <span class="text-gray-400 text-xs">来源</span>
                    <div class="flex items-center gap-0.5 ml-1">
                        <button
                            v-for="opt in sourceOptions" :key="opt.value"
                            class="px-2.5 py-1 rounded-md text-xs font-medium transition-colors"
                            :class="sourceFilter === opt.value ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'"
                            @click="applyFilter('source', opt.value)"
                        >{{ opt.label }}</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- List card -->
        <div class="bg-white rounded-xl p-6">
            <vort-spin :spinning="loading">
                <div v-if="!loading && notifications.length === 0" class="py-16 text-center">
                    <BellOff :size="36" class="mx-auto text-gray-300 mb-3" />
                    <p class="text-sm text-gray-400">暂无通知</p>
                </div>
                <div v-else class="divide-y divide-gray-50">
                    <div
                        v-for="n in notifications" :key="n.id"
                        class="flex items-start gap-3 py-3.5 px-3 -mx-3 rounded-lg cursor-pointer transition-colors"
                        :class="isUnread(n.status) ? 'hover:bg-blue-50/60' : 'hover:bg-gray-50'"
                        @click="goToChat(n.session_id)"
                    >
                        <div class="flex-shrink-0 mt-1 w-8 h-8 rounded-full flex items-center justify-center"
                            :class="isUnread(n.status) ? 'bg-blue-50' : 'bg-gray-50'"
                        >
                            <Clock v-if="n.source === 'schedule'" :size="16" class="text-blue-500" />
                            <Bot v-else-if="n.source === 'ai_message'" :size="16" class="text-blue-500" />
                            <Bell v-else :size="16" class="text-gray-400" />
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex items-center gap-2">
                                <span
                                    v-if="isUnread(n.status)"
                                    class="flex-shrink-0 w-1.5 h-1.5 rounded-full bg-blue-500"
                                />
                                <span class="text-sm text-gray-800 truncate" :class="isUnread(n.status) ? 'font-semibold' : 'font-normal'">{{ n.title }}</span>
                                <vort-tag size="small" :color="statusTagColor[n.status] || 'default'">{{ statusLabelMap[n.status] || n.status }}</vort-tag>
                            </div>
                            <p v-if="n.summary" class="text-xs text-gray-400 mt-1 line-clamp-2 leading-relaxed">{{ n.summary }}</p>
                        </div>
                        <span class="text-[11px] text-gray-300 flex-shrink-0 whitespace-nowrap mt-1.5">{{ formatTime(n.created_at) }}</span>
                    </div>
                </div>
            </vort-spin>

            <div v-if="total > pageSize" class="flex justify-end mt-4 pt-4 border-t border-gray-50">
                <vort-pagination
                    v-model:current="page"
                    v-model:page-size="pageSize"
                    :total="total"
                    show-total-info
                    @change="handlePageChange"
                />
            </div>
        </div>
    </div>
</template>
