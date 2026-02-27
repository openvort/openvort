<script setup lang="ts">
import { ref, computed, watch, useSlots, onMounted, onBeforeUnmount, nextTick } from "vue";

defineOptions({ name: "VortSegmented" });

/** Vort Segmented - 分段控制器组件 */

type SegmentedSize = "large" | "middle" | "small";
type SegmentedShape = "default" | "round";

/** 选项类型 */
interface SegmentedOption {
    /** 选项值 */
    value: string | number;
    /** 显示文本 */
    label?: string;
    /** 图标 */
    icon?: unknown;
    /** 是否禁用 */
    disabled?: boolean;
    /** 额外的类名 */
    className?: string;
    /** 支持自定义扩展属性 */
    [key: string]: unknown;
}

interface Props {
    /** 当前选中的值（v-model） */
    modelValue?: string | number;
    /** 默认选中的值 */
    defaultValue?: string | number;
    /** 选项数据 */
    options?: (string | number | SegmentedOption)[];
    /** 是否禁用所有选项 */
    disabled?: boolean;
    /** 尺寸 */
    size?: SegmentedSize;
    /** 是否填充父容器宽度 */
    block?: boolean;
    /** 形状 */
    shape?: SegmentedShape;
    /** input[type="radio"] 的 name 属性 */
    name?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    size: "middle",
    block: false,
    shape: "default"
});

const emit = defineEmits<{
    "update:modelValue": [value: string | number];
    change: [value: string | number];
}>();

const slots = useSlots();

// ==================== 内部状态 ====================

// 内部值管理
const innerValue = ref<string | number | undefined>(props.modelValue ?? props.defaultValue);

// 容器和选项元素引用
const containerRef = ref<HTMLElement | null>(null);
const itemRefs = ref<HTMLElement[]>([]);

// 滑块位置和尺寸
const thumbStyle = ref({
    left: 0,
    top: 0,
    width: 0,
    height: 0,
    opacity: 0 // 初始隐藏，等计算完成后显示
});

// 监听 modelValue 变化
watch(
    () => props.modelValue,
    (newVal) => {
        if (newVal !== undefined) {
            innerValue.value = newVal;
        }
    }
);

// 当前选中的值
const selectedValue = computed(() => innerValue.value);

// 当前选中项的索引
const selectedIndex = computed(() => {
    return normalizedOptions.value.findIndex((opt) => opt.value === selectedValue.value);
});

// ==================== 格式化选项 ====================

const normalizedOptions = computed<SegmentedOption[]>(() => {
    if (!props.options) return [];
    return props.options.map((opt) => {
        if (typeof opt === "string" || typeof opt === "number") {
            return { value: opt, label: String(opt) };
        }
        return {
            ...opt,
            label: opt.label ?? String(opt.value)
        };
    });
});

// 如果没有设置默认值，自动选中第一个选项
watch(
    normalizedOptions,
    (options) => {
        if (innerValue.value === undefined && options.length > 0) {
            const firstOption = options[0];
            if (firstOption) {
                innerValue.value = firstOption.value;
                emit("update:modelValue", firstOption.value);
            }
        }
    },
    { immediate: true }
);

// ==================== 滑块位置计算 ====================

// 更新滑块位置
const updateThumbPosition = () => {
    const index = selectedIndex.value;
    if (index < 0 || !itemRefs.value[index] || !containerRef.value) {
        thumbStyle.value.opacity = 0;
        return;
    }

    const itemEl = itemRefs.value[index];
    const containerEl = containerRef.value;

    if (!itemEl || !containerEl) return;

    // 使用 offset* 获取相对于父元素的位置和尺寸
    const left = itemEl.offsetLeft;
    const top = itemEl.offsetTop;
    const width = itemEl.offsetWidth;
    const height = itemEl.offsetHeight;

    thumbStyle.value = {
        left,
        top,
        width,
        height,
        opacity: 1
    };
};

// 监听选中值变化，更新滑块位置
watch(selectedIndex, () => {
    nextTick(updateThumbPosition);
});

// 监听 options 变化
watch(
    normalizedOptions,
    () => {
        nextTick(updateThumbPosition);
    },
    { deep: true }
);

// 窗口大小变化时重新计算
const handleResize = () => {
    updateThumbPosition();
};

onMounted(() => {
    // 初始化滑块位置
    nextTick(updateThumbPosition);
    window.addEventListener("resize", handleResize);
});

onBeforeUnmount(() => {
    window.removeEventListener("resize", handleResize);
});

// 设置选项元素引用
const setItemRef = (el: HTMLElement | null, index: number) => {
    if (el) {
        itemRefs.value[index] = el;
    }
};

// ==================== 事件处理 ====================

const handleSelect = (option: SegmentedOption) => {
    if (props.disabled || option.disabled) return;

    innerValue.value = option.value;
    emit("update:modelValue", option.value);
    emit("change", option.value);
};

// 键盘导航
const handleKeydown = (event: KeyboardEvent, index: number) => {
    const options = normalizedOptions.value;
    let nextIndex = index;

    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
        event.preventDefault();
        nextIndex = index - 1;
        if (nextIndex < 0) nextIndex = options.length - 1;
    } else if (event.key === "ArrowRight" || event.key === "ArrowDown") {
        event.preventDefault();
        nextIndex = index + 1;
        if (nextIndex >= options.length) nextIndex = 0;
    }

    // 跳过禁用的选项
    while (options[nextIndex]?.disabled && nextIndex !== index) {
        if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
            nextIndex = nextIndex - 1;
            if (nextIndex < 0) nextIndex = options.length - 1;
        } else {
            nextIndex = nextIndex + 1;
            if (nextIndex >= options.length) nextIndex = 0;
        }
    }

    if (nextIndex !== index) {
        const nextOption = options[nextIndex];
        if (nextOption && !nextOption.disabled) {
            handleSelect(nextOption);
            // 聚焦到下一个选项
            const nextButton = itemRefs.value[nextIndex];
            nextButton?.focus();
        }
    }
};

// ==================== 样式计算 ====================

// 容器样式
const containerClasses = computed(() => {
    const classes = ["vort-segmented"];
    // 尺寸
    if (props.size === "large") classes.push("vort-segmented-lg");
    if (props.size === "small") classes.push("vort-segmented-sm");
    // block 模式
    if (props.block) classes.push("vort-segmented-block");
    // 形状
    classes.push(props.shape === "round" ? "vort-segmented-round" : "vort-segmented-default");
    // 禁用
    if (props.disabled) classes.push("vort-segmented-disabled");
    // 自定义类名
    if (props.class) classes.push(props.class);
    return classes;
});

// 选项样式（移除选中项的背景，由滑块提供）
const getItemClasses = (option: SegmentedOption, _index: number) => {
    const isSelected = selectedValue.value === option.value;
    const isDisabled = props.disabled || option.disabled;

    const classes = ["vort-segmented-item"];
    // 尺寸
    classes.push(`vort-segmented-item-${props.size}`);
    // 形状
    classes.push(props.shape === "round" ? "vort-segmented-item-round" : "vort-segmented-item-default");
    // block 模式
    if (props.block) classes.push("vort-segmented-item-block");
    // 选中状态
    if (isSelected) classes.push("vort-segmented-item-selected");
    // 禁用状态
    if (isDisabled) classes.push("vort-segmented-item-disabled");
    // 额外类名
    if (option.className) classes.push(option.className);

    return classes;
};

// 滑块样式
const thumbClasses = computed(() => {
    const classes = ["vort-segmented-thumb"];
    classes.push(props.shape === "round" ? "vort-segmented-thumb-round" : "vort-segmented-thumb-default");
    return classes;
});

// 标签样式
const labelClasses = computed(() => ["vort-segmented-label"]);

// 生成唯一 ID
const uniqueId = computed(() => props.name || `vort-segmented-${Math.random().toString(36).slice(2, 9)}`);
</script>

<template>
    <div ref="containerRef" :class="containerClasses" role="radiogroup" :aria-disabled="disabled">
        <!-- 滑块背景 -->
        <div
            :class="thumbClasses"
            :style="{
                left: `${thumbStyle.left}px`,
                top: `${thumbStyle.top}px`,
                width: `${thumbStyle.width}px`,
                height: `${thumbStyle.height}px`,
                opacity: thumbStyle.opacity
            }"
            aria-hidden="true"
        />

        <!-- 选项 -->
        <label
            v-for="(option, index) in normalizedOptions"
            :key="option.value"
            :ref="(el) => setItemRef(el as HTMLElement, index)"
            :class="getItemClasses(option, index)"
            :aria-checked="selectedValue === option.value"
            :tabindex="selectedValue === option.value ? 0 : -1"
            @click="handleSelect(option)"
            @keydown="handleKeydown($event, index)"
        >
            <!-- 隐藏的 radio input -->
            <input
                type="radio"
                :name="uniqueId"
                :value="option.value"
                :checked="selectedValue === option.value"
                :disabled="disabled || option.disabled"
                class="vort-segmented-input"
            />

            <!-- 标签内容 -->
            <span :class="labelClasses">
                <!-- 图标插槽 -->
                <slot name="icon" :option="option" :selected="selectedValue === option.value">
                    <component v-if="option.icon" :is="option.icon" class="vort-segmented-icon" />
                </slot>

                <!-- 标签文本插槽 -->
                <slot name="label" :option="option" :selected="selectedValue === option.value">
                    <span v-if="option.label" class="vort-segmented-label-text">{{ option.label }}</span>
                </slot>
            </span>
        </label>
    </div>
</template>

<style scoped>
/* ============ 容器样式 ============ */
.vort-segmented {
    position: relative;
    display: inline-flex;
    padding: 2px;
    background: var(--vort-fill-quaternary, rgba(0, 0, 0, 0.02));
}

.vort-segmented-default {
    border-radius: var(--vort-border-radius, 6px);
}

.vort-segmented-round {
    border-radius: 9999px;
}

.vort-segmented-block {
    display: flex;
    width: 100%;
}

.vort-segmented-disabled {
    opacity: 0.6;
    cursor: not-allowed;
}

/* ============ 选项样式 ============ */
.vort-segmented-item {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    user-select: none;
    z-index: 1;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
    transition: color 200ms cubic-bezier(0.645, 0.045, 0.355, 1);
}

.vort-segmented-item-default {
    border-radius: var(--vort-border-radius, 6px);
}

.vort-segmented-item-round {
    border-radius: 9999px;
}

/* 尺寸 */
.vort-segmented-item-large {
    min-height: 36px;
    padding: 6px 16px;
    font-size: 16px;
}

.vort-segmented-item-middle {
    min-height: 28px;
    padding: 4px 12px;
    font-size: 14px;
}

.vort-segmented-item-small {
    min-height: 20px;
    padding: 2px 8px;
    font-size: 12px;
}

/* block 模式 */
.vort-segmented-item-block {
    flex: 1;
}

/* 选中状态 */
.vort-segmented-item-selected {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

/* 禁用状态 */
.vort-segmented-item-disabled {
    cursor: not-allowed;
    color: var(--vort-text-disabled, rgba(0, 0, 0, 0.25));
}

/* 伪元素用于 hover/active 背景效果 */
.vort-segmented-item::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    opacity: 0;
    background-color: transparent;
    transition: all 200ms cubic-bezier(0.645, 0.045, 0.355, 1);
    pointer-events: none;
    z-index: -1;
}

/* Hover 效果 - 仅对未选中且未禁用的选项 */
.vort-segmented-item:not(.vort-segmented-item-selected):not(.vort-segmented-item-disabled):hover {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-segmented-item:not(.vort-segmented-item-selected):not(.vort-segmented-item-disabled):hover::after {
    opacity: 1;
    background-color: rgba(0, 0, 0, 0.06);
}

/* Active/Click 效果 - 仅对未选中且未禁用的选项 */
.vort-segmented-item:not(.vort-segmented-item-selected):not(.vort-segmented-item-disabled):active {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-segmented-item:not(.vort-segmented-item-selected):not(.vort-segmented-item-disabled):active::after {
    opacity: 1;
    background-color: rgba(0, 0, 0, 0.15);
}

/* 聚焦状态 */
.vort-segmented-item:focus-visible {
    outline: none;
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

/* 禁用状态下的项 */
.vort-segmented-disabled .vort-segmented-item {
    cursor: not-allowed;
}

/* ============ 滑块样式 ============ */
.vort-segmented-thumb {
    position: absolute;
    z-index: 0;
    pointer-events: none;
    background: #fff;
    box-shadow:
        0 1px 2px 0 rgba(0, 0, 0, 0.03),
        0 1px 6px -1px rgba(0, 0, 0, 0.02),
        0 2px 4px 0 rgba(0, 0, 0, 0.02);
    transition: all 200ms cubic-bezier(0.645, 0.045, 0.355, 1);
}

.vort-segmented-thumb-default {
    border-radius: var(--vort-border-radius, 6px);
}

.vort-segmented-thumb-round {
    border-radius: 9999px;
}

/* ============ 标签样式 ============ */
.vort-segmented-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.vort-segmented-icon {
    width: 16px;
    height: 16px;
}

/* ============ 隐藏的 radio input ============ */
.vort-segmented-input {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}
</style>
