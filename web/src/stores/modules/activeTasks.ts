import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { getChatActiveTasks } from "@/api";

export interface ActiveTask {
    task_id: string;
    session_id: string;
    executor_id: string;
    source: string;
    done: boolean;
    description?: string;
}

export const useActiveTasksStore = defineStore("activeTasks", () => {
    const tasks = ref<ActiveTask[]>([]);

    const hasActiveTasks = computed(() => tasks.value.length > 0);

    async function fetchActiveTasks() {
        try {
            const res: any = await getChatActiveTasks();
            tasks.value = res?.tasks || res?.data?.tasks || [];
        } catch {
            tasks.value = [];
        }
    }

    function addTask(task: ActiveTask) {
        if (!tasks.value.find((t) => t.task_id === task.task_id)) {
            tasks.value.push(task);
        }
    }

    function removeTask(taskId: string) {
        tasks.value = tasks.value.filter((t) => t.task_id !== taskId);
    }

    function clearAll() {
        tasks.value = [];
    }

    return {
        tasks,
        hasActiveTasks,
        fetchActiveTasks,
        addTask,
        removeTask,
        clearAll,
    };
});
