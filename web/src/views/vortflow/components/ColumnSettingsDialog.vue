<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Dialog, Button, Checkbox } from "@openvort/vort-ui";
import { GripVertical } from "lucide-vue-next";

export interface ColumnSettingItem {
    key: string;
    title: string;
    fixed?: boolean;
    visible: boolean;
}

interface Props {
    allColumns: ColumnSettingItem[];
}

const props = defineProps<Props>();
const open = defineModel<boolean>("open", { default: false });
const emit = defineEmits<{
    save: [columns: ColumnSettingItem[]];
}>();

const SYSTEM_FIELDS: { key: string; title: string }[] = [
    { key: "workNo", title: "工作项编号" },
    { key: "title", title: "标题" },
    { key: "status", title: "状态" },
    { key: "tags", title: "标签" },
    { key: "iteration", title: "迭代" },
    { key: "owner", title: "负责人" },
    { key: "collaborators", title: "协作者" },
    { key: "creator", title: "创建人" },
    { key: "priority", title: "优先级" },
    { key: "type", title: "工作项类型" },
    { key: "createdAt", title: "创建时间" },
    { key: "planTime", title: "计划时间" },
    { key: "updatedAt", title: "更新时间" },
    { key: "repo", title: "关联仓库" },
    { key: "branch", title: "关联分支" },
    { key: "project", title: "关联项目" },
    { key: "version", title: "版本" },
    { key: "startAt", title: "实际开始时间" },
    { key: "endAt", title: "实际结束时间" },
    { key: "estimateHours", title: "预估工时" },
    { key: "loggedHours", title: "登记工时" },
    { key: "remainHours", title: "剩余工时" },
];

const ALWAYS_VISIBLE_KEYS = new Set(["workNo", "title"]);
const SYSTEM_KEYS = new Set(SYSTEM_FIELDS.map((f) => f.key));

// Local editable copy, reset on dialog open (merge SYSTEM_FIELDS for completeness)
const localColumns = ref<ColumnSettingItem[]>([]);

watch(open, (v) => {
    if (v) {
        const existing = new Set(props.allColumns.map((c) => c.key));
        const merged = props.allColumns.map((c) => ({ ...c }));
        for (const f of SYSTEM_FIELDS) {
            if (!existing.has(f.key)) {
                merged.push({ key: f.key, title: f.title, visible: false });
            }
        }
        localColumns.value = merged;
    }
});

const fieldTitleMap = computed(() => {
    const map = new Map<string, string>();
    for (const f of SYSTEM_FIELDS) map.set(f.key, f.title);
    for (const c of props.allColumns) {
        if (!map.has(c.key)) map.set(c.key, c.title);
    }
    return map;
});

const customFields = computed(() =>
    props.allColumns.filter((c) => !SYSTEM_KEYS.has(c.key)),
);

const visibleSet = computed(() => {
    const set = new Set<string>();
    for (const c of localColumns.value) {
        if (c.visible) set.add(c.key);
    }
    return set;
});

const toggleField = (key: string) => {
    if (ALWAYS_VISIBLE_KEYS.has(key)) return;
    const col = localColumns.value.find((c) => c.key === key);
    if (col) col.visible = !col.visible;
};

// Right panel: visible columns split into fixed (top) and sortable (bottom)
const fixedColumns = computed(() =>
    localColumns.value.filter((c) => c.visible && c.fixed),
);

const sortableColumns = computed(() =>
    localColumns.value.filter((c) => c.visible && !c.fixed),
);

const visibleCount = computed(
    () => localColumns.value.filter((c) => c.visible).length,
);

// --- HTML5 drag-and-drop ---
const draggedIndex = ref<number | null>(null);
const dropTargetIndex = ref<number | null>(null);

const onDragStart = (e: DragEvent, index: number) => {
    draggedIndex.value = index;
    if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(index));
    }
};

const onDragOver = (e: DragEvent, index: number) => {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    dropTargetIndex.value = index;
};

const onDragLeave = () => {
    dropTargetIndex.value = null;
};

const onDrop = (e: DragEvent, toIndex: number) => {
    e.preventDefault();
    const fromIndex = draggedIndex.value;
    if (fromIndex === null || fromIndex === toIndex) {
        draggedIndex.value = null;
        dropTargetIndex.value = null;
        return;
    }

    // Reorder within sortable (non-fixed) columns in localColumns
    const sortableKeys = sortableColumns.value.map((c) => c.key);
    const movedKey = sortableKeys[fromIndex];
    sortableKeys.splice(fromIndex, 1);
    sortableKeys.splice(toIndex, 0, movedKey);

    // Rebuild localColumns: fixed first (preserve order), then sortable in new order, then hidden
    const fixedItems = localColumns.value.filter((c) => c.fixed && c.visible);
    const reorderedSortable = sortableKeys
        .map((k) => localColumns.value.find((c) => c.key === k)!)
        .filter(Boolean);
    const hiddenItems = localColumns.value.filter((c) => !c.visible);
    localColumns.value = [...fixedItems, ...reorderedSortable, ...hiddenItems];

    draggedIndex.value = null;
    dropTargetIndex.value = null;
};

const onDragEnd = () => {
    draggedIndex.value = null;
    dropTargetIndex.value = null;
};

const handleSave = () => {
    emit("save", localColumns.value.map((c) => ({ ...c })));
    open.value = false;
};

const handleCancel = () => {
    open.value = false;
};

const getTitle = (key: string) => fieldTitleMap.value.get(key) || key;
</script>

<template>
    <Dialog v-model:open="open" title="表头显示设置" width="780px">
        <div class="column-settings">
            <!-- Left panel: selectable fields -->
            <div class="panel panel-left">
                <div class="panel-title">
                    可选择字段 ({{ localColumns.length }}个)
                </div>

                <div class="field-section">
                    <div class="section-label">系统字段</div>
                    <div class="field-grid">
                        <label
                            v-for="field in SYSTEM_FIELDS"
                            :key="field.key"
                            class="field-item"
                        >
                            <Checkbox
                                :checked="visibleSet.has(field.key)"
                                :disabled="ALWAYS_VISIBLE_KEYS.has(field.key)"
                                @update:checked="toggleField(field.key)"
                            />
                            <span class="field-name">{{ field.title }}</span>
                        </label>
                    </div>
                </div>

                <div v-if="customFields.length" class="field-section">
                    <div class="section-label">自定义字段</div>
                    <div class="field-grid">
                        <label
                            v-for="field in customFields"
                            :key="field.key"
                            class="field-item"
                        >
                            <Checkbox
                                :checked="visibleSet.has(field.key)"
                                @update:checked="toggleField(field.key)"
                            />
                            <span class="field-name">{{ field.title }}</span>
                        </label>
                    </div>
                </div>
            </div>

            <!-- Right panel: displayed columns with drag sort -->
            <div class="panel panel-right">
                <div class="panel-title">
                    已展示字段 ({{ visibleCount }}个)
                </div>

                <div class="displayed-list">
                    <!-- Fixed columns (not draggable) -->
                    <div
                        v-for="col in fixedColumns"
                        :key="col.key"
                        class="displayed-item displayed-item--fixed"
                    >
                        <GripVertical :size="14" class="drag-handle drag-handle--disabled" />
                        <span class="displayed-name">{{ getTitle(col.key) }}</span>
                    </div>

                    <!-- Divider -->
                    <div v-if="fixedColumns.length" class="fixed-divider">
                        <span class="fixed-divider-text">以上为固定表头</span>
                    </div>

                    <!-- Sortable columns -->
                    <div
                        v-for="(col, idx) in sortableColumns"
                        :key="col.key"
                        class="displayed-item"
                        :class="{
                            'displayed-item--dragging': draggedIndex === idx,
                            'displayed-item--drop-target': dropTargetIndex === idx && draggedIndex !== idx,
                        }"
                        draggable="true"
                        @dragstart="onDragStart($event, idx)"
                        @dragover="onDragOver($event, idx)"
                        @dragleave="onDragLeave"
                        @drop="onDrop($event, idx)"
                        @dragend="onDragEnd"
                    >
                        <GripVertical :size="14" class="drag-handle" />
                        <span class="displayed-name">{{ getTitle(col.key) }}</span>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-2">
                <Button @click="handleCancel">取消</Button>
                <Button type="primary" @click="handleSave">保存到视图</Button>
            </div>
        </template>
    </Dialog>
</template>

<style scoped>
.column-settings {
    display: flex;
    gap: 1px;
    background: #f0f0f0;
    border: 1px solid #f0f0f0;
    border-radius: 6px;
    overflow: hidden;
    min-height: 400px;
    max-height: 500px;
}

.panel {
    flex: 1;
    background: #fff;
    padding: 16px;
    overflow-y: auto;
}

.panel-title {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    margin-bottom: 16px;
}

/* Left panel */
.field-section {
    margin-bottom: 16px;
    overflow: hidden;
}

.section-label {
    font-size: 12px;
    color: #999;
    margin-bottom: 8px;
    padding-bottom: 4px;
    border-bottom: 1px solid #f5f5f5;
}

.field-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 4px 8px;
}

.field-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: 4px;
    user-select: none;
}

.field-item:hover {
    background: #f7f8fa;
}

.field-name {
    font-size: 13px;
    color: #333;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Right panel */
.displayed-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.displayed-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 4px;
    border: 2px solid transparent;
    transition: background 0.15s, border-color 0.15s;
}

.displayed-item:hover {
    background: #f7f8fa;
}

.displayed-item--fixed {
    cursor: default;
}

.displayed-item--fixed .displayed-name {
    color: #999;
}

.displayed-item--dragging {
    opacity: 0.4;
    background: #e6f4ff;
}

.displayed-item--drop-target {
    border-top: 2px solid var(--vort-primary);
}

.drag-handle {
    color: #bbb;
    cursor: grab;
    flex-shrink: 0;
}

.drag-handle--disabled {
    color: #e0e0e0;
    cursor: default;
}

.displayed-name {
    font-size: 13px;
    color: #333;
}

.fixed-divider {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    margin: 4px 0;
}

.fixed-divider::before,
.fixed-divider::after {
    content: "";
    flex: 1;
    height: 1px;
    background: #e8e8e8;
}

.fixed-divider-text {
    font-size: 12px;
    color: #bbb;
    white-space: nowrap;
}
</style>
