import { ref, computed } from "vue";

export interface GanttUndoSnapshot {
    rowId: string;
    planStartDate: string;
    planEndDate: string;
    progress: number;
    testTime?: string;
    draftTime?: string;
    releaseTime?: string;
}

export interface GanttUndoRecord {
    prev: GanttUndoSnapshot;
    next: GanttUndoSnapshot;
}

const MAX_HISTORY = 5;

export function useGanttUndo() {
    const undoStack = ref<GanttUndoRecord[]>([]);
    const redoStack = ref<GanttUndoRecord[]>([]);

    const canUndo = computed(() => undoStack.value.length > 0);
    const canRedo = computed(() => redoStack.value.length > 0);

    function pushRecord(record: GanttUndoRecord) {
        undoStack.value.push(record);
        if (undoStack.value.length > MAX_HISTORY) {
            undoStack.value.shift();
        }
        redoStack.value = [];
    }

    function undo(): GanttUndoSnapshot | null {
        const record = undoStack.value.pop();
        if (!record) return null;
        redoStack.value.push(record);
        return record.prev;
    }

    function redo(): GanttUndoSnapshot | null {
        const record = redoStack.value.pop();
        if (!record) return null;
        undoStack.value.push(record);
        return record.next;
    }

    function reset() {
        undoStack.value = [];
        redoStack.value = [];
    }

    return { canUndo, canRedo, pushRecord, undo, redo, reset };
}
