<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { Tooltip } from "@/components/vort/tooltip";
import type { SliderProps, Mark } from "./types";

defineOptions({ name: "VortSlider" });

/** Vort Slider - 滑动输入条组件 */

const props = withDefaults(defineProps<SliderProps>(), {
    min: 0,
    max: 100,
    step: 1,
    disabled: false,
    tooltip: true,
    range: false,
    vertical: false,
    reverse: false,
    included: true,
    dots: false
});

const emit = defineEmits<{
    "update:modelValue": [value: number | [number, number]];
    change: [value: number | [number, number]];
    afterChange: [value: number | [number, number]];
}>();

// 滑块容器和轨道引用
const railRef = ref<HTMLElement | null>(null);
const isDragging = ref(false);
const activeHandleIndex = ref<number | null>(null);

// 显示 Tooltip 状态
const showTooltip = ref<boolean[]>([false, false]);

// Tooltip 引用，用于强制更新位置
const tooltipRef0 = ref<InstanceType<typeof Tooltip> | null>(null);
const tooltipRef1 = ref<InstanceType<typeof Tooltip> | null>(null);

// 内部值
const internalValue = ref<[number, number]>([props.min, props.min]);

// 初始化值
const initValue = () => {
    if (props.modelValue === undefined) {
        internalValue.value = [props.min, props.min];
    } else if (props.range && Array.isArray(props.modelValue)) {
        internalValue.value = [props.modelValue[0], props.modelValue[1]];
    } else if (!props.range && typeof props.modelValue === "number") {
        internalValue.value = [props.min, props.modelValue];
    } else {
        internalValue.value = [props.min, props.min];
    }
};

initValue();

// 监听外部值变化
watch(
    () => props.modelValue,
    (newVal) => {
        if (newVal === undefined) {
            internalValue.value = [props.min, props.min];
        } else if (props.range && Array.isArray(newVal)) {
            internalValue.value = [newVal[0], newVal[1]];
        } else if (!props.range && typeof newVal === "number") {
            internalValue.value = [props.min, newVal];
        }
    }
);

// 计算百分比
const getPercent = (value: number): number => {
    const percent = ((value - props.min) / (props.max - props.min)) * 100;
    return Math.max(0, Math.min(100, percent));
};

// 获取数字的小数位数
const getDecimalPlaces = (num: number): number => {
    const str = String(num);
    const decimalIndex = str.indexOf(".");
    return decimalIndex === -1 ? 0 : str.length - decimalIndex - 1;
};

// 根据百分比计算值
const getValueFromPercent = (percent: number): number => {
    let value = props.min + (percent / 100) * (props.max - props.min);

    // 步长处理
    if (props.step > 0) {
        const steps = Math.round((value - props.min) / props.step);
        value = props.min + steps * props.step;

        // 修正浮点数精度问题：根据 step 的小数位数进行四舍五入
        const decimals = getDecimalPlaces(props.step);
        const factor = Math.pow(10, decimals);
        value = Math.round(value * factor) / factor;
    }

    // 边界限制
    value = Math.max(props.min, Math.min(props.max, value));

    return value;
};

// 根据位置计算百分比
const getPercentFromPosition = (clientPos: number): number => {
    if (!railRef.value) return 0;

    const rect = railRef.value.getBoundingClientRect();
    let percent = 0;

    if (props.vertical) {
        const total = rect.height;
        const offset = rect.bottom - clientPos;
        percent = (offset / total) * 100;
    } else {
        const total = rect.width;
        const offset = clientPos - rect.left;
        percent = (offset / total) * 100;
    }

    if (props.reverse) {
        percent = 100 - percent;
    }

    return Math.max(0, Math.min(100, percent));
};

// 轨道样式（已填充部分）
const trackStyle = computed(() => {
    const [startValue, endValue] = internalValue.value;
    const startPercent = getPercent(props.range ? startValue : props.min);
    const endPercent = getPercent(endValue);

    if (props.vertical) {
        if (props.reverse) {
            return {
                top: `${startPercent}%`,
                height: `${endPercent - startPercent}%`,
                bottom: "auto"
            };
        } else {
            return {
                bottom: `${startPercent}%`,
                height: `${endPercent - startPercent}%`,
                top: "auto"
            };
        }
    } else {
        if (props.reverse) {
            return {
                right: `${startPercent}%`,
                width: `${endPercent - startPercent}%`,
                left: "auto"
            };
        } else {
            return {
                left: `${startPercent}%`,
                width: `${endPercent - startPercent}%`,
                right: "auto"
            };
        }
    }
});

// 手柄位置
const getHandleStyle = (index: number) => {
    const value = internalValue.value[index] ?? 0;
    const percent = getPercent(value);

    if (props.vertical) {
        return {
            [props.reverse ? "top" : "bottom"]: `${percent}%`,
            [props.reverse ? "bottom" : "top"]: "auto",
            left: "0",
            right: "auto"
        };
    } else {
        return {
            [props.reverse ? "right" : "left"]: `${percent}%`,
            [props.reverse ? "left" : "right"]: "auto",
            top: "0",
            bottom: "auto"
        };
    }
};

// 处理点击轨道
const handleRailClick = (e: MouseEvent) => {
    if (props.disabled) return;

    // 如果点击的是手柄，不处理
    const target = e.target as HTMLElement;
    if (target.closest(".vort-slider-handle")) {
        return;
    }

    const clientPos = props.vertical ? e.clientY : e.clientX;
    const percent = getPercentFromPosition(clientPos);
    const value = getValueFromPercent(percent);

    if (props.range) {
        const [start, end] = internalValue.value;
        const mid = (start + end) / 2;

        if (value < mid) {
            internalValue.value = [value, end];
        } else {
            internalValue.value = [start, value];
        }
    } else {
        internalValue.value = [props.min, value];
    }

    emitChange();
    emitAfterChange();
};

// 开始拖拽
const handleMouseDown = (e: MouseEvent, index: number) => {
    if (props.disabled) return;

    e.preventDefault();
    e.stopPropagation();

    // 让当前聚焦的元素失焦，避免与其他输入组件（如 InputNumber）的焦点冲突
    if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
    }

    isDragging.value = true;
    activeHandleIndex.value = index;
    showTooltip.value[index] = true;

    // 立即更新一次位置
    handleMouseMove(e);

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
};

// 拖拽中
const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging.value || activeHandleIndex.value === null) return;

    const clientPos = props.vertical ? e.clientY : e.clientX;
    const percent = getPercentFromPosition(clientPos);
    const value = getValueFromPercent(percent);

    const index = activeHandleIndex.value;
    const newValue = [...internalValue.value] as [number, number];

    if (props.range) {
        // 范围模式：确保两个手柄不交叉
        if (index === 0) {
            newValue[0] = Math.min(value, newValue[1]);
        } else {
            newValue[1] = Math.max(value, newValue[0]);
        }
    } else {
        newValue[1] = value;
    }

    internalValue.value = newValue;
    emitChange();

    // 强制更新 Tooltip 位置
    nextTick(() => {
        if (index === 0 && tooltipRef0.value) {
            (tooltipRef0.value as any).updatePosition?.();
        } else if (index === 1 && tooltipRef1.value) {
            (tooltipRef1.value as any).updatePosition?.();
        }
    });
};

// 结束拖拽
const handleMouseUp = () => {
    if (!isDragging.value) return;

    isDragging.value = false;
    if (activeHandleIndex.value !== null) {
        showTooltip.value[activeHandleIndex.value] = false;
    }
    activeHandleIndex.value = null;

    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);

    emitAfterChange();
};

// 键盘控制
const handleKeyDown = (e: KeyboardEvent, index: number) => {
    if (props.disabled) return;

    const step = props.step || 1;
    let handled = false;

    const newValue = [...internalValue.value] as [number, number];

    switch (e.key) {
        case "ArrowLeft":
        case "ArrowDown":
            newValue[index] = Math.max(props.min, (newValue[index] ?? 0) - step);
            handled = true;
            break;
        case "ArrowRight":
        case "ArrowUp":
            newValue[index] = Math.min(props.max, (newValue[index] ?? 0) + step);
            handled = true;
            break;
        case "Home":
            newValue[index] = props.min;
            handled = true;
            break;
        case "End":
            newValue[index] = props.max;
            handled = true;
            break;
    }

    if (handled) {
        e.preventDefault();

        // 范围模式：确保两个手柄不交叉
        if (props.range) {
            if (index === 0) {
                newValue[0] = Math.min(newValue[0], newValue[1]);
            } else {
                newValue[1] = Math.max(newValue[1], newValue[0]);
            }
        }

        internalValue.value = newValue;
        emitChange();
        emitAfterChange();
    }
};

// 触发事件
const emitChange = () => {
    const value = props.range ? [...internalValue.value] : internalValue.value[1];
    emit("update:modelValue", value as any);
    emit("change", value as any);
};

const emitAfterChange = () => {
    const value = props.range ? [...internalValue.value] : internalValue.value[1];
    emit("afterChange", value as any);
};

// 格式化 Tooltip 显示内容
const formatTooltip = (value: number): string => {
    if (props.tipFormatter === null) return "";
    if (props.tipFormatter) return props.tipFormatter(value);
    return String(value);
};

// 解析标记
const parsedMarks = computed(() => {
    if (!props.marks) return [];

    return Object.keys(props.marks)
        .map((key) => {
            const value = Number(key);
            const mark = props.marks![value];

            if (typeof mark === "string") {
                return { value, label: mark };
            } else if (typeof mark === "object") {
                return { value, label: mark.label || String(value) };
            }
            return { value, label: String(value) };
        })
        .filter((mark) => mark.value >= props.min && mark.value <= props.max);
});

// 点样式
const dotStyle = (value: number) => {
    const percent = getPercent(value);
    if (props.vertical) {
        return {
            [props.reverse ? "top" : "bottom"]: `${percent}%`
        };
    } else {
        return {
            [props.reverse ? "right" : "left"]: `${percent}%`
        };
    }
};

// 计算步长点
const stepDots = computed(() => {
    // 只有开启 dots 时才显示所有步长点
    if (!props.dots) return [];

    const dots: number[] = [];
    const total = props.max - props.min;
    const count = Math.floor(total / props.step);

    for (let i = 0; i <= count; i++) {
        const value = props.min + i * props.step;
        if (value >= props.min && value <= props.max) {
            dots.push(value);
        }
    }

    return dots;
});

// 判断点是否激活
const isDotActive = (value: number): boolean => {
    const [start, end] = internalValue.value;
    if (props.included) {
        return value >= (props.range ? start : props.min) && value <= end;
    } else {
        return value === end || (props.range && value === start);
    }
};

// 显示 Tooltip 条件
const shouldShowTooltip = (index: number): boolean => {
    if (props.tooltip === false || props.tipFormatter === null) return false;
    if (props.tooltip === "always") return true;
    return showTooltip.value[index] || isDragging.value;
};

// 处理鼠标进入/离开手柄
const handleHandleMouseEnter = (index: number) => {
    if (props.disabled || isDragging.value) return;
    showTooltip.value[index] = true;
};

const handleHandleMouseLeave = (index: number) => {
    if (props.disabled || isDragging.value) return;
    showTooltip.value[index] = false;
};

// 清理事件监听
onBeforeUnmount(() => {
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
});

// 计算容器类名
const containerClass = computed(() => {
    const classes = ["vort-slider"];
    if (props.disabled) classes.push("vort-slider-disabled");
    if (props.vertical) classes.push("vort-slider-vertical");
    if (parsedMarks.value.length > 0) classes.push("vort-slider-with-marks");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div :class="containerClass" @click="handleRailClick">
        <div ref="railRef" class="vort-slider-rail">
            <!-- 轨道 -->
            <div class="vort-slider-track" :style="trackStyle" />

            <!-- 步长点 -->
            <template v-if="dots">
                <span
                    v-for="dot in stepDots"
                    :key="dot"
                    class="vort-slider-dot"
                    :class="{ 'vort-slider-dot-active': isDotActive(dot) }"
                    :style="dotStyle(dot)"
                />
            </template>

            <!-- 标记点 -->
            <template v-if="marks && !dots">
                <span
                    v-for="mark in parsedMarks"
                    :key="mark.value"
                    class="vort-slider-dot"
                    :class="{ 'vort-slider-dot-active': isDotActive(mark.value) }"
                    :style="dotStyle(mark.value)"
                />
            </template>

            <!-- 手柄 1（范围模式的起始手柄，或单值模式隐藏） -->
            <div
                v-if="range"
                class="vort-slider-handle"
                :style="getHandleStyle(0)"
                tabindex="0"
                role="slider"
                :aria-valuenow="internalValue[0]"
                :aria-valuemin="min"
                :aria-valuemax="max"
                :aria-disabled="disabled"
                @mousedown="handleMouseDown($event, 0)"
                @mouseenter="handleHandleMouseEnter(0)"
                @mouseleave="handleHandleMouseLeave(0)"
                @keydown="handleKeyDown($event, 0)"
            >
                <Tooltip
                    v-if="tooltip !== false && tipFormatter !== null"
                    ref="tooltipRef0"
                    :open="shouldShowTooltip(0)"
                    :title="formatTooltip(internalValue[0])"
                    :placement="vertical ? 'right' : 'top'"
                    trigger="manual"
                    dark
                >
                    <div class="vort-slider-handle-inner" />
                </Tooltip>
                <div v-else class="vort-slider-handle-inner" />
            </div>

            <!-- 手柄 2（单值模式的唯一手柄，或范围模式的结束手柄） -->
            <div
                class="vort-slider-handle"
                :style="getHandleStyle(1)"
                tabindex="0"
                role="slider"
                :aria-valuenow="internalValue[1]"
                :aria-valuemin="min"
                :aria-valuemax="max"
                :aria-disabled="disabled"
                @mousedown="handleMouseDown($event, 1)"
                @mouseenter="handleHandleMouseEnter(1)"
                @mouseleave="handleHandleMouseLeave(1)"
                @keydown="handleKeyDown($event, 1)"
            >
                <Tooltip
                    v-if="tooltip !== false && tipFormatter !== null"
                    ref="tooltipRef1"
                    :open="shouldShowTooltip(1)"
                    :title="formatTooltip(internalValue[1])"
                    :placement="vertical ? 'right' : 'top'"
                    trigger="manual"
                    dark
                >
                    <div class="vort-slider-handle-inner" />
                </Tooltip>
                <div v-else class="vort-slider-handle-inner" />
            </div>
        </div>

        <!-- 刻度标记 -->
        <div v-if="marks && parsedMarks.length > 0" class="vort-slider-marks">
            <span
                v-for="mark in parsedMarks"
                :key="mark.value"
                class="vort-slider-mark"
                :class="{ 'vort-slider-mark-active': isDotActive(mark.value) }"
                :style="dotStyle(mark.value)"
            >
                <span class="vort-slider-mark-text">{{ mark.label }}</span>
            </span>
        </div>
    </div>
</template>

<style scoped>
/* 容器 */
.vort-slider {
    position: relative;
    display: block;
    padding: 4px 0;
    cursor: pointer;
    touch-action: none;
    user-select: none;
}

.vort-slider-vertical {
    width: 12px;
    height: 100%;
    min-height: 100px;
    padding: 0 4px;
    display: inline-block;
}

.vort-slider-disabled {
    cursor: not-allowed;
}

/* 轨道容器 */
.vort-slider-rail {
    position: relative;
    width: 100%;
    height: 4px;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 2px;
    transition: background-color 0.2s;
    user-select: none;
}

.vort-slider-vertical .vort-slider-rail {
    width: 4px;
    height: 100%;
}

.vort-slider:hover .vort-slider-rail {
    background: rgba(0, 0, 0, 0.06);
}

.vort-slider-disabled .vort-slider-rail {
    background: rgba(0, 0, 0, 0.04) !important;
}

/* 已填充轨道 */
.vort-slider-track {
    position: absolute;
    z-index: 1;
    height: 4px;
    background: var(--vort-primary);
    border-radius: 2px;
    transition: background-color 0.2s;
}

.vort-slider-vertical .vort-slider-track {
    width: 4px;
    height: auto;
}

.vort-slider:hover .vort-slider-track {
    background: var(--vort-primary-hover);
}

.vort-slider-disabled .vort-slider-track {
    background: rgba(0, 0, 0, 0.25) !important;
}

/* 手柄 */
.vort-slider-handle {
    position: absolute;
    z-index: 2;
    width: 14px;
    height: 14px;
    outline: none;
    cursor: pointer;
    user-select: none;
}

/* 水平模式定位 */
.vort-slider:not(.vort-slider-vertical) .vort-slider-handle {
    top: 0;
    margin-top: -5px;
    margin-left: -7px;
}

/* 垂直模式定位 */
.vort-slider-vertical .vort-slider-handle {
    left: 0;
    margin-bottom: -7px;
    margin-left: -5px;
}

.vort-slider-handle :deep(.vort-tooltip-trigger) {
    display: block;
    width: 100%;
    height: 100%;
    pointer-events: none;
}

.vort-slider-handle-inner {
    width: 14px;
    height: 14px;
    background: #fff;
    border: 2px solid var(--vort-primary);
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12);
    transition: all 0.2s;
    pointer-events: auto;
}

.vort-slider-handle:hover .vort-slider-handle-inner {
    border-color: var(--vort-primary-hover);
    transform: scale(1.2);
}

.vort-slider-handle:focus .vort-slider-handle-inner {
    border-color: var(--vort-primary);
    box-shadow: 0 0 0 4px var(--vort-primary-shadow);
}

.vort-slider-disabled .vort-slider-handle {
    cursor: not-allowed;
}

.vort-slider-disabled .vort-slider-handle-inner {
    border-color: #d9d9d9;
    background: #fff;
    box-shadow: none;
}

.vort-slider-disabled .vort-slider-handle:hover .vort-slider-handle-inner {
    transform: none;
}

/* 步长点 */
.vort-slider-dot {
    position: absolute;
    z-index: 3;
    width: 8px;
    height: 8px;
    margin-top: -2px;
    margin-left: -4px;
    background: #fff;
    border: 2px solid rgba(0, 0, 0, 0.06);
    border-radius: 50%;
    cursor: pointer;
}

.vort-slider-vertical .vort-slider-dot {
    margin-top: -4px;
    margin-left: -2px;
}

.vort-slider-dot-active {
    border-color: var(--vort-primary);
}

.vort-slider-disabled .vort-slider-dot {
    cursor: not-allowed;
}

/* 刻度标记 */
.vort-slider-marks {
    position: absolute;
    top: 18px;
    left: 0;
    width: 100%;
}

.vort-slider-vertical .vort-slider-marks {
    top: 0;
    left: 18px;
    width: auto;
    height: 100%;
}

.vort-slider-mark {
    position: absolute;
    cursor: pointer;
}

.vort-slider-mark-text {
    position: absolute;
    display: inline-block;
    font-size: 14px;
    color: rgba(0, 0, 0, 0.45);
    line-height: 1;
    white-space: nowrap;
    text-align: center;
    transform: translateX(-50%);
    cursor: pointer;
    user-select: none;
}

.vort-slider-vertical .vort-slider-mark-text {
    transform: translateY(-50%);
    margin-left: 4px;
}

.vort-slider-mark-active .vort-slider-mark-text {
    color: rgba(0, 0, 0, 0.88);
}

.vort-slider-disabled .vort-slider-mark-text {
    color: rgba(0, 0, 0, 0.25);
    cursor: not-allowed;
}

/* 带标记的滑块需要更多底部空间 */
.vort-slider-with-marks {
    margin-bottom: 28px;
}

.vort-slider-vertical.vort-slider-with-marks {
    margin-bottom: 0;
    margin-right: 28px;
}
</style>
