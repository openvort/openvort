<script setup lang="ts">
import { computed } from "vue";

defineOptions({ name: "VortCheckableTag" });

/** Vort CheckableTag - 可选中标签组件 */

interface Props {
    /** 设置标签的选中状态 */
    checked?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    checked: false
});

const emit = defineEmits<{
    /** 点击标签时触发 */
    change: [checked: boolean];
    /** v-model 支持 */
    "update:checked": [checked: boolean];
}>();

// 定义插槽类型
defineSlots<{
    /** 默认插槽，标签内容 */
    default?: () => unknown;
}>();

// 计算标签类名
const tagClasses = computed(() => {
    const classes = ["vort-checkable-tag"];
    if (props.checked) classes.push("vort-checkable-tag-checked");
    if (props.class) classes.push(props.class);
    return classes;
});

// 处理点击
const handleClick = () => {
    const newChecked = !props.checked;
    emit("change", newChecked);
    emit("update:checked", newChecked);
};
</script>

<template>
    <span :class="tagClasses" @click="handleClick">
        <slot />
    </span>
</template>

<style scoped>
.vort-checkable-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0 7px;
    font-size: 12px;
    line-height: 20px;
    border-radius: var(--vort-radius-sm, 4px);
    box-sizing: border-box;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    border: 1px solid transparent;
    background: rgba(0, 0, 0, 0.02);
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    transition: all var(--vort-duration-normal, 200ms);
}

.vort-checkable-tag:hover {
    color: var(--vort-primary);
}

/* 选中状态 */
.vort-checkable-tag-checked {
    background: var(--vort-primary);
    color: #fff;
}

.vort-checkable-tag-checked:hover {
    background: var(--vort-primary-hover);
    color: #fff;
}
</style>
