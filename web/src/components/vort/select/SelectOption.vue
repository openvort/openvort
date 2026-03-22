<script setup lang="ts">
import { inject, onMounted, onBeforeUnmount, useSlots, computed, type VNode, type Slot } from "vue";
import type { SelectOptionContext } from "./types";

/**
 * SelectOption - 选择器选项子组件
 *
 * 用于配合 vort-select 组件使用，支持声明式定义选项
 * 支持自定义渲染内容，例如图标、组件等
 *
 * @example
 * <vort-select v-model="value">
 *   <vort-select-option value="jack">Jack</vort-select-option>
 *   <vort-select-option value="lucy" disabled>Lucy</vort-select-option>
 *   <vort-select-option value="1"><SignTag :value="1" /></vort-select-option>
 * </vort-select>
 */

defineOptions({ name: "VortSelectOption" });

defineSlots<{
    default?: () => unknown;
}>();

interface Props {
    /** 选项值 */
    value: string | number;
    /** 选项标签（可选，默认使用 slot 内容） */
    label?: string;
    /** 是否禁用 */
    disabled?: boolean;
}

export interface SelectOptionProps extends Props {}

const props = withDefaults(defineProps<Props>(), {
    label: undefined,
    disabled: false
});

const slots = useSlots();

// 辅助函数：安全获取默认插槽内容
const getDefaultSlot = (): VNode[] => {
    const slotFn = slots.default;
    if (!slotFn) return [];
    const result = slotFn();
    return Array.isArray(result) ? result : [result];
};

// 检查插槽是否包含组件（非纯文本）
const hasComponentSlot = computed(() => {
    const defaultSlot = getDefaultSlot();
    if (defaultSlot.length === 0) return false;

    // 检查是否有非文本节点（如组件）
    return defaultSlot.some((node: VNode) => {
        // 如果是对象类型且有 type 属性，可能是组件或元素
        return typeof node.type === "object" || typeof node.type === "function" || (typeof node.type === "string" && node.type !== "");
    });
});

// 获取默认插槽的文本内容作为 label
const computedLabel = computed(() => {
    if (props.label) return props.label;
    // 尝试从插槽获取文本内容
    const defaultSlot = getDefaultSlot();
    if (defaultSlot.length > 0) {
        // 递归提取文本内容
        const extractText = (nodes: VNode[]): string => {
            return nodes
                .map((node) => {
                    if (typeof node.children === "string") {
                        return node.children;
                    }
                    if (Array.isArray(node.children)) {
                        return extractText(node.children as VNode[]);
                    }
                    if (node.children && typeof node.children === "object" && "default" in node.children) {
                        // 处理函数式插槽
                        const slotContent = (node.children as { default?: () => VNode[] | VNode }).default;
                        if (slotContent) {
                            const slotResult = slotContent();
                            return extractText(Array.isArray(slotResult) ? slotResult : [slotResult]);
                        }
                    }
                    return "";
                })
                .join("");
        };
        const text = extractText(defaultSlot);
        // 如果提取到的文本为空但有组件插槽，使用 value 作为 label
        if (!text && hasComponentSlot.value) {
            return String(props.value);
        }
        return text || String(props.value);
    }
    return String(props.value);
});

// 创建渲染函数，用于在下拉列表中渲染自定义内容
const renderFunction = computed(() => {
    if (!hasComponentSlot.value) return undefined;
    // 返回一个函数，调用时返回插槽内容
    return () => slots.default?.();
});

// 注入父组件提供的注册方法
const selectContext = inject<SelectOptionContext | null>("vortSelectContext", null);

// 组件挂载时注册选项
onMounted(() => {
    if (selectContext) {
        selectContext.registerOption({
            value: props.value,
            label: computedLabel.value,
            disabled: props.disabled,
            render: renderFunction.value
        });
    }
});

// 组件卸载时注销选项
onBeforeUnmount(() => {
    if (selectContext) {
        selectContext.unregisterOption(props.value);
    }
});
</script>

<template>
    <!-- 
        此组件不渲染任何内容，仅作为选项数据的载体
        实际渲染由父组件 Select 完成
    -->
</template>
