<script setup lang="ts">
import type { Priority } from "./WorkItemTable.types";

interface Props {
    modelValue?: Priority;
    disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    modelValue: "none",
    disabled: false
});

const emit = defineEmits<{
    (e: "update:modelValue", value: Priority): void;
    (e: "change", value: Priority): void;
}>();

const priorityOptions: Array<{ label: string; value: Priority }> = [
    { label: "紧急", value: "urgent" },
    { label: "高", value: "high" },
    { label: "中", value: "medium" },
    { label: "低", value: "low" },
    { label: "无优先级", value: "none" }
];

const priorityLabelMap: Record<Priority, string> = {
    urgent: "紧急",
    high: "高",
    medium: "中",
    low: "低",
    none: "无优先级"
};

const priorityClassMap: Record<Priority, string> = {
    urgent: "text-red-500 border-red-500 bg-red-50",
    high: "text-amber-500 border-amber-500 bg-amber-50",
    medium: "text-blue-500 border-blue-500 bg-blue-50",
    low: "text-emerald-500 border-emerald-500 bg-emerald-50",
    none: "text-gray-400 border-gray-300 bg-gray-50"
};

const open = defineModel<boolean>("open", { default: false });

const handleSelect = (value: Priority) => {
    emit("update:modelValue", value);
    emit("change", value);
    open.value = false;
};
</script>

<template>
    <vort-popover
        v-model:open="open"
        trigger="click"
        placement="bottomLeft"
        :arrow="false"
        :disabled="disabled"
    >
        <slot>
            <div class="priority-cell-trigger" :class="{ 'is-disabled': disabled }">
                <span class="priority-pill" :class="priorityClassMap[modelValue]">
                    {{ priorityLabelMap[modelValue] }}
                </span>
            </div>
        </slot>
        <template #content>
            <div class="priority-cell-menu" @click.stop>
                <div
                    v-for="opt in priorityOptions"
                    :key="opt.value"
                    class="priority-cell-menu-item"
                    :class="{ 'is-selected': modelValue === opt.value, 'is-disabled': disabled }"
                    @click.stop="!disabled && handleSelect(opt.value)"
                >
                    <span class="priority-pill" :class="priorityClassMap[opt.value]">
                        {{ opt.label }}
                    </span>
                </div>
            </div>
        </template>
    </vort-popover>
</template>

<style scoped>
.priority-cell-trigger {
    padding: 2px 8px;
    cursor: pointer;
}

.priority-cell-trigger.is-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}

.priority-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    border: 1px solid;
}

.priority-cell-menu {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 100px;
}

.priority-cell-menu-item {
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
}

.priority-cell-menu-item:hover {
    background-color: #f5f5f5;
}

.priority-cell-menu-item.is-selected {
    background-color: #e6f4ff;
}

.priority-cell-menu-item.is-disabled {
    cursor: not-allowed;
    opacity: 0.5;
}
</style>
