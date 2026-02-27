<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted, useAttrs } from "vue";
import { ClockCircleOutlined, CloseCircleFilled } from "@/components/vort/icons";
import { Button as VortButton } from "@/components/vort/button";
import { getVortPopupContainer, useZIndex } from "@/components/vort/composables";

defineOptions({ name: "VortTimePicker", inheritAttrs: false });

// 多根节点（包含 Teleport）时，外部属性不会自动继承到根节点，需要手动透传
const attrs = useAttrs();

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popup");

/** Vort TimePicker - 时间选择器组件 */

type TimePickerSize = "large" | "middle" | "small";
type TimePickerStatus = "error" | "warning";

interface Props {
    /** 选中的时间 (v-model) */
    modelValue?: Date | string | null;
    /** 默认选中的时间 */
    defaultValue?: Date | string;
    /** 选择器大小 */
    size?: TimePickerSize;
    /** 是否禁用 */
    disabled?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 时间格式化字符串（显示格式） */
    format?: string;
    /** 绑定值的格式，不指定则返回 Date 对象 */
    valueFormat?: string;
    /** 是否显示清除按钮 */
    allowClear?: boolean;
    /** 不可选择的小时 */
    disabledHours?: () => number[];
    /** 不可选择的分钟 */
    disabledMinutes?: (selectedHour: number) => number[];
    /** 不可选择的秒 */
    disabledSeconds?: (selectedHour: number, selectedMinute: number) => number[];
    /** 校验状态 */
    status?: TimePickerStatus;
    /** 控制弹层显示 */
    open?: boolean;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 自定义类名 */
    class?: string;
    /** 是否使用 12 小时制 */
    use12Hours?: boolean;
    /** 小时选项间隔 */
    hourStep?: number;
    /** 分钟选项间隔 */
    minuteStep?: number;
    /** 秒数选项间隔 */
    secondStep?: number;
    /** 是否显示秒选择 */
    showSecond?: boolean;
    /** 是否显示此刻按钮 */
    showNow?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    size: "middle",
    disabled: false,
    placeholder: "请选择时间",
    format: "HH:mm:ss",
    allowClear: true,
    use12Hours: false,
    hourStep: 1,
    minuteStep: 1,
    secondStep: 1,
    showSecond: true,
    showNow: true
});

const emit = defineEmits<{
    "update:modelValue": [value: Date | string | null];
    "update:open": [value: boolean];
    change: [value: Date | string | null, timeString: string];
    openChange: [open: boolean];
}>();

// ============ 状态 ============
const isOpen = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const isHovered = ref(false);
const isFocused = ref(false);
const triggerRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const position = ref({ top: 0, left: 0 });
const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

// 当前选中的时间
const selectedHour = ref(0);
const selectedMinute = ref(0);
const selectedSecond = ref(0);
const selectedPeriod = ref<"AM" | "PM">("AM");

// 滚动容器引用
const hourColumnRef = ref<HTMLElement | null>(null);
const minuteColumnRef = ref<HTMLElement | null>(null);
const secondColumnRef = ref<HTMLElement | null>(null);
const periodColumnRef = ref<HTMLElement | null>(null);

// ============ 时间处理 ============
const parseTime = (value: Date | string | null | undefined): Date | null => {
    if (!value) return null;
    if (value instanceof Date) return value;
    // 尝试解析时间字符串
    const timeMatch = String(value).match(/(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?(?:\s*(AM|PM))?/i);
    if (timeMatch) {
        const date = new Date();
        // noUncheckedIndexedAccess 下 timeMatch[n] 可能为 undefined，需要兜底
        let hours = parseInt(timeMatch[1] ?? "0", 10);
        const minutes = parseInt(timeMatch[2] ?? "0", 10);
        const seconds = timeMatch[3] ? parseInt(timeMatch[3], 10) : 0;
        const period = timeMatch[4]?.toUpperCase();

        if (period === "PM" && hours < 12) hours += 12;
        if (period === "AM" && hours === 12) hours = 0;

        date.setHours(hours, minutes, seconds, 0);
        return date;
    }
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
};

const selectedTime = computed(() => parseTime(props.modelValue));

// 格式化时间
const formatTime = (date: Date | null, fmt: string = props.format): string => {
    if (!date) return "";

    let hours = date.getHours();
    const minutes = date.getMinutes();
    const seconds = date.getSeconds();

    let period = "";
    if (props.use12Hours) {
        period = hours >= 12 ? "PM" : "AM";
        hours = hours % 12 || 12;
    }

    return fmt
        .replace(/HH/g, String(hours).padStart(2, "0"))
        .replace(/H/g, String(hours))
        .replace(/hh/g, String(hours).padStart(2, "0"))
        .replace(/h/g, String(hours))
        .replace(/mm/g, String(minutes).padStart(2, "0"))
        .replace(/m/g, String(minutes))
        .replace(/ss/g, String(seconds).padStart(2, "0"))
        .replace(/s/g, String(seconds))
        .replace(/A/g, period)
        .replace(/a/g, period.toLowerCase());
};

// 显示的文本
const displayText = computed(() => {
    if (!selectedTime.value) return "";
    return formatTime(selectedTime.value);
});

// ============ 样式类 ============
const triggerClasses = computed(() => {
    const classes = ["vort-timepicker-trigger"];
    // 尺寸
    classes.push(`vort-timepicker-trigger-${props.size}`);
    // 状态
    if (props.status) classes.push(`vort-timepicker-trigger-${props.status}`);
    // focus / open
    if (isFocused.value || isOpen.value) classes.push("vort-timepicker-trigger-focused");
    // 禁用
    if (props.disabled) classes.push("vort-timepicker-trigger-disabled");
    // 自定义
    if (props.class) classes.push(props.class);
    return classes;
});

// 图标尺寸
const iconSizeClass = computed(() => {
    const sizes = {
        large: "vort-timepicker-icon-large",
        middle: "vort-timepicker-icon-middle",
        small: "vort-timepicker-icon-small"
    };
    return sizes[props.size];
});

// 是否显示清除按钮
const showClearButton = computed(() => {
    return props.allowClear && !props.disabled && selectedTime.value && isHovered.value;
});

// ============ 面板定位 ============
const updatePosition = async () => {
    await nextTick();
    if (!triggerRef.value || !panelRef.value) return;

    const triggerRect = triggerRef.value.getBoundingClientRect();
    const panelHeight = panelRef.value.offsetHeight;
    const panelWidth = panelRef.value.offsetWidth;
    const container = popupContainer.value;
    const useCustomContainer = container && container !== document.body;
    const scrollTop = useCustomContainer ? container.scrollTop : window.scrollY;
    const scrollLeft = useCustomContainer ? container.scrollLeft : window.scrollX;
    const containerRect = useCustomContainer ? container.getBoundingClientRect() : null;
    const gap = 4;

    let top = 0;
    let left = 0;

    if (useCustomContainer && containerRect) {
        const offsetTop = triggerRect.top - containerRect.top + scrollTop;
        const offsetLeft = triggerRect.left - containerRect.left + scrollLeft;
        top = offsetTop + triggerRect.height + gap;
        left = offsetLeft;
    } else {
        top = triggerRect.bottom + scrollTop + gap;
        left = triggerRect.left + scrollLeft;
    }

    // 边界检测 - 下方空间不足时向上弹出
    if (useCustomContainer && containerRect) {
        const containerHeight = container.clientHeight;
        const offsetTop = triggerRect.top - containerRect.top + scrollTop;
        const spaceBelow = containerHeight - (offsetTop + triggerRect.height);
        const spaceAbove = offsetTop;
        if (spaceBelow < panelHeight + gap && spaceAbove > spaceBelow) {
            top = offsetTop - panelHeight - gap;
        }
    } else {
        const viewportHeight = window.innerHeight;
        if (triggerRect.bottom + panelHeight + gap > viewportHeight && triggerRect.top > panelHeight + gap) {
            top = triggerRect.top + scrollTop - panelHeight - gap;
        }
    }

    // 右侧边界检测
    if (useCustomContainer && containerRect) {
        const containerWidth = container.clientWidth;
        if (left + panelWidth > scrollLeft + containerWidth - 8) {
            left = scrollLeft + containerWidth - panelWidth - 8;
        }
        if (left < scrollLeft + 8) left = scrollLeft + 8;
    } else {
        const viewportWidth = window.innerWidth;
        if (left + panelWidth > viewportWidth - 8) {
            left = viewportWidth - panelWidth - 8;
        }
        if (left < 8) left = 8;
    }

    position.value = { top, left };
};

// ============ 时间列表数据 ============
const hours = computed(() => {
    const result: number[] = [];
    const max = props.use12Hours ? 12 : 24;
    const start = props.use12Hours ? 1 : 0;
    const disabledHoursList = props.disabledHours?.() || [];

    for (let i = start; i < (props.use12Hours ? max + 1 : max); i += props.hourStep) {
        if (!disabledHoursList.includes(i)) {
            result.push(i);
        }
    }
    return result;
});

const minutes = computed(() => {
    const result: number[] = [];
    const disabledMinutesList = props.disabledMinutes?.(selectedHour.value) || [];

    for (let i = 0; i < 60; i += props.minuteStep) {
        if (!disabledMinutesList.includes(i)) {
            result.push(i);
        }
    }
    return result;
});

const seconds = computed(() => {
    const result: number[] = [];
    const disabledSecondsList = props.disabledSeconds?.(selectedHour.value, selectedMinute.value) || [];

    for (let i = 0; i < 60; i += props.secondStep) {
        if (!disabledSecondsList.includes(i)) {
            result.push(i);
        }
    }
    return result;
});

// ============ 面板控制 ============
const openPanel = () => {
    if (props.disabled) return;
    shouldRenderTeleport.value = true; // 先渲染 Teleport
    isOpen.value = true;
    emit("update:open", true);
    emit("openChange", true);

    // 初始化选中的时间
    if (selectedTime.value) {
        let h = selectedTime.value.getHours();
        if (props.use12Hours) {
            selectedPeriod.value = h >= 12 ? "PM" : "AM";
            h = h % 12 || 12;
        }
        selectedHour.value = h;
        selectedMinute.value = selectedTime.value.getMinutes();
        selectedSecond.value = selectedTime.value.getSeconds();
    } else {
        // 未选时间时定位在0时0分0秒
        if (props.use12Hours) {
            selectedPeriod.value = "AM";
            selectedHour.value = 12; // 12小时制的0点是12 AM
        } else {
            selectedHour.value = 0;
        }
        selectedMinute.value = 0;
        selectedSecond.value = 0;
    }

    nextTick(() => {
        updatePosition();
        scrollToSelected();
    });
};

const closePanel = () => {
    isOpen.value = false;
    emit("update:open", false);
    emit("openChange", false);
};

// Transition 离开动画完成后移除 Teleport
const handleAfterLeave = () => {
    shouldRenderTeleport.value = false;
};

const togglePanel = () => {
    if (isOpen.value) {
        closePanel();
    } else {
        openPanel();
    }
};

// 同步外部 open 状态
watch(
    () => props.open,
    (val) => {
        if (val !== undefined && val !== isOpen.value) {
            if (val) {
                openPanel();
            } else {
                closePanel();
            }
        }
    }
);

// ============ 平滑滚动函数 ============
const smoothScrollTo = (element: HTMLElement, targetScrollTop: number, duration: number = 200) => {
    const startScrollTop = element.scrollTop;
    const distance = targetScrollTop - startScrollTop;
    const startTime = performance.now();

    const easeOutCubic = (t: number): number => {
        return 1 - Math.pow(1 - t, 3);
    };

    const animateScroll = (currentTime: number) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easedProgress = easeOutCubic(progress);

        element.scrollTop = startScrollTop + distance * easedProgress;

        if (progress < 1) {
            requestAnimationFrame(animateScroll);
        }
    };

    requestAnimationFrame(animateScroll);
};

// ============ 滚动到选中项 ============
const scrollToSelected = async (smooth: boolean = false) => {
    await nextTick();
    const itemHeight = 28;

    const scrollToPosition = (element: HTMLElement | null, index: number) => {
        if (!element || index < 0) return;
        const targetScrollTop = index * itemHeight;
        if (smooth) {
            smoothScrollTo(element, targetScrollTop, 200);
        } else {
            element.scrollTop = targetScrollTop;
        }
    };

    const hourIndex = hours.value.indexOf(selectedHour.value);
    scrollToPosition(hourColumnRef.value, hourIndex);

    const minuteIndex = minutes.value.indexOf(selectedMinute.value);
    scrollToPosition(minuteColumnRef.value, minuteIndex);

    const secondIndex = seconds.value.indexOf(selectedSecond.value);
    scrollToPosition(secondColumnRef.value, secondIndex);

    const periodIndex = selectedPeriod.value === "AM" ? 0 : 1;
    scrollToPosition(periodColumnRef.value, periodIndex);
};

// ============ 选择处理 ============
const selectHour = (hour: number) => {
    selectedHour.value = hour;
    updateTime();
    // 平滑滚动到选中的小时
    nextTick(() => {
        const itemHeight = 28;
        const hourIndex = hours.value.indexOf(hour);
        if (hourColumnRef.value && hourIndex >= 0) {
            smoothScrollTo(hourColumnRef.value, hourIndex * itemHeight, 200);
        }
    });
};

const selectMinute = (minute: number) => {
    selectedMinute.value = minute;
    updateTime();
    // 平滑滚动到选中的分钟
    nextTick(() => {
        const itemHeight = 28;
        const minuteIndex = minutes.value.indexOf(minute);
        if (minuteColumnRef.value && minuteIndex >= 0) {
            smoothScrollTo(minuteColumnRef.value, minuteIndex * itemHeight, 200);
        }
    });
};

const selectSecond = (second: number) => {
    selectedSecond.value = second;
    updateTime();
    // 平滑滚动到选中的秒
    nextTick(() => {
        const itemHeight = 28;
        const secondIndex = seconds.value.indexOf(second);
        if (secondColumnRef.value && secondIndex >= 0) {
            smoothScrollTo(secondColumnRef.value, secondIndex * itemHeight, 200);
        }
    });
};

const selectPeriod = (period: "AM" | "PM") => {
    selectedPeriod.value = period;
    updateTime();
    // 平滑滚动到选中的时段
    nextTick(() => {
        const itemHeight = 28;
        const periodIndex = period === "AM" ? 0 : 1;
        if (periodColumnRef.value) {
            smoothScrollTo(periodColumnRef.value, periodIndex * itemHeight, 200);
        }
    });
};

const updateTime = () => {
    const date = new Date();
    let hours = selectedHour.value;

    if (props.use12Hours) {
        if (selectedPeriod.value === "PM" && hours < 12) {
            hours += 12;
        } else if (selectedPeriod.value === "AM" && hours === 12) {
            hours = 0;
        }
    }

    date.setHours(hours, selectedMinute.value, props.showSecond ? selectedSecond.value : 0, 0);

    const timeString = formatTime(date);
    // 如果指定了 valueFormat，返回格式化后的字符串；否则返回 Date 对象
    const value = props.valueFormat ? formatTime(date, props.valueFormat) : date;

    emit("update:modelValue", value);
    emit("change", value, timeString);
};

const selectNow = () => {
    const now = new Date();
    let h = now.getHours();

    if (props.use12Hours) {
        selectedPeriod.value = h >= 12 ? "PM" : "AM";
        h = h % 12 || 12;
    }

    selectedHour.value = h;
    selectedMinute.value = now.getMinutes();
    selectedSecond.value = now.getSeconds();

    updateTime();
    closePanel();
};

const confirmSelection = () => {
    updateTime();
    closePanel();
};

// ============ 清除 ============
const handleClear = (e: Event) => {
    e.stopPropagation();
    // 如果指定了 valueFormat，清除时返回空字符串；否则返回 null
    const value = props.valueFormat ? "" : null;
    emit("update:modelValue", value);
    emit("change", value, "");
};

// ============ 点击外部关闭 ============
const handleClickOutside = (e: MouseEvent) => {
    if (!isOpen.value) return;
    const target = e.target as Node;
    if (triggerRef.value?.contains(target) || panelRef.value?.contains(target)) {
        return;
    }
    closePanel();
};

// ============ 生命周期 ============
onMounted(() => {
    document.addEventListener("mousedown", handleClickOutside);
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
});

onUnmounted(() => {
    document.removeEventListener("mousedown", handleClickOutside);
    window.removeEventListener("scroll", updatePosition, true);
    window.removeEventListener("resize", updatePosition);
});

// 面板样式
const panelStyle = computed(() => ({
    top: `${position.value.top}px`,
    left: `${position.value.left}px`,
    zIndex: zIndex.value
}));

// transform-origin 计算
const transformOrigin = computed(() => {
    if (!triggerRef.value || !panelRef.value) return "center top";
    const triggerRect = triggerRef.value.getBoundingClientRect();
    const container = popupContainer.value;
    const useCustomContainer = container && container !== document.body;
    const containerRect = useCustomContainer ? container.getBoundingClientRect() : null;
    const panelTop = useCustomContainer && containerRect ? position.value.top - container.scrollTop + containerRect.top : position.value.top - window.scrollY;
    if (panelTop < triggerRect.top) {
        return "center bottom";
    }
    return "center top";
});

// 判断是否被禁用
const isHourDisabled = (hour: number): boolean => {
    return props.disabledHours?.().includes(hour) ?? false;
};

const isMinuteDisabled = (minute: number): boolean => {
    return props.disabledMinutes?.(selectedHour.value).includes(minute) ?? false;
};

const isSecondDisabled = (second: number): boolean => {
    return props.disabledSeconds?.(selectedHour.value, selectedMinute.value).includes(second) ?? false;
};

// 暴露方法
defineExpose({
    focus: () => triggerRef.value?.focus(),
    blur: () => triggerRef.value?.blur()
});
</script>

<template>
    <div
        ref="triggerRef"
        v-bind="attrs"
        :class="triggerClasses"
        tabindex="0"
        @click="togglePanel"
        @mouseenter="isHovered = true"
        @mouseleave="isHovered = false"
        @focus="isFocused = true"
        @blur="isFocused = false"
    >
        <!-- 时钟图标 -->
        <span class="vort-timepicker-prefix-icon">
            <ClockCircleOutlined />
        </span>

        <!-- 显示内容 -->
        <span class="vort-timepicker-display" :class="displayText ? 'vort-timepicker-display-filled' : 'vort-timepicker-display-placeholder'">
            {{ displayText || placeholder }}
        </span>

        <!-- 后缀图标 -->
        <span class="vort-timepicker-suffix">
            <!-- 清除按钮 -->
            <span v-if="showClearButton" class="vort-timepicker-clear" @click="handleClear" @mousedown.prevent>
                <CloseCircleFilled :class="iconSizeClass" />
            </span>
        </span>
    </div>

    <!-- 时间面板 -->
    <Teleport v-if="shouldRenderTeleport" :to="popupContainer">
        <Transition name="vort-timepicker" appear @after-leave="handleAfterLeave">
            <div v-if="isOpen" ref="panelRef" class="vort-timepicker-panel" :style="{ ...panelStyle, '--transform-origin': transformOrigin }">
                <!-- 时间选择区域 -->
                <div class="vort-timepicker-content">
                    <!-- 小时列 -->
                    <div ref="hourColumnRef" class="vort-timepicker-column">
                        <ul class="vort-timepicker-column-inner">
                            <li
                                v-for="hour in hours"
                                :key="hour"
                                :class="[
                                    'vort-timepicker-cell',
                                    selectedHour === hour && 'vort-timepicker-cell-selected',
                                    isHourDisabled(hour) && 'vort-timepicker-cell-disabled'
                                ]"
                                @click="!isHourDisabled(hour) && selectHour(hour)"
                            >
                                {{ String(hour).padStart(2, "0") }}
                            </li>
                        </ul>
                    </div>

                    <!-- 分钟列 -->
                    <div ref="minuteColumnRef" class="vort-timepicker-column">
                        <ul class="vort-timepicker-column-inner">
                            <li
                                v-for="minute in minutes"
                                :key="minute"
                                :class="[
                                    'vort-timepicker-cell',
                                    selectedMinute === minute && 'vort-timepicker-cell-selected',
                                    isMinuteDisabled(minute) && 'vort-timepicker-cell-disabled'
                                ]"
                                @click="!isMinuteDisabled(minute) && selectMinute(minute)"
                            >
                                {{ String(minute).padStart(2, "0") }}
                            </li>
                        </ul>
                    </div>

                    <!-- 秒列 -->
                    <div v-if="showSecond" ref="secondColumnRef" class="vort-timepicker-column">
                        <ul class="vort-timepicker-column-inner">
                            <li
                                v-for="second in seconds"
                                :key="second"
                                :class="[
                                    'vort-timepicker-cell',
                                    selectedSecond === second && 'vort-timepicker-cell-selected',
                                    isSecondDisabled(second) && 'vort-timepicker-cell-disabled'
                                ]"
                                @click="!isSecondDisabled(second) && selectSecond(second)"
                            >
                                {{ String(second).padStart(2, "0") }}
                            </li>
                        </ul>
                    </div>

                    <!-- AM/PM 列（12小时制） -->
                    <div v-if="use12Hours" ref="periodColumnRef" class="vort-timepicker-column">
                        <ul class="vort-timepicker-column-inner">
                            <li :class="['vort-timepicker-cell', selectedPeriod === 'AM' && 'vort-timepicker-cell-selected']" @click="selectPeriod('AM')">
                                AM
                            </li>
                            <li :class="['vort-timepicker-cell', selectedPeriod === 'PM' && 'vort-timepicker-cell-selected']" @click="selectPeriod('PM')">
                                PM
                            </li>
                        </ul>
                    </div>
                </div>

                <!-- 底部操作区 -->
                <div class="vort-timepicker-footer">
                    <VortButton v-if="showNow" variant="text" size="small" @click="selectNow"> 此刻 </VortButton>
                    <VortButton variant="primary" size="small" @click="confirmSelection"> 确定 </VortButton>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
/* ============ 触发器样式 ============ */
.vort-timepicker-trigger {
    position: relative;
    display: inline-flex;
    align-items: center;
    width: 100%;
    background: #fff;
    border: 1px solid var(--vort-border);
    border-radius: var(--vort-border-radius, 6px);
    transition: all var(--vort-duration-normal, 200ms);
    cursor: pointer;
}

.vort-timepicker-trigger:not(.vort-timepicker-trigger-disabled):hover {
    border-color: var(--vort-primary-hover);
}

.vort-timepicker-trigger-focused {
    border-color: var(--vort-primary) !important;
    box-shadow: 0 0 0 2px var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
}

/* 尺寸 */
.vort-timepicker-trigger-large {
    height: 40px;
    padding: 0 11px;
    font-size: 16px;
}

.vort-timepicker-trigger-middle {
    height: 32px;
    padding: 0 11px;
    font-size: 14px;
}

.vort-timepicker-trigger-small {
    height: 24px;
    padding: 0 7px;
    font-size: 14px;
}

/* 状态 */
.vort-timepicker-trigger-error {
    border-color: var(--vort-error) !important;
}

.vort-timepicker-trigger-error:hover {
    border-color: var(--vort-error) !important;
}

.vort-timepicker-trigger-warning {
    border-color: var(--vort-warning) !important;
}

.vort-timepicker-trigger-warning:hover {
    border-color: var(--vort-warning) !important;
}

/* 禁用 */
.vort-timepicker-trigger-disabled {
    background: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary);
    cursor: not-allowed;
}

/* 前缀图标 */
.vort-timepicker-prefix-icon {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-right: 8px;
    color: var(--vort-text-quaternary);
}

/* 显示内容 */
.vort-timepicker-display {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.vort-timepicker-display-filled {
    color: var(--vort-text);
}

.vort-timepicker-display-placeholder {
    color: var(--vort-text-quaternary);
}

/* 后缀 */
.vort-timepicker-suffix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-left: 4px;
}

/* 清除按钮 */
.vort-timepicker-clear {
    display: flex;
    align-items: center;
    cursor: pointer;
    color: var(--vort-text-quaternary);
    transition: color var(--vort-duration-fast, 100ms);
}

.vort-timepicker-clear:hover {
    color: var(--vort-text-tertiary);
}

/* 图标尺寸 */
.vort-timepicker-icon-large {
    font-size: 16px;
}

.vort-timepicker-icon-middle {
    font-size: 14px;
}

.vort-timepicker-icon-small {
    font-size: 12px;
}

/* ============ 面板样式 ============ */
.vort-timepicker-panel {
    position: absolute;
    background: #fff;
    border-radius: var(--vort-border-radius-lg, var(--vort-border-radius, 8px));
    pointer-events: auto;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    overflow: hidden;
}

/* 动画 */
.vort-timepicker-enter-active {
    animation: vortTimepickerIn 0.2s cubic-bezier(0.08, 0.82, 0.17, 1);
    transform-origin: var(--transform-origin, center top);
}

.vort-timepicker-leave-active {
    animation: vortTimepickerOut 0.15s cubic-bezier(0.78, 0.14, 0.15, 0.86);
    transform-origin: var(--transform-origin, center top);
}

@keyframes vortTimepickerIn {
    0% {
        opacity: 0;
        transform: scaleY(0.8);
    }
    100% {
        opacity: 1;
        transform: scaleY(1);
    }
}

@keyframes vortTimepickerOut {
    0% {
        opacity: 1;
        transform: scaleY(1);
    }
    100% {
        opacity: 0;
        transform: scaleY(0.8);
    }
}

/* 内容区 */
.vort-timepicker-content {
    display: flex;
    max-height: 224px;
    border-bottom: 1px solid var(--vort-border-secondary);
}

/* 时间列 */
.vort-timepicker-column {
    flex: 1;
    width: 56px;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.15) transparent;
}

.vort-timepicker-column:not(:last-child) {
    border-right: 1px solid var(--vort-border-secondary);
}

.vort-timepicker-column::-webkit-scrollbar {
    width: 4px;
}

.vort-timepicker-column::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.15);
    border-radius: var(--vort-border-radius-sm, 2px);
}

.vort-timepicker-column::-webkit-scrollbar-track {
    background: transparent;
}

.vort-timepicker-column-inner {
    list-style: none;
    margin: 0;
    padding: 4px 0;
}

/* 时间单元格 */
.vort-timepicker-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 28px;
    margin: 0 4px;
    padding: 0 8px;
    font-size: 14px;
    color: var(--vort-text);
    cursor: pointer;
    border-radius: var(--vort-border-radius-sm, 2px);
    transition: all 0.15s;
}

.vort-timepicker-cell:hover:not(.vort-timepicker-cell-disabled):not(.vort-timepicker-cell-selected) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-timepicker-cell-selected {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
    font-weight: 500;
}

.vort-timepicker-cell-disabled {
    color: var(--vort-text-quaternary);
    cursor: not-allowed;
}

/* 底部 */
.vort-timepicker-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
}
</style>
