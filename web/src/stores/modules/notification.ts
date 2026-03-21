import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { getChatUnreadCounts, getNotificationUnreadCount } from "@/api";

export const useNotificationStore = defineStore("notification", () => {
    const unreadCounts = ref<Record<string, number>>({});
    const taskStatuses = ref<Record<string, { status: string; jobName: string }>>({});
    const vortflowUnreadCount = ref(0);

    const totalUnreadCount = computed(() =>
        Object.values(unreadCounts.value).reduce((sum, c) => sum + c, 0)
    );

    function getUnread(sessionId: string): number {
        return unreadCounts.value[sessionId] || 0;
    }

    function setUnread(sessionId: string, count: number) {
        if (count > 0) {
            unreadCounts.value[sessionId] = count;
        } else {
            delete unreadCounts.value[sessionId];
        }
    }

    function clearUnread(sessionId: string) {
        delete unreadCounts.value[sessionId];
    }

    function setTaskStatus(memberId: string, status: string, jobName: string = "") {
        if (status === "idle") {
            delete taskStatuses.value[memberId];
        } else {
            taskStatuses.value[memberId] = { status, jobName };
        }
    }

    function getTaskStatus(memberId: string) {
        return taskStatuses.value[memberId] || null;
    }

    function incrementVortflowUnread() {
        vortflowUnreadCount.value++;
    }

    function clearVortflowUnread() {
        vortflowUnreadCount.value = 0;
    }

    async function fetchUnreadCounts() {
        try {
            const res = await getChatUnreadCounts();
            const counts: Record<string, number> = (res as any)?.data?.counts || (res as any)?.counts || {};
            unreadCounts.value = {};
            for (const [sid, count] of Object.entries(counts)) {
                if (count > 0) unreadCounts.value[sid] = count;
            }
        } catch {
            // silent
        }
    }

    async function fetchVortflowUnreadCount() {
        try {
            const res: any = await getNotificationUnreadCount("vortflow");
            vortflowUnreadCount.value = res?.count || 0;
        } catch {
            // silent
        }
    }

    return {
        unreadCounts,
        taskStatuses,
        totalUnreadCount,
        vortflowUnreadCount,
        getUnread,
        setUnread,
        clearUnread,
        setTaskStatus,
        getTaskStatus,
        incrementVortflowUnread,
        clearVortflowUnread,
        fetchUnreadCounts,
        fetchVortflowUnreadCount,
    };
});
