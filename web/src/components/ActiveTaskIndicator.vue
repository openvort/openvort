<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { Loader2, X } from "lucide-vue-next";
import { useActiveTasksStore } from "@/stores/modules/activeTasks";
import { cancelChatTask } from "@/api";
import { useWebSocket } from "@/composables/useWebSocket";

const router = useRouter();
const activeTasksStore = useActiveTasksStore();
const { on } = useWebSocket();

onMounted(() => {
    activeTasksStore.fetchActiveTasks();

    on("task_completed", (data: any) => {
        activeTasksStore.removeTask(data.task_id);
    });
    on("task_failed", (data: any) => {
        activeTasksStore.removeTask(data.task_id);
    });
});

function goToChat(sessionId: string) {
    router.push({ path: "/chat", query: { session: sessionId } });
}

async function handleCancel(taskId: string) {
    try {
        await cancelChatTask(taskId);
        activeTasksStore.removeTask(taskId);
    } catch { /* silent */ }
}
</script>

<template>
    <div v-if="activeTasksStore.hasActiveTasks" class="flex items-center gap-2">
        <div
            v-for="task in activeTasksStore.tasks"
            :key="task.task_id"
            class="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-600 text-xs cursor-pointer hover:bg-blue-100 transition-colors"
            @click="goToChat(task.session_id)"
        >
            <Loader2 :size="12" class="animate-spin" />
            <span class="max-w-[120px] truncate">{{ task.description || 'AI 正在执行...' }}</span>
            <X
                :size="12"
                class="text-blue-400 hover:text-red-500 cursor-pointer"
                @click.stop="handleCancel(task.task_id)"
            />
        </div>
    </div>
</template>
