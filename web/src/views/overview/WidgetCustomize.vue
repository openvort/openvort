<script setup lang="ts">
import { GripVertical, Eye, EyeOff } from "lucide-vue-next";

export interface WidgetConfig {
    id: string;
    title: string;
    description: string;
    visible: boolean;
    /** 布局占比: full=整行, half=半行 */
    span: "full" | "half";
}

const props = defineProps<{
    open: boolean;
    widgets: WidgetConfig[];
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "save", widgets: WidgetConfig[]): void;
}>();

import { ref, watch } from "vue";

const localWidgets = ref<WidgetConfig[]>([]);

watch(() => props.open, (val) => {
    if (val) localWidgets.value = JSON.parse(JSON.stringify(props.widgets));
});

function toggleVisible(id: string) {
    const w = localWidgets.value.find(w => w.id === id);
    if (w) w.visible = !w.visible;
}

function toggleSpan(id: string) {
    const w = localWidgets.value.find(w => w.id === id);
    if (w) w.span = w.span === "full" ? "half" : "full";
}

// ---- 拖拽排序 ----
const dragIndex = ref<number | null>(null);
const dropIndex = ref<number | null>(null);

function onDragStart(index: number, e: DragEvent) {
    dragIndex.value = index;
    if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(index));
    }
}

function onDragOver(index: number, e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
    dropIndex.value = index;
}

function onDrop(index: number, e: DragEvent) {
    e.preventDefault();
    const from = dragIndex.value;
    if (from === null || from === index) return;
    const arr = localWidgets.value;
    const [item] = arr.splice(from, 1);
    arr.splice(index, 0, item);
    dragIndex.value = null;
    dropIndex.value = null;
}

function onDragEnd() {
    dragIndex.value = null;
    dropIndex.value = null;
}

function handleSave() {
    emit("save", JSON.parse(JSON.stringify(localWidgets.value)));
    emit("update:open", false);
}
</script>

<template>
    <VortDrawer :open="open" title="自定义概览" :width="420" @update:open="emit('update:open', $event)">
        <div class="space-y-2">
            <p class="text-sm text-gray-500 mb-4">拖动排序、显示/隐藏组件，打造你的专属概览页</p>
            <div
                v-for="(widget, index) in localWidgets"
                :key="widget.id"
                draggable="true"
                class="flex items-center gap-3 p-3 rounded-lg border bg-white transition-all duration-150"
                :class="[
                    !widget.visible ? 'opacity-50' : '',
                    dragIndex === index ? 'border-blue-400 shadow-md opacity-70 scale-[0.98]' : 'border-gray-200',
                    dropIndex === index && dragIndex !== index ? 'border-blue-300 border-dashed bg-blue-50/50' : '',
                ]"
                @dragstart="onDragStart(index, $event)"
                @dragover="onDragOver(index, $event)"
                @drop="onDrop(index, $event)"
                @dragend="onDragEnd"
            >
                <GripVertical :size="16" class="text-gray-300 flex-shrink-0 cursor-grab active:cursor-grabbing" />
                <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium text-gray-800">{{ widget.title }}</div>
                    <div class="text-xs text-gray-400 mt-0.5">{{ widget.description }}</div>
                </div>
                <div class="flex items-center gap-1 flex-shrink-0">
                    <VortTooltip :title="widget.span === 'full' ? '整行' : '半行'">
                        <VortButton size="small" variant="text" @click="toggleSpan(widget.id)">
                            <span class="text-xs text-gray-500">{{ widget.span === 'full' ? '整行' : '半行' }}</span>
                        </VortButton>
                    </VortTooltip>
                    <VortButton size="small" variant="text" @click="toggleVisible(widget.id)">
                        <Eye v-if="widget.visible" :size="16" class="text-gray-500" />
                        <EyeOff v-else :size="16" class="text-gray-300" />
                    </VortButton>
                </div>
            </div>
        </div>
        <template #footer>
            <div class="flex justify-end gap-2">
                <VortButton @click="emit('update:open', false)">取消</VortButton>
                <VortButton variant="primary" @click="handleSave">保存布局</VortButton>
            </div>
        </template>
    </VortDrawer>
</template>
