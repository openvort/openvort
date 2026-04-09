import { onBeforeUnmount, ref, watch, type Ref } from "vue";

export function useGanttScroll(
    tableScrollEl: Ref<HTMLElement | null>,
    ganttScrollEl: Ref<HTMLElement | null>,
) {
    const isSyncing = ref(false);

    function syncTableToGantt() {
        if (isSyncing.value) return;
        const table = tableScrollEl.value;
        const gantt = ganttScrollEl.value;
        if (!table || !gantt) return;
        isSyncing.value = true;
        gantt.scrollTop = table.scrollTop;
        requestAnimationFrame(() => { isSyncing.value = false; });
    }

    function syncGanttToTable() {
        if (isSyncing.value) return;
        const table = tableScrollEl.value;
        const gantt = ganttScrollEl.value;
        if (!table || !gantt) return;
        isSyncing.value = true;
        table.scrollTop = gantt.scrollTop;
        requestAnimationFrame(() => { isSyncing.value = false; });
    }

    function attach() {
        tableScrollEl.value?.addEventListener("scroll", syncTableToGantt, { passive: true });
        ganttScrollEl.value?.addEventListener("scroll", syncGanttToTable, { passive: true });
    }

    function detach() {
        tableScrollEl.value?.removeEventListener("scroll", syncTableToGantt);
        ganttScrollEl.value?.removeEventListener("scroll", syncGanttToTable);
    }

    watch([tableScrollEl, ganttScrollEl], ([t, g]) => {
        detach();
        if (t && g) attach();
    });

    onBeforeUnmount(detach);

    return { syncTableToGantt, syncGanttToTable };
}
