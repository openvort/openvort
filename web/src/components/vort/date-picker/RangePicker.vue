<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted, useAttrs } from "vue";
import { CalendarOutlined, CloseCircleFilled } from "@/components/vort/icons";
import { Button as VortButton } from "@/components/vort/button";
import { getVortPopupContainer, useZIndex } from "@/components/vort/composables";
import { useLocale } from "@/components/vort/locale/useLocale";

defineOptions({ name: "VortRangePicker", inheritAttrs: false });

const { componentLocale: dpLocale, t: dpT } = useLocale("DatePicker");

// 多根节点（包含 Teleport）时，外部属性不会自动继承到根节点，需要手动透传
const attrs = useAttrs();

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popup");

/** Vort RangePicker - 日期范围选择器组件 */

type DatePickerSize = "large" | "middle" | "small";
type DatePickerStatus = "error" | "warning";
type PickerMode = "date" | "month" | "year";

// 范围值类型
type RangeValue = [Date | null, Date | null] | null;

type PresetValue = Date | string | number | null | undefined | { toDate?: () => Date } | { $d?: Date };

interface RangePresetItem {
    /** 预设文案 */
    label: string;
    /** 预设值（支持函数返回，便于动态计算“最近7天”等） */
    value: [PresetValue, PresetValue] | (() => [PresetValue, PresetValue]);
}

/** showTime 配置选项 */
interface ShowTimeOptions {
    /** 小时选项间隔 */
    hourStep?: number;
    /** 分钟选项间隔 */
    minuteStep?: number;
    /** 秒数选项间隔 */
    secondStep?: number;
    /** 是否显示秒选择 */
    showSecond?: boolean;
    /** 默认时间 */
    defaultValue?: [Date | string, Date | string] | Date | string;
}

interface Props {
    /** 选中的日期范围 (v-model) */
    modelValue?: RangeValue;
    /** 默认选中的日期范围 */
    defaultValue?: RangeValue;
    /** 选择器大小 */
    size?: DatePickerSize;
    /** 是否禁用 */
    disabled?: boolean;
    /** 输入框占位文本 [开始, 结束] */
    placeholder?: [string, string];
    /** 日期格式化字符串 */
    format?: string;
    /** 是否显示清除按钮 */
    allowClear?: boolean;
    /** 不可选择的日期 */
    disabledDate?: (currentDate: Date) => boolean;
    /** 校验状态 */
    status?: DatePickerStatus;
    /** 控制弹层显示 */
    open?: boolean;
    /** 菜单渲染父节点。默认渲染到 body 上，如果你遇到菜单滚动定位问题，试试修改为滚动的区域，并相对其定位 */
    getPopupContainer?: () => HTMLElement;
    /** 自定义类名 */
    class?: string;
    /** 分隔符 */
    separator?: string;
    /** 设置选择器类型 */
    picker?: PickerMode;
    /** 是否增加时间选择功能 */
    showTime?: boolean | ShowTimeOptions;
    /** 不可选择的小时（showTime 时有效） */
    disabledHours?: () => number[];
    /** 不可选择的分钟（showTime 时有效） */
    disabledMinutes?: (selectedHour: number) => number[];
    /** 不可选择的秒（showTime 时有效） */
    disabledSeconds?: (selectedHour: number, selectedMinute: number) => number[];
    /** 是否显示"此刻"按钮（showTime 时有效） */
    showNow?: boolean;
    /** 预设范围（与 Ant Design 一致，显示在弹层左侧，垂直排列） */
    presets?: RangePresetItem[];
}

const props = withDefaults(defineProps<Props>(), {
    size: "middle",
    disabled: false,
    placeholder: undefined,
    format: undefined,
    allowClear: true,
    separator: "~",
    picker: "date",
    showTime: false,
    showNow: true
});

const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

const emit = defineEmits<{
    "update:modelValue": [value: RangeValue];
    "update:open": [value: boolean];
    change: [value: RangeValue, dateStrings: [string, string]];
    openChange: [open: boolean];
    calendarChange: [dates: RangeValue, dateStrings: [string, string], info: { range: "start" | "end" }];
}>();

// ============ 状态 ============
const isOpen = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const isHovered = ref(false);
const isFocused = ref(false);
const triggerRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const position = ref({ top: 0, left: 0 });

// 选择状态: 'start' | 'end'
const selectingType = ref<"start" | "end">("start");

// 当前面板模式（左右面板独立）
const leftPanelMode = ref<PickerMode>(props.picker);
const rightPanelMode = ref<PickerMode>(props.picker);

// 面板显示的年月（用于导航）
const leftPanelYear = ref(new Date().getFullYear());
const leftPanelMonth = ref(new Date().getMonth());
const rightPanelYear = ref(new Date().getFullYear());
const rightPanelMonth = ref(new Date().getMonth() + 1 > 11 ? 0 : new Date().getMonth() + 1);

// 悬停的日期（用于显示范围预览）
const hoveredDate = ref<Date | null>(null);

// ============ showTime 配置解析 ============
const showTimeOptions = computed<ShowTimeOptions | null>(() => {
    if (!props.showTime) return null;
    if (props.showTime === true) {
        return { hourStep: 1, minuteStep: 1, secondStep: 1, showSecond: true };
    }
    return {
        hourStep: props.showTime.hourStep ?? 1,
        minuteStep: props.showTime.minuteStep ?? 1,
        secondStep: props.showTime.secondStep ?? 1,
        showSecond: props.showTime.showSecond ?? true,
        defaultValue: props.showTime.defaultValue
    };
});

// 计算实际的 placeholder
const actualPlaceholder = computed<[string, string]>(() => {
    if (props.placeholder !== undefined) return props.placeholder;
    if (props.showTime) return [dpLocale.value.start_datetime, dpLocale.value.end_datetime];
    return [dpT("start_date"), dpT("end_date")];
});

// 计算实际的 format
const actualFormat = computed(() => {
    if (props.format !== undefined) return props.format;
    if (props.showTime) {
        const showSecond = showTimeOptions.value?.showSecond !== false;
        return showSecond ? "YYYY-MM-DD HH:mm:ss" : "YYYY-MM-DD HH:mm";
    }
    if (props.picker === "year") return "YYYY";
    if (props.picker === "month") return "YYYY-MM";
    return "YYYY-MM-DD";
});

// ============ 时间选择状态 ============
const startHour = ref(0);
const startMinute = ref(0);
const startSecond = ref(0);
const endHour = ref(0);
const endMinute = ref(0);
const endSecond = ref(0);

// 时间选择列滚动容器引用
const startHourColumnRef = ref<HTMLElement | null>(null);
const startMinuteColumnRef = ref<HTMLElement | null>(null);
const startSecondColumnRef = ref<HTMLElement | null>(null);
const endHourColumnRef = ref<HTMLElement | null>(null);
const endMinuteColumnRef = ref<HTMLElement | null>(null);
const endSecondColumnRef = ref<HTMLElement | null>(null);

// ============ 日期处理 ============
const parseDate = (value: unknown): Date | null => {
    if (value === null || value === undefined || value === "") return null;
    if (value instanceof Date) return isNaN(value.getTime()) ? null : value;

    // 兼容 dayjs 等库（toDate / $d）
    if (typeof value === "object") {
        const anyValue = value as any;
        if (typeof anyValue?.toDate === "function") {
            const d = anyValue.toDate();
            return d instanceof Date && !isNaN(d.getTime()) ? d : null;
        }
        if (anyValue?.$d instanceof Date) {
            const d = anyValue.$d as Date;
            return !isNaN(d.getTime()) ? d : null;
        }
    }

    const d = new Date(value as any);
    return isNaN(d.getTime()) ? null : d;
};

// 选中的开始日期
const startDate = computed(() => {
    if (!props.modelValue) return null;
    return parseDate(props.modelValue[0]);
});

// 选中的结束日期
const endDate = computed(() => {
    if (!props.modelValue) return null;
    return parseDate(props.modelValue[1]);
});

const hasPresets = computed(() => props.picker === "date" && Array.isArray(props.presets) && props.presets.length > 0);

const isSameDay = (a: Date, b: Date): boolean => {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
};

const isPresetActive = (preset: RangePresetItem): boolean => {
    if (!startDate.value || !endDate.value) return false;
    const raw = typeof preset.value === "function" ? preset.value() : preset.value;
    const presetStart = parseDate(raw?.[0]);
    const presetEnd = parseDate(raw?.[1]);
    if (!presetStart || !presetEnd) return false;
    if (props.showTime) {
        return startDate.value.getTime() === presetStart.getTime() && endDate.value.getTime() === presetEnd.getTime();
    }
    return isSameDay(startDate.value, presetStart) && isSameDay(endDate.value, presetEnd);
};

const applyPresetRange = (preset: RangePresetItem) => {
    const raw = typeof preset.value === "function" ? preset.value() : preset.value;
    const presetStart = parseDate(raw?.[0]);
    const presetEnd = parseDate(raw?.[1]);
    if (!presetStart || !presetEnd) return;

    let start = new Date(presetStart);
    let end = new Date(presetEnd);
    if (start.getTime() > end.getTime()) {
        const tmp = start;
        start = end;
        end = tmp;
    }

    if (props.showTime) {
        start.setHours(startHour.value, startMinute.value, startSecond.value, 0);
        end.setHours(endHour.value, endMinute.value, endSecond.value, 0);
    } else {
        start.setHours(0, 0, 0, 0);
        end.setHours(0, 0, 0, 0);
    }

    if (props.disabledDate?.(start) || props.disabledDate?.(end)) return;

    const newValue: RangeValue = [start, end];
    hoveredDate.value = null;
    selectingType.value = "end";

    // 同步面板显示的年月（跨度较大时更符合直觉）
    leftPanelYear.value = start.getFullYear();
    leftPanelMonth.value = start.getMonth();
    rightPanelYear.value = end.getFullYear();
    rightPanelMonth.value = end.getMonth();
    ensureRightPanelAfterLeft();

    emit("update:modelValue", newValue);
    emit("calendarChange", newValue, [formatDate(start), formatDate(end)], { range: "end" });

    // showTime 模式下与点击选择保持一致：不自动关闭，需要点击确定
    if (!props.showTime) {
        emit("change", newValue, [formatDate(start), formatDate(end)]);
        closePanel();
    }
};

// 格式化日期（支持时间）
const formatDate = (date: Date | null, fmt: string = actualFormat.value): string => {
    if (!date) return "";

    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const seconds = date.getSeconds();

    return fmt
        .replace(/YYYY/g, String(year))
        .replace(/YY/g, String(year).slice(-2))
        .replace(/MM/g, String(month).padStart(2, "0"))
        .replace(/M/g, String(month))
        .replace(/DD/g, String(day).padStart(2, "0"))
        .replace(/D/g, String(day))
        .replace(/HH/g, String(hours).padStart(2, "0"))
        .replace(/H/g, String(hours))
        .replace(/mm/g, String(minutes).padStart(2, "0"))
        .replace(/m/g, String(minutes))
        .replace(/ss/g, String(seconds).padStart(2, "0"))
        .replace(/s/g, String(seconds));
};

// 显示的开始日期文本
const startDisplayText = computed(() => {
    if (!startDate.value) return "";
    return formatDate(startDate.value, actualFormat.value);
});

// 显示的结束日期文本
const endDisplayText = computed(() => {
    if (!endDate.value) return "";
    return formatDate(endDate.value, actualFormat.value);
});

// ============ 时间列表数据 ============
const hours = computed(() => {
    const result: number[] = [];
    const step = showTimeOptions.value?.hourStep ?? 1;
    const disabledHoursList = props.disabledHours?.() || [];

    for (let i = 0; i < 24; i += step) {
        if (!disabledHoursList.includes(i)) {
            result.push(i);
        }
    }
    return result;
});

const getMinutes = (selectedHour: number) => {
    const result: number[] = [];
    const step = showTimeOptions.value?.minuteStep ?? 1;
    const disabledMinutesList = props.disabledMinutes?.(selectedHour) || [];

    for (let i = 0; i < 60; i += step) {
        if (!disabledMinutesList.includes(i)) {
            result.push(i);
        }
    }
    return result;
};

const getSeconds = (selectedHour: number, selectedMinute: number) => {
    const result: number[] = [];
    const step = showTimeOptions.value?.secondStep ?? 1;
    const disabledSecondsList = props.disabledSeconds?.(selectedHour, selectedMinute) || [];

    for (let i = 0; i < 60; i += step) {
        if (!disabledSecondsList.includes(i)) {
            result.push(i);
        }
    }
    return result;
};

const startMinutes = computed(() => getMinutes(startHour.value));
const startSeconds = computed(() => getSeconds(startHour.value, startMinute.value));
const endMinutes = computed(() => getMinutes(endHour.value));
const endSeconds = computed(() => getSeconds(endHour.value, endMinute.value));

// 判断时间是否被禁用
const isHourDisabled = (hour: number): boolean => {
    return props.disabledHours?.().includes(hour) ?? false;
};

const isMinuteDisabled = (minute: number, selectedHour: number): boolean => {
    return props.disabledMinutes?.(selectedHour).includes(minute) ?? false;
};

const isSecondDisabled = (second: number, selectedHour: number, selectedMinute: number): boolean => {
    return props.disabledSeconds?.(selectedHour, selectedMinute).includes(second) ?? false;
};

// ============ 样式类（简洁的类名切换） ============

/** 触发器类名 */
const triggerClasses = computed(() => {
    const classes = ["vort-rangepicker-selector", `vort-rangepicker-${props.size}`];

    if (props.showTime) classes.push("vort-rangepicker-showtime");
    if (props.status) classes.push(`vort-rangepicker-${props.status}`);
    if (props.disabled) classes.push("vort-rangepicker-disabled");
    if (isFocused.value || isOpen.value) classes.push("vort-rangepicker-focused");
    if (props.class) classes.push(props.class);

    return classes;
});

/** 输入字段类名 */
const getInputClasses = (type: "start" | "end", hasValue: boolean) => {
    const classes = ["vort-rangepicker-input"];

    if (hasValue) {
        classes.push("vort-rangepicker-input-value");
    } else {
        classes.push("vort-rangepicker-input-placeholder");
    }

    if (selectingType.value === type && isOpen.value) {
        classes.push("vort-rangepicker-input-active");
    }

    return classes;
};

// 是否显示清除按钮
const showClearButton = computed(() => {
    return props.allowClear && !props.disabled && (startDate.value || endDate.value) && isHovered.value;
});

// ============ 面板定位 ============
const updatePosition = async () => {
    await nextTick();
    if (!triggerRef.value || !panelRef.value) return;

    const triggerRect = triggerRef.value.getBoundingClientRect();
    const panelHeight = panelRef.value.offsetHeight;
    const panelWidth = panelRef.value.offsetWidth;
    const scrollTop = window.scrollY;
    const scrollLeft = window.scrollX;
    const gap = 4;

    let top = triggerRect.bottom + scrollTop + gap;
    let left = triggerRect.left + scrollLeft;

    // 边界检测 - 下方空间不足时向上弹出
    const viewportHeight = window.innerHeight;
    if (triggerRect.bottom + panelHeight + gap > viewportHeight && triggerRect.top > panelHeight + gap) {
        top = triggerRect.top + scrollTop - panelHeight - gap;
    }

    // 右侧边界检测
    const viewportWidth = window.innerWidth;
    if (left + panelWidth > viewportWidth - 8) {
        left = viewportWidth - panelWidth - 8;
    }

    position.value = { top, left };
};

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

// ============ 滚动到选中的时间 ============
const scrollToSelectedTime = async (smooth: boolean = false) => {
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

    // 开始时间滚动
    const startHourIndex = hours.value.indexOf(startHour.value);
    scrollToPosition(startHourColumnRef.value, startHourIndex);

    const startMinuteIndex = startMinutes.value.indexOf(startMinute.value);
    scrollToPosition(startMinuteColumnRef.value, startMinuteIndex);

    const startSecondIndex = startSeconds.value.indexOf(startSecond.value);
    scrollToPosition(startSecondColumnRef.value, startSecondIndex);

    // 结束时间滚动
    const endHourIndex = hours.value.indexOf(endHour.value);
    scrollToPosition(endHourColumnRef.value, endHourIndex);

    const endMinuteIndex = endMinutes.value.indexOf(endMinute.value);
    scrollToPosition(endMinuteColumnRef.value, endMinuteIndex);

    const endSecondIndex = endSeconds.value.indexOf(endSecond.value);
    scrollToPosition(endSecondColumnRef.value, endSecondIndex);
};

// ============ 面板控制 ============
const initPanelDates = () => {
    const now = new Date();
    if (startDate.value) {
        leftPanelYear.value = startDate.value.getFullYear();
        leftPanelMonth.value = startDate.value.getMonth();
    } else {
        leftPanelYear.value = now.getFullYear();
        leftPanelMonth.value = now.getMonth();
    }

    if (endDate.value) {
        rightPanelYear.value = endDate.value.getFullYear();
        rightPanelMonth.value = endDate.value.getMonth();
    } else {
        // 右侧面板默认显示下个月
        if (leftPanelMonth.value === 11) {
            rightPanelYear.value = leftPanelYear.value + 1;
            rightPanelMonth.value = 0;
        } else {
            rightPanelYear.value = leftPanelYear.value;
            rightPanelMonth.value = leftPanelMonth.value + 1;
        }
    }

    // 确保右侧面板不会和左侧重叠
    ensureRightPanelAfterLeft();
};

const ensureRightPanelAfterLeft = () => {
    const leftTotal = leftPanelYear.value * 12 + leftPanelMonth.value;
    const rightTotal = rightPanelYear.value * 12 + rightPanelMonth.value;
    if (rightTotal <= leftTotal) {
        if (leftPanelMonth.value === 11) {
            rightPanelYear.value = leftPanelYear.value + 1;
            rightPanelMonth.value = 0;
        } else {
            rightPanelYear.value = leftPanelYear.value;
            rightPanelMonth.value = leftPanelMonth.value + 1;
        }
    }
};

const openPanel = () => {
    if (props.disabled) return;
    shouldRenderTeleport.value = true; // 先渲染 Teleport
    isOpen.value = true;
    emit("update:open", true);
    emit("openChange", true);

    // 初始化面板年月
    initPanelDates();

    // 重置面板模式
    leftPanelMode.value = props.picker;
    rightPanelMode.value = props.picker;

    // 初始化时间选择
    if (props.showTime) {
        if (startDate.value) {
            startHour.value = startDate.value.getHours();
            startMinute.value = startDate.value.getMinutes();
            startSecond.value = startDate.value.getSeconds();
        } else {
            // 使用默认时间或者 0
            const defaultTime = showTimeOptions.value?.defaultValue;
            if (defaultTime) {
                const time = Array.isArray(defaultTime) ? parseDate(defaultTime[0]) : parseDate(defaultTime);
                if (time) {
                    startHour.value = time.getHours();
                    startMinute.value = time.getMinutes();
                    startSecond.value = time.getSeconds();
                } else {
                    startHour.value = 0;
                    startMinute.value = 0;
                    startSecond.value = 0;
                }
            } else {
                startHour.value = 0;
                startMinute.value = 0;
                startSecond.value = 0;
            }
        }

        if (endDate.value) {
            endHour.value = endDate.value.getHours();
            endMinute.value = endDate.value.getMinutes();
            endSecond.value = endDate.value.getSeconds();
        } else {
            // 使用默认时间或者 23:59:59
            const defaultTime = showTimeOptions.value?.defaultValue;
            if (defaultTime && Array.isArray(defaultTime)) {
                const time = parseDate(defaultTime[1]);
                if (time) {
                    endHour.value = time.getHours();
                    endMinute.value = time.getMinutes();
                    endSecond.value = time.getSeconds();
                } else {
                    endHour.value = 23;
                    endMinute.value = 59;
                    endSecond.value = 59;
                }
            } else {
                endHour.value = 23;
                endMinute.value = 59;
                endSecond.value = 59;
            }
        }
    }

    // 重置选择状态：
    // - 如果已有完整范围（开始和结束都有），重新开始选择
    // - 如果只有开始日期没有结束日期，继续选择结束日期
    // - 如果没有日期，从开始日期开始选择
    if (startDate.value && endDate.value) {
        selectingType.value = "start";
    } else if (startDate.value && !endDate.value) {
        selectingType.value = "end";
    } else {
        selectingType.value = "start";
    }

    nextTick(() => {
        updatePosition();
        if (props.showTime) {
            scrollToSelectedTime();
        }
    });
};

const closePanel = () => {
    isOpen.value = false;
    hoveredDate.value = null;
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

// ============ 日历数据 ============
// 从周一开始
const weekDays = computed(() => {
    const ws = dpLocale.value.weekdays_short;
    return [...ws.slice(1), ws[0]];
});

// 获取某月的天数
const getDaysInMonth = (year: number, month: number): number => {
    return new Date(year, month + 1, 0).getDate();
};

// 获取某月第一天是星期几（周一为0，周日为6）
const getFirstDayOfMonth = (year: number, month: number): number => {
    const day = new Date(year, month, 1).getDay();
    // 将周日(0)转换为6，其他减1
    return day === 0 ? 6 : day - 1;
};

// 判断日期是否在范围内
const isDateInRange = (date: Date): boolean => {
    if (!startDate.value) return false;

    const dateTime = date.getTime();
    const startTime = new Date(startDate.value).setHours(0, 0, 0, 0);

    // 如果有结束日期，使用结束日期
    if (endDate.value) {
        const endTime = new Date(endDate.value).setHours(0, 0, 0, 0);
        return dateTime > startTime && dateTime < endTime;
    }

    // 如果正在选择结束日期且有悬停日期，使用悬停日期
    if (selectingType.value === "end" && hoveredDate.value) {
        const hoverTime = new Date(hoveredDate.value).setHours(0, 0, 0, 0);
        if (hoverTime > startTime) {
            return dateTime > startTime && dateTime < hoverTime;
        } else if (hoverTime < startTime) {
            return dateTime > hoverTime && dateTime < startTime;
        }
    }

    return false;
};

// 判断日期是否是范围的边界
const isRangeEdge = (date: Date, edge: "start" | "end"): boolean => {
    const dateTime = new Date(date).setHours(0, 0, 0, 0);

    // 已有完整范围时
    if (startDate.value && endDate.value) {
        const startTime = new Date(startDate.value).setHours(0, 0, 0, 0);
        const endTime = new Date(endDate.value).setHours(0, 0, 0, 0);
        if (edge === "start") {
            return dateTime === startTime;
        }
        if (edge === "end") {
            return dateTime === endTime;
        }
    }

    // 悬停时的边界预览（只有开始日期，正在选择结束日期）
    if (selectingType.value === "end" && hoveredDate.value && startDate.value && !endDate.value) {
        const hoverTime = new Date(hoveredDate.value).setHours(0, 0, 0, 0);
        const startTime = new Date(startDate.value).setHours(0, 0, 0, 0);

        if (hoverTime > startTime) {
            // 悬停在开始日期之后：开始日期是 range-start，悬停日期是 range-end
            if (edge === "start") return dateTime === startTime;
            if (edge === "end") return dateTime === hoverTime;
        } else if (hoverTime < startTime) {
            // 悬停在开始日期之前：悬停日期是 range-start，开始日期是 range-end
            if (edge === "start") return dateTime === hoverTime;
            if (edge === "end") return dateTime === startTime;
        }
    }

    return false;
};

// 生成日历网格数据
const generateCalendarDays = (year: number, month: number) => {
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    const prevMonthDays = getDaysInMonth(year, month - 1);

    const days: Array<{
        date: Date;
        isCurrentMonth: boolean;
        isToday: boolean;
        isStartSelected: boolean;
        isEndSelected: boolean;
        isInRange: boolean;
        isRangeStart: boolean;
        isRangeEnd: boolean;
        isDisabled: boolean;
    }> = [];

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // 上月的补充日期
    for (let i = firstDay - 1; i >= 0; i--) {
        const date = new Date(year, month - 1, prevMonthDays - i);
        days.push(createDayData(date, false, today));
    }

    // 当月日期
    for (let i = 1; i <= daysInMonth; i++) {
        const date = new Date(year, month, i);
        days.push(createDayData(date, true, today));
    }

    // 下月的补充日期（补满6行）
    const remainingDays = 42 - days.length;
    for (let i = 1; i <= remainingDays; i++) {
        const date = new Date(year, month + 1, i);
        days.push(createDayData(date, false, today));
    }

    return days;
};

const createDayData = (date: Date, isCurrentMonth: boolean, today: Date) => {
    const dateTime = date.getTime();
    // 非当月日期不显示任何选中效果
    return {
        date,
        isCurrentMonth,
        isToday: dateTime === today.getTime(),
        isStartSelected: isCurrentMonth && startDate.value ? dateTime === new Date(startDate.value).setHours(0, 0, 0, 0) : false,
        isEndSelected: isCurrentMonth && endDate.value ? dateTime === new Date(endDate.value).setHours(0, 0, 0, 0) : false,
        isInRange: isCurrentMonth && isDateInRange(date),
        isRangeStart: isCurrentMonth && isRangeEdge(date, "start"),
        isRangeEnd: isCurrentMonth && isRangeEdge(date, "end"),
        isDisabled: props.disabledDate ? props.disabledDate(date) : false
    };
};

const leftCalendarDays = computed(() => generateCalendarDays(leftPanelYear.value, leftPanelMonth.value));
const rightCalendarDays = computed(() => generateCalendarDays(rightPanelYear.value, rightPanelMonth.value));

// 月份数据
const months = computed(() => dpLocale.value.months);

// 年份范围（当前年份前后10年）
const leftYearRange = computed(() => {
    const startYear = Math.floor(leftPanelYear.value / 10) * 10;
    const years: number[] = [];
    for (let i = startYear - 1; i <= startYear + 10; i++) {
        years.push(i);
    }
    return years;
});

const rightYearRange = computed(() => {
    const startYear = Math.floor(rightPanelYear.value / 10) * 10;
    const years: number[] = [];
    for (let i = startYear - 1; i <= startYear + 10; i++) {
        years.push(i);
    }
    return years;
});

// ============ 选择处理 ============
const selectDate = (date: Date) => {
    if (props.disabledDate?.(date)) return;

    const newDate = new Date(date);

    if (selectingType.value === "start") {
        // 选择开始日期，保留时间
        if (props.showTime) {
            newDate.setHours(startHour.value, startMinute.value, startSecond.value, 0);
        } else {
            newDate.setHours(0, 0, 0, 0);
        }
        const newValue: RangeValue = [newDate, null];
        emit("update:modelValue", newValue);
        emit("calendarChange", newValue, [formatDate(newDate), ""], { range: "start" });
        selectingType.value = "end";
    } else {
        // 选择结束日期
        if (startDate.value) {
            if (props.showTime) {
                newDate.setHours(endHour.value, endMinute.value, endSecond.value, 0);
            } else {
                newDate.setHours(0, 0, 0, 0);
            }

            const startTime = new Date(startDate.value).getTime();
            const newTime = newDate.getTime();

            let finalStart: Date;
            let finalEnd: Date;

            if (newTime >= startTime) {
                finalStart = startDate.value;
                finalEnd = newDate;
            } else {
                // 如果选择的日期在开始日期之前，交换
                finalStart = newDate;
                finalEnd = startDate.value;
                // 交换时间
                if (props.showTime) {
                    const tempHour = startHour.value;
                    const tempMinute = startMinute.value;
                    const tempSecond = startSecond.value;
                    startHour.value = endHour.value;
                    startMinute.value = endMinute.value;
                    startSecond.value = endSecond.value;
                    endHour.value = tempHour;
                    endMinute.value = tempMinute;
                    endSecond.value = tempSecond;
                }
            }

            const newValue: RangeValue = [finalStart, finalEnd];
            emit("update:modelValue", newValue);
            emit("calendarChange", newValue, [formatDate(finalStart), formatDate(finalEnd)], { range: "end" });

            // showTime 模式下不自动关闭，需要点击确定按钮
            if (!props.showTime) {
                emit("change", newValue, [formatDate(finalStart), formatDate(finalEnd)]);
                closePanel();
            }
        }
    }
};

const selectMonth = (monthIndex: number, panel: "left" | "right") => {
    if (props.picker === "month") {
        const year = panel === "left" ? leftPanelYear.value : rightPanelYear.value;
        const newDate = new Date(year, monthIndex, 1);

        if (selectingType.value === "start") {
            const newValue: RangeValue = [newDate, null];
            emit("update:modelValue", newValue);
            emit("calendarChange", newValue, [formatDate(newDate, "YYYY-MM"), ""], { range: "start" });
            selectingType.value = "end";
        } else {
            if (startDate.value) {
                let finalStart: Date;
                let finalEnd: Date;

                if (newDate >= startDate.value) {
                    finalStart = startDate.value;
                    finalEnd = newDate;
                } else {
                    finalStart = newDate;
                    finalEnd = startDate.value;
                }

                const newValue: RangeValue = [finalStart, finalEnd];
                emit("update:modelValue", newValue);
                emit("change", newValue, [formatDate(finalStart, "YYYY-MM"), formatDate(finalEnd, "YYYY-MM")]);
                closePanel();
            }
        }
    } else {
        if (panel === "left") {
            leftPanelMonth.value = monthIndex;
            leftPanelMode.value = "date";
        } else {
            rightPanelMonth.value = monthIndex;
            rightPanelMode.value = "date";
        }
        ensureRightPanelAfterLeft();
    }
};

const selectYear = (year: number, panel: "left" | "right") => {
    if (props.picker === "year") {
        const newDate = new Date(year, 0, 1);

        if (selectingType.value === "start") {
            const newValue: RangeValue = [newDate, null];
            emit("update:modelValue", newValue);
            emit("calendarChange", newValue, [formatDate(newDate, "YYYY"), ""], { range: "start" });
            selectingType.value = "end";
        } else {
            if (startDate.value) {
                let finalStart: Date;
                let finalEnd: Date;

                if (newDate >= startDate.value) {
                    finalStart = startDate.value;
                    finalEnd = newDate;
                } else {
                    finalStart = newDate;
                    finalEnd = startDate.value;
                }

                const newValue: RangeValue = [finalStart, finalEnd];
                emit("update:modelValue", newValue);
                emit("change", newValue, [formatDate(finalStart, "YYYY"), formatDate(finalEnd, "YYYY")]);
                closePanel();
            }
        }
    } else {
        if (panel === "left") {
            leftPanelYear.value = year;
            if (props.picker === "month") {
                leftPanelMode.value = "month";
            } else {
                leftPanelMode.value = "date";
            }
        } else {
            rightPanelYear.value = year;
            if (props.picker === "month") {
                rightPanelMode.value = "month";
            } else {
                rightPanelMode.value = "date";
            }
        }
        ensureRightPanelAfterLeft();
    }
};

// ============ 时间选择处理 ============
const selectStartHour = (hour: number) => {
    startHour.value = hour;
    updateStartTimeSelection();
    nextTick(() => {
        const itemHeight = 28;
        const hourIndex = hours.value.indexOf(hour);
        if (startHourColumnRef.value && hourIndex >= 0) {
            smoothScrollTo(startHourColumnRef.value, hourIndex * itemHeight, 200);
        }
    });
};

const selectStartMinute = (minute: number) => {
    startMinute.value = minute;
    updateStartTimeSelection();
    nextTick(() => {
        const itemHeight = 28;
        const minuteIndex = startMinutes.value.indexOf(minute);
        if (startMinuteColumnRef.value && minuteIndex >= 0) {
            smoothScrollTo(startMinuteColumnRef.value, minuteIndex * itemHeight, 200);
        }
    });
};

const selectStartSecond = (second: number) => {
    startSecond.value = second;
    updateStartTimeSelection();
    nextTick(() => {
        const itemHeight = 28;
        const secondIndex = startSeconds.value.indexOf(second);
        if (startSecondColumnRef.value && secondIndex >= 0) {
            smoothScrollTo(startSecondColumnRef.value, secondIndex * itemHeight, 200);
        }
    });
};

const selectEndHour = (hour: number) => {
    endHour.value = hour;
    updateEndTimeSelection();
    nextTick(() => {
        const itemHeight = 28;
        const hourIndex = hours.value.indexOf(hour);
        if (endHourColumnRef.value && hourIndex >= 0) {
            smoothScrollTo(endHourColumnRef.value, hourIndex * itemHeight, 200);
        }
    });
};

const selectEndMinute = (minute: number) => {
    endMinute.value = minute;
    updateEndTimeSelection();
    nextTick(() => {
        const itemHeight = 28;
        const minuteIndex = endMinutes.value.indexOf(minute);
        if (endMinuteColumnRef.value && minuteIndex >= 0) {
            smoothScrollTo(endMinuteColumnRef.value, minuteIndex * itemHeight, 200);
        }
    });
};

const selectEndSecond = (second: number) => {
    endSecond.value = second;
    updateEndTimeSelection();
    nextTick(() => {
        const itemHeight = 28;
        const secondIndex = endSeconds.value.indexOf(second);
        if (endSecondColumnRef.value && secondIndex >= 0) {
            smoothScrollTo(endSecondColumnRef.value, secondIndex * itemHeight, 200);
        }
    });
};

// 更新开始时间选择
const updateStartTimeSelection = () => {
    if (!startDate.value) return;
    const newDate = new Date(startDate.value);
    newDate.setHours(startHour.value, startMinute.value, startSecond.value, 0);

    const newValue: RangeValue = [newDate, endDate.value];
    emit("update:modelValue", newValue);
    emit("calendarChange", newValue, [formatDate(newDate), formatDate(endDate.value)], { range: "start" });
};

// 更新结束时间选择
const updateEndTimeSelection = () => {
    if (!endDate.value) return;
    const newDate = new Date(endDate.value);
    newDate.setHours(endHour.value, endMinute.value, endSecond.value, 0);

    const newValue: RangeValue = [startDate.value, newDate];
    emit("update:modelValue", newValue);
    emit("calendarChange", newValue, [formatDate(startDate.value), formatDate(newDate)], { range: "end" });
};

// 选择"此刻"（日期+时间都设为当前）
const selectNow = () => {
    const now = new Date();
    const newValue: RangeValue = [now, new Date(now)];

    startHour.value = now.getHours();
    startMinute.value = now.getMinutes();
    startSecond.value = now.getSeconds();
    endHour.value = now.getHours();
    endMinute.value = now.getMinutes();
    endSecond.value = now.getSeconds();

    emit("update:modelValue", newValue);
    emit("change", newValue, [formatDate(now), formatDate(now)]);
    closePanel();
};

// 确认选择（showTime 模式下）
const confirmSelection = () => {
    if (startDate.value && endDate.value) {
        const finalStart = new Date(startDate.value);
        finalStart.setHours(startHour.value, startMinute.value, startSecond.value, 0);

        const finalEnd = new Date(endDate.value);
        finalEnd.setHours(endHour.value, endMinute.value, endSecond.value, 0);

        const newValue: RangeValue = [finalStart, finalEnd];
        emit("update:modelValue", newValue);
        emit("change", newValue, [formatDate(finalStart), formatDate(finalEnd)]);
    }
    closePanel();
};

// ============ 面板导航 ============
const prevMonth = (panel: "left" | "right") => {
    if (panel === "left") {
        if (leftPanelMonth.value === 0) {
            leftPanelMonth.value = 11;
            leftPanelYear.value--;
        } else {
            leftPanelMonth.value--;
        }
    } else {
        if (rightPanelMonth.value === 0) {
            rightPanelMonth.value = 11;
            rightPanelYear.value--;
        } else {
            rightPanelMonth.value--;
        }
        ensureRightPanelAfterLeft();
    }
};

const nextMonth = (panel: "left" | "right") => {
    if (panel === "left") {
        if (leftPanelMonth.value === 11) {
            leftPanelMonth.value = 0;
            leftPanelYear.value++;
        } else {
            leftPanelMonth.value++;
        }
        ensureRightPanelAfterLeft();
    } else {
        if (rightPanelMonth.value === 11) {
            rightPanelMonth.value = 0;
            rightPanelYear.value++;
        } else {
            rightPanelMonth.value++;
        }
    }
};

const prevYear = (panel: "left" | "right") => {
    if (panel === "left") {
        leftPanelYear.value--;
    } else {
        rightPanelYear.value--;
        ensureRightPanelAfterLeft();
    }
};

const nextYear = (panel: "left" | "right") => {
    if (panel === "left") {
        leftPanelYear.value++;
        ensureRightPanelAfterLeft();
    } else {
        rightPanelYear.value++;
    }
};

const prevDecade = (panel: "left" | "right") => {
    if (panel === "left") {
        leftPanelYear.value -= 10;
    } else {
        rightPanelYear.value -= 10;
    }
};

const nextDecade = (panel: "left" | "right") => {
    if (panel === "left") {
        leftPanelYear.value += 10;
    } else {
        rightPanelYear.value += 10;
    }
};

// ============ 清除 ============
const handleClear = (e: Event) => {
    e.stopPropagation();
    emit("update:modelValue", null);
    emit("change", null, ["", ""]);
};

// ============ 悬停处理 ============
const handleDayHover = (date: Date) => {
    if (selectingType.value === "end" && startDate.value) {
        hoveredDate.value = date;
    }
};

const handleDayLeave = () => {
    hoveredDate.value = null;
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
    // 使用 mousedown 而不是 click，避免 DOM 更新后检测失败
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
    const panelTop = position.value.top - window.scrollY;
    if (panelTop < triggerRect.top) {
        return "center bottom";
    }
    return "center top";
});

// 点击输入框区域
const handleInputClick = (type: "start" | "end") => {
    if (props.disabled) return;
    selectingType.value = type;
    if (!isOpen.value) {
        openPanel();
    }
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
        <!-- 日期图标 -->
        <span class="vort-rangepicker-prefix">
            <CalendarOutlined />
        </span>

        <!-- 开始日期输入 -->
        <span :class="getInputClasses('start', !!startDisplayText)" @click.stop="handleInputClick('start')">
            {{ startDisplayText || actualPlaceholder[0] }}
        </span>

        <!-- 分隔符 -->
        <span class="vort-rangepicker-separator">{{ separator }}</span>

        <!-- 结束日期输入 -->
        <span :class="getInputClasses('end', !!endDisplayText)" @click.stop="handleInputClick('end')">
            {{ endDisplayText || actualPlaceholder[1] }}
        </span>

        <!-- 后缀图标 -->
        <span class="vort-rangepicker-suffix">
            <!-- 清除按钮 -->
            <span
                class="vort-rangepicker-clear"
                :class="{ 'vort-rangepicker-clear-visible': showClearButton }"
                @click="handleClear"
                @mousedown.prevent
            >
                <CloseCircleFilled />
            </span>
        </span>
    </div>

    <!-- 日期面板 -->
    <Teleport v-if="shouldRenderTeleport" :to="popupContainer">
        <Transition name="vort-datepicker" appear @after-leave="handleAfterLeave">
            <div
                v-if="isOpen"
                ref="panelRef"
                class="vort-rangepicker-panel"
                :class="{ 'vort-rangepicker-panel-showtime': showTime }"
                :style="{ ...panelStyle, '--transform-origin': transformOrigin }"
            >
                <div class="vort-rangepicker-panel-body">
                    <!-- 预设区域（与 Ant Design 一致，左侧垂直排列） -->
                    <div v-if="hasPresets" class="vort-rangepicker-presets">
                        <button
                            v-for="preset in presets"
                            :key="preset.label"
                            type="button"
                            class="vort-rangepicker-presets-item"
                            :class="isPresetActive(preset) && 'vort-rangepicker-presets-item-active'"
                            @click="applyPresetRange(preset)"
                            @mousedown.prevent
                        >
                            {{ preset.label }}
                        </button>
                    </div>
                    <div class="vort-rangepicker-panels">
                        <!-- 左侧面板 -->
                        <div class="vort-rangepicker-panel-left">
                            <!-- 日期选择区域 -->
                            <div class="vort-datepicker-date-panel">
                                <!-- 日期选择面板 -->
                                <template v-if="leftPanelMode === 'date'">
                                    <!-- 头部 -->
                                    <div class="vort-datepicker-header">
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevYear('left')">
                                            <span class="vort-picker-super-prev-icon"></span>
                                        </button>
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevMonth('left')">
                                            <span class="vort-picker-prev-icon"></span>
                                        </button>

                                        <div class="vort-datepicker-header-view">
                                            <button type="button" class="vort-datepicker-header-btn" @click="leftPanelMode = 'year'">
                                                {{ leftPanelYear }}{{ dpLocale.year_suffix }}
                                            </button>
                                            <button type="button" class="vort-datepicker-header-btn" @click="leftPanelMode = 'month'">
                                                {{ months[leftPanelMonth] }}
                                            </button>
                                        </div>

                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextMonth('left')">
                                            <span class="vort-picker-next-icon"></span>
                                        </button>
                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextYear('left')">
                                            <span class="vort-picker-super-next-icon"></span>
                                        </button>
                                    </div>

                                    <!-- 日历 -->
                                    <div class="vort-datepicker-content">
                                        <!-- 星期头 -->
                                        <div class="vort-datepicker-week-header">
                                            <span v-for="day in weekDays" :key="day" class="vort-datepicker-week-cell">{{ day }}</span>
                                        </div>

                                        <!-- 日期网格 -->
                                        <div class="vort-datepicker-days">
                                            <button
                                                v-for="(day, index) in leftCalendarDays"
                                                :key="index"
                                                type="button"
                                                :class="[
                                                    'vort-datepicker-day-cell',
                                                    !day.isCurrentMonth && 'vort-datepicker-day-other',
                                                    day.isToday && 'vort-datepicker-day-today',
                                                    (day.isStartSelected || day.isEndSelected) && 'vort-datepicker-day-selected',
                                                    day.isInRange && 'vort-datepicker-day-in-range',
                                                    day.isRangeStart && 'vort-datepicker-day-range-start',
                                                    day.isRangeEnd && 'vort-datepicker-day-range-end',
                                                    day.isDisabled && 'vort-datepicker-day-disabled'
                                                ]"
                                                :disabled="day.isDisabled"
                                                @click="selectDate(day.date)"
                                                @mouseenter="handleDayHover(day.date)"
                                                @mouseleave="handleDayLeave"
                                            >
                                                {{ day.date.getDate() }}
                                            </button>
                                        </div>
                                    </div>
                                </template>

                                <!-- 月份选择面板 -->
                                <template v-else-if="leftPanelMode === 'month'">
                                    <div class="vort-datepicker-header">
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevYear('left')">
                                            <span class="vort-picker-super-prev-icon"></span>
                                        </button>

                                        <div class="vort-datepicker-header-view">
                                            <button type="button" class="vort-datepicker-header-btn" @click="leftPanelMode = 'year'">
                                                {{ leftPanelYear }}{{ dpLocale.year_suffix }}
                                            </button>
                                        </div>

                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextYear('left')">
                                            <span class="vort-picker-super-next-icon"></span>
                                        </button>
                                    </div>

                                    <div class="vort-datepicker-content">
                                        <div class="vort-datepicker-months">
                                            <button
                                                v-for="(month, index) in months"
                                                :key="index"
                                                type="button"
                                                :class="[
                                                    'vort-datepicker-month-cell',
                                                    startDate &&
                                                        startDate.getFullYear() === leftPanelYear &&
                                                        startDate.getMonth() === index &&
                                                        'vort-datepicker-month-selected',
                                                    endDate &&
                                                        endDate.getFullYear() === leftPanelYear &&
                                                        endDate.getMonth() === index &&
                                                        'vort-datepicker-month-selected'
                                                ]"
                                                @click="selectMonth(index, 'left')"
                                            >
                                                {{ month }}
                                            </button>
                                        </div>
                                    </div>
                                </template>

                                <!-- 年份选择面板 -->
                                <template v-else-if="leftPanelMode === 'year'">
                                    <div class="vort-datepicker-header">
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevDecade('left')">
                                            <span class="vort-picker-super-prev-icon"></span>
                                        </button>

                                        <div class="vort-datepicker-header-view">
                                            <span class="vort-datepicker-header-text"> {{ leftYearRange[1] }} - {{ leftYearRange[10] }} </span>
                                        </div>

                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextDecade('left')">
                                            <span class="vort-picker-super-next-icon"></span>
                                        </button>
                                    </div>

                                    <div class="vort-datepicker-content">
                                        <div class="vort-datepicker-years">
                                            <button
                                                v-for="year in leftYearRange"
                                                :key="year"
                                                type="button"
                                                :class="[
                                                    'vort-datepicker-year-cell',
                                                    (year === leftYearRange[0] || year === leftYearRange[11]) && 'vort-datepicker-year-other',
                                                    startDate && startDate.getFullYear() === year && 'vort-datepicker-year-selected',
                                                    endDate && endDate.getFullYear() === year && 'vort-datepicker-year-selected'
                                                ]"
                                                @click="selectYear(year, 'left')"
                                            >
                                                {{ year }}
                                            </button>
                                        </div>
                                    </div>
                                </template>
                            </div>

                            <!-- 时间选择区域（showTime 模式下显示） - 开始时间 -->
                            <div v-if="showTime && leftPanelMode === 'date'" class="vort-datepicker-time-panel">
                                <!-- 时间头部 -->
                                <div class="vort-datepicker-time-header">
                                    <span
                                        >{{ String(startHour).padStart(2, "0") }}:{{ String(startMinute).padStart(2, "0")
                                        }}{{ showTimeOptions?.showSecond !== false ? ":" + String(startSecond).padStart(2, "0") : "" }}</span
                                    >
                                </div>

                                <!-- 时间选择列 -->
                                <div class="vort-datepicker-time-content">
                                    <!-- 小时列 -->
                                    <div ref="startHourColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="hour in hours"
                                                :key="hour"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    startHour === hour && 'vort-datepicker-time-cell-selected',
                                                    isHourDisabled(hour) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isHourDisabled(hour) && selectStartHour(hour)"
                                            >
                                                {{ String(hour).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>

                                    <!-- 分钟列 -->
                                    <div ref="startMinuteColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="minute in startMinutes"
                                                :key="minute"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    startMinute === minute && 'vort-datepicker-time-cell-selected',
                                                    isMinuteDisabled(minute, startHour) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isMinuteDisabled(minute, startHour) && selectStartMinute(minute)"
                                            >
                                                {{ String(minute).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>

                                    <!-- 秒列 -->
                                    <div v-if="showTimeOptions?.showSecond !== false" ref="startSecondColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="second in startSeconds"
                                                :key="second"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    startSecond === second && 'vort-datepicker-time-cell-selected',
                                                    isSecondDisabled(second, startHour, startMinute) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isSecondDisabled(second, startHour, startMinute) && selectStartSecond(second)"
                                            >
                                                {{ String(second).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- 右侧面板 -->
                        <div class="vort-rangepicker-panel-right">
                            <!-- 日期选择区域 -->
                            <div class="vort-datepicker-date-panel">
                                <!-- 日期选择面板 -->
                                <template v-if="rightPanelMode === 'date'">
                                    <!-- 头部 -->
                                    <div class="vort-datepicker-header">
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevYear('right')">
                                            <span class="vort-picker-super-prev-icon"></span>
                                        </button>
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevMonth('right')">
                                            <span class="vort-picker-prev-icon"></span>
                                        </button>

                                        <div class="vort-datepicker-header-view">
                                            <button type="button" class="vort-datepicker-header-btn" @click="rightPanelMode = 'year'">
                                                {{ rightPanelYear }}{{ dpLocale.year_suffix }}
                                            </button>
                                            <button type="button" class="vort-datepicker-header-btn" @click="rightPanelMode = 'month'">
                                                {{ months[rightPanelMonth] }}
                                            </button>
                                        </div>

                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextMonth('right')">
                                            <span class="vort-picker-next-icon"></span>
                                        </button>
                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextYear('right')">
                                            <span class="vort-picker-super-next-icon"></span>
                                        </button>
                                    </div>

                                    <!-- 日历 -->
                                    <div class="vort-datepicker-content">
                                        <!-- 星期头 -->
                                        <div class="vort-datepicker-week-header">
                                            <span v-for="day in weekDays" :key="day" class="vort-datepicker-week-cell">{{ day }}</span>
                                        </div>

                                        <!-- 日期网格 -->
                                        <div class="vort-datepicker-days">
                                            <button
                                                v-for="(day, index) in rightCalendarDays"
                                                :key="index"
                                                type="button"
                                                :class="[
                                                    'vort-datepicker-day-cell',
                                                    !day.isCurrentMonth && 'vort-datepicker-day-other',
                                                    day.isToday && 'vort-datepicker-day-today',
                                                    (day.isStartSelected || day.isEndSelected) && 'vort-datepicker-day-selected',
                                                    day.isInRange && 'vort-datepicker-day-in-range',
                                                    day.isRangeStart && 'vort-datepicker-day-range-start',
                                                    day.isRangeEnd && 'vort-datepicker-day-range-end',
                                                    day.isDisabled && 'vort-datepicker-day-disabled'
                                                ]"
                                                :disabled="day.isDisabled"
                                                @click="selectDate(day.date)"
                                                @mouseenter="handleDayHover(day.date)"
                                                @mouseleave="handleDayLeave"
                                            >
                                                {{ day.date.getDate() }}
                                            </button>
                                        </div>
                                    </div>
                                </template>

                                <!-- 月份选择面板 -->
                                <template v-else-if="rightPanelMode === 'month'">
                                    <div class="vort-datepicker-header">
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevYear('right')">
                                            <span class="vort-picker-super-prev-icon"></span>
                                        </button>

                                        <div class="vort-datepicker-header-view">
                                            <button type="button" class="vort-datepicker-header-btn" @click="rightPanelMode = 'year'">
                                                {{ rightPanelYear }}{{ dpLocale.year_suffix }}
                                            </button>
                                        </div>

                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextYear('right')">
                                            <span class="vort-picker-super-next-icon"></span>
                                        </button>
                                    </div>

                                    <div class="vort-datepicker-content">
                                        <div class="vort-datepicker-months">
                                            <button
                                                v-for="(month, index) in months"
                                                :key="index"
                                                type="button"
                                                :class="[
                                                    'vort-datepicker-month-cell',
                                                    startDate &&
                                                        startDate.getFullYear() === rightPanelYear &&
                                                        startDate.getMonth() === index &&
                                                        'vort-datepicker-month-selected',
                                                    endDate &&
                                                        endDate.getFullYear() === rightPanelYear &&
                                                        endDate.getMonth() === index &&
                                                        'vort-datepicker-month-selected'
                                                ]"
                                                @click="selectMonth(index, 'right')"
                                            >
                                                {{ month }}
                                            </button>
                                        </div>
                                    </div>
                                </template>

                                <!-- 年份选择面板 -->
                                <template v-else-if="rightPanelMode === 'year'">
                                    <div class="vort-datepicker-header">
                                        <button type="button" class="vort-datepicker-nav-btn" @click="prevDecade('right')">
                                            <span class="vort-picker-super-prev-icon"></span>
                                        </button>

                                        <div class="vort-datepicker-header-view">
                                            <span class="vort-datepicker-header-text"> {{ rightYearRange[1] }} - {{ rightYearRange[10] }} </span>
                                        </div>

                                        <button type="button" class="vort-datepicker-nav-btn" @click="nextDecade('right')">
                                            <span class="vort-picker-super-next-icon"></span>
                                        </button>
                                    </div>

                                    <div class="vort-datepicker-content">
                                        <div class="vort-datepicker-years">
                                            <button
                                                v-for="year in rightYearRange"
                                                :key="year"
                                                type="button"
                                                :class="[
                                                    'vort-datepicker-year-cell',
                                                    (year === rightYearRange[0] || year === rightYearRange[11]) && 'vort-datepicker-year-other',
                                                    startDate && startDate.getFullYear() === year && 'vort-datepicker-year-selected',
                                                    endDate && endDate.getFullYear() === year && 'vort-datepicker-year-selected'
                                                ]"
                                                @click="selectYear(year, 'right')"
                                            >
                                                {{ year }}
                                            </button>
                                        </div>
                                    </div>
                                </template>
                            </div>

                            <!-- 时间选择区域（showTime 模式下显示） - 结束时间 -->
                            <div v-if="showTime && rightPanelMode === 'date'" class="vort-datepicker-time-panel">
                                <!-- 时间头部 -->
                                <div class="vort-datepicker-time-header">
                                    <span
                                        >{{ String(endHour).padStart(2, "0") }}:{{ String(endMinute).padStart(2, "0")
                                        }}{{ showTimeOptions?.showSecond !== false ? ":" + String(endSecond).padStart(2, "0") : "" }}</span
                                    >
                                </div>

                                <!-- 时间选择列 -->
                                <div class="vort-datepicker-time-content">
                                    <!-- 小时列 -->
                                    <div ref="endHourColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="hour in hours"
                                                :key="hour"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    endHour === hour && 'vort-datepicker-time-cell-selected',
                                                    isHourDisabled(hour) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isHourDisabled(hour) && selectEndHour(hour)"
                                            >
                                                {{ String(hour).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>

                                    <!-- 分钟列 -->
                                    <div ref="endMinuteColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="minute in endMinutes"
                                                :key="minute"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    endMinute === minute && 'vort-datepicker-time-cell-selected',
                                                    isMinuteDisabled(minute, endHour) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isMinuteDisabled(minute, endHour) && selectEndMinute(minute)"
                                            >
                                                {{ String(minute).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>

                                    <!-- 秒列 -->
                                    <div v-if="showTimeOptions?.showSecond !== false" ref="endSecondColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="second in endSeconds"
                                                :key="second"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    endSecond === second && 'vort-datepicker-time-cell-selected',
                                                    isSecondDisabled(second, endHour, endMinute) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isSecondDisabled(second, endHour, endMinute) && selectEndSecond(second)"
                                            >
                                                {{ String(second).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 底部按钮 -->
                <div v-if="showTime" class="vort-datepicker-footer vort-datepicker-footer-showtime">
                    <VortButton v-if="showNow" variant="text" size="small" @click="selectNow">{{ dpT('now') }}</VortButton>
                    <VortButton variant="primary" size="small" @click="confirmSelection">{{ dpT('ok') }}</VortButton>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
/* ========================================
   选择器触发器
   ======================================== */
.vort-rangepicker-selector {
    --_border-color: var(--vort-border, #d9d9d9);
    --_focus-color: var(--vort-primary, #1456f0);
    --_focus-shadow: var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_bg-color: #fff;
    --_input-width: 90px;

    position: relative;
    display: inline-flex;
    align-items: center;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg-color);
    cursor: pointer;
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-rangepicker-selector:hover:not(.vort-rangepicker-disabled) {
    border-color: var(--_focus-color);
}

.vort-rangepicker-focused:not(.vort-rangepicker-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

.vort-rangepicker-error {
    --_border-color: var(--vort-error, #ff4d4f);
    --_focus-color: var(--vort-error, #ff4d4f);
    --_focus-shadow: rgba(255, 77, 79, 0.06);
}

.vort-rangepicker-warning {
    --_border-color: var(--vort-warning, #faad14);
    --_focus-color: var(--vort-warning, #faad14);
    --_focus-shadow: rgba(250, 173, 20, 0.1);
}

.vort-rangepicker-disabled {
    --_bg-color: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

/* 尺寸 */
.vort-rangepicker-large {
    --_input-width: 100px;
    height: var(--vort-height-lg, 40px);
    padding: 0 11px;
    font-size: var(--vort-font-size-md, 16px);
}

.vort-rangepicker-large.vort-rangepicker-showtime {
    --_input-width: 150px;
}

.vort-rangepicker-middle {
    --_input-width: 90px;
    height: var(--vort-height-md, 32px);
    padding: 0 11px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-rangepicker-middle.vort-rangepicker-showtime {
    --_input-width: 140px;
}

.vort-rangepicker-small {
    --_input-width: 80px;
    height: var(--vort-height-sm, 24px);
    padding: 0 7px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-rangepicker-small.vort-rangepicker-showtime {
    --_input-width: 130px;
}

/* 前缀区域 */
.vort-rangepicker-prefix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-right: 8px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* 输入字段 */
.vort-rangepicker-input {
    min-width: 0;
    width: var(--_input-width);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: text;
}

.vort-rangepicker-input-value {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-rangepicker-input-placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

.vort-rangepicker-input-active {
    color: var(--vort-primary, #1456f0);
}

/* 分隔符 */
.vort-rangepicker-separator {
    padding: 0 8px;
    flex-shrink: 0;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* 后缀区域 */
.vort-rangepicker-suffix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-left: 4px;
    width: 14px;
    height: 14px;
    justify-content: center;
}

.vort-rangepicker-clear {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: pointer;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition:
        color var(--vort-transition-colors, 0.1s),
        opacity var(--vort-transition-colors, 0.1s);
}

.vort-rangepicker-clear-visible {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
}

.vort-rangepicker-clear:hover {
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

/* ========================================
   范围选择器面板
   ======================================== */
.vort-rangepicker-panel {
    position: absolute;
    background: #fff;
    border-radius: var(--vort-radius-lg, 8px);
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    overflow: hidden;
}

.vort-rangepicker-panel-body {
    display: flex;
}

.vort-rangepicker-presets {
    display: flex;
    flex-direction: column;
    width: 120px;
    padding: 8px;
    border-right: 1px solid var(--vort-border-secondary);
}

.vort-rangepicker-presets-item {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    font-size: 14px;
    color: var(--vort-text);
    text-align: left;
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius, 6px);
    cursor: pointer;
    transition: all 0.15s;
}

.vort-rangepicker-presets-item:hover:not(.vort-rangepicker-presets-item-active) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-rangepicker-presets-item-active {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
    font-weight: 500;
}

.vort-rangepicker-panels {
    display: flex;
}

.vort-rangepicker-panel-left,
.vort-rangepicker-panel-right {
    width: 268px;
}

.vort-rangepicker-panel-left {
    border-right: 1px solid var(--vort-border-secondary);
}

/* ========================================
   动画 - 复用 motion.css 中的通用下拉动画
   ======================================== */
.vort-datepicker-enter-active {
    animation: vort-dropdown-slide-up-in var(--vort-duration-normal, 150ms) var(--vort-ease-decelerate, cubic-bezier(0, 0, 0.2, 1));
    transform-origin: var(--transform-origin, center top);
}

.vort-datepicker-leave-active {
    animation: vort-dropdown-slide-up-out var(--vort-duration-normal, 150ms) var(--vort-ease-accelerate, cubic-bezier(0.4, 0, 1, 1));
    transform-origin: var(--transform-origin, center top);
}

/* 响应用户"减少动画"偏好设置 */
@media (prefers-reduced-motion: reduce) {
    .vort-datepicker-enter-active,
    .vort-datepicker-leave-active {
        animation-duration: 0ms;
    }
}

/* 头部 */
.vort-datepicker-header {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid var(--vort-border-secondary);
}

.vort-datepicker-nav-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    padding: 0;
    color: var(--vort-text-tertiary);
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-datepicker-nav-btn:hover {
    color: var(--vort-text);
    background: rgba(0, 0, 0, 0.04);
}

.vort-datepicker-header-view {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
}

.vort-datepicker-header-btn {
    padding: 4px 8px;
    font-size: 14px;
    font-weight: 500;
    color: var(--vort-text);
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-datepicker-header-btn:hover {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
}

.vort-datepicker-header-text {
    font-size: 14px;
    font-weight: 500;
    color: var(--vort-text);
}

/* 内容区 */
.vort-datepicker-content {
    padding: 8px;
}

/* 星期头 */
.vort-datepicker-week-header {
    display: grid;
    grid-template-columns: repeat(7, 36px);
    height: 36px;
}

.vort-datepicker-week-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    font-size: 14px;
    color: var(--vort-text-secondary);
}

/* 日期网格 */
.vort-datepicker-days {
    display: grid;
    grid-template-columns: repeat(7, 36px);
}

.vort-datepicker-day-cell {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 6px;
    font-size: 14px;
    color: var(--vort-text);
    background: transparent;
    border: none;
    cursor: pointer;
    transition: color 0.15s;
    z-index: 1;
}

/* 日期数字的可点击区域和背景 */
.vort-datepicker-day-cell::after {
    content: "";
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 24px;
    height: 24px;
    border-radius: var(--vort-border-radius-sm, 4px);
    transition: background-color 0.15s;
    z-index: -1;
}

.vort-datepicker-day-cell:hover:not(.vort-datepicker-day-disabled):not(.vort-datepicker-day-selected)::after {
    background: rgba(0, 0, 0, 0.04);
}

.vort-datepicker-day-other {
    color: var(--vort-text-quaternary);
}

.vort-datepicker-day-today::after {
    border: 1px solid var(--vort-primary);
}

.vort-datepicker-day-selected {
    color: #fff;
}

.vort-datepicker-day-selected::after {
    background: var(--vort-primary);
}

.vort-datepicker-day-selected:hover::after {
    background: var(--vort-primary-hover);
}

/* 范围背景 - 使用 ::before 伪元素 */
.vort-datepicker-day-in-range::before {
    content: "";
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    left: 0;
    right: 0;
    height: 24px;
    background: var(--vort-primary-bg);
    z-index: -1;
}

.vort-datepicker-day-in-range:hover::after {
    background: rgba(0, 0, 0, 0.04);
}

/* 范围起始 - 右侧延伸 */
.vort-datepicker-day-range-start::before {
    content: "";
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    left: calc(50% - 12px);
    right: 0;
    height: 24px;
    background: var(--vort-primary-bg);
    border-radius: var(--vort-border-radius-sm, 4px) 0 0 var(--vort-border-radius-sm, 4px);
    z-index: -1;
}

/* 范围结束 - 左侧延伸 */
.vort-datepicker-day-range-end::before {
    content: "";
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    left: 0;
    right: calc(50% - 12px);
    height: 24px;
    background: var(--vort-primary-bg);
    border-radius: 0 var(--vort-border-radius-sm, 4px) var(--vort-border-radius-sm, 4px) 0;
    z-index: -1;
}

/* 同一天既是开始又是结束时，不需要任何“范围延伸”背景 */
.vort-datepicker-day-range-start.vort-datepicker-day-range-end::before {
    content: none;
}

.vort-datepicker-day-disabled {
    color: var(--vort-text-quaternary);
    cursor: not-allowed;
}

.vort-datepicker-day-disabled::after {
    background: rgba(0, 0, 0, 0.04);
}

/* 月份网格 */
.vort-datepicker-months {
    display: grid;
    grid-template-columns: repeat(3, 84px);
    grid-template-rows: repeat(4, 54px);
}

.vort-datepicker-month-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 84px;
    height: 54px;
    font-size: 14px;
    color: var(--vort-text);
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    transition: all 0.15s;
}

.vort-datepicker-month-cell:hover:not(.vort-datepicker-month-selected) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-datepicker-month-selected {
    color: #fff;
    background: var(--vort-primary);
}

/* 年份网格 */
.vort-datepicker-years {
    display: grid;
    grid-template-columns: repeat(3, 84px);
    grid-template-rows: repeat(4, 54px);
}

.vort-datepicker-year-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 84px;
    height: 54px;
    font-size: 14px;
    color: var(--vort-text);
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    transition: all 0.15s;
}

.vort-datepicker-year-cell:hover:not(.vort-datepicker-year-selected) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-datepicker-year-other {
    color: var(--vort-text-quaternary);
}

.vort-datepicker-year-selected {
    color: #fff;
    background: var(--vort-primary);
}

/* CSS 箭头图标 */
.vort-picker-prev-icon,
.vort-picker-next-icon {
    position: relative;
    display: inline-block;
    width: 7px;
    height: 7px;
}

.vort-picker-super-prev-icon,
.vort-picker-super-next-icon {
    position: relative;
    display: inline-block;
    width: 14px;
    height: 7px;
}

.vort-picker-prev-icon::before,
.vort-picker-next-icon::before {
    position: absolute;
    top: 0;
    inset-inline-start: 0;
    width: 7px;
    height: 7px;
    border: 0 solid currentcolor;
    border-block-start-width: 1.5px;
    border-inline-start-width: 1.5px;
    content: "";
}

.vort-picker-super-prev-icon::before,
.vort-picker-super-next-icon::before {
    position: absolute;
    top: 0;
    inset-inline-start: 0;
    width: 7px;
    height: 7px;
    border: 0 solid currentcolor;
    border-block-start-width: 1.5px;
    border-inline-start-width: 1.5px;
    content: "";
}

.vort-picker-super-prev-icon::after,
.vort-picker-super-next-icon::after {
    position: absolute;
    top: 0;
    inset-inline-start: 7px;
    display: inline-block;
    width: 7px;
    height: 7px;
    border: 0 solid currentcolor;
    border-block-start-width: 1.5px;
    border-inline-start-width: 1.5px;
    content: "";
}

/* 向左箭头 - 旋转 -45deg */
.vort-picker-prev-icon::before,
.vort-picker-super-prev-icon::before,
.vort-picker-super-prev-icon::after {
    transform: rotate(-45deg);
}

/* 向右箭头 - 旋转 135deg */
.vort-picker-next-icon::before,
.vort-picker-super-next-icon::before,
.vort-picker-super-next-icon::after {
    transform: rotate(135deg);
}

/* ============ showTime 模式样式 ============ */

/* 面板容器 - showTime 模式 */
.vort-rangepicker-panel-showtime {
    width: auto;
}

/* 面板主体 - flex 布局 */
.vort-rangepicker-panel-body {
    display: flex;
    flex-direction: row;
}

/* showTime 模式下左右面板内部使用 flex */
.vort-rangepicker-panel-showtime .vort-rangepicker-panel-left,
.vort-rangepicker-panel-showtime .vort-rangepicker-panel-right {
    display: flex;
    width: auto;
}

/* 日期选择区域 */
.vort-datepicker-date-panel {
    flex-shrink: 0;
}

/* 时间面板 */
.vort-datepicker-time-panel {
    display: flex;
    flex-direction: column;
    width: 168px;
    border-left: 1px solid var(--vort-border-secondary);
}

/* 时间头部 */
.vort-datepicker-time-header {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 41px;
    padding: 0 12px;
    font-size: 14px;
    font-weight: 500;
    color: var(--vort-text);
    border-bottom: 1px solid var(--vort-border-secondary);
}

/* 时间内容区 */
.vort-datepicker-time-content {
    display: flex;
    height: 268px;
    overflow: hidden;
}

/* 时间选择列 */
.vort-datepicker-time-column {
    flex: 1;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: rgba(0, 0, 0, 0.15) transparent;
}

.vort-datepicker-time-column:not(:last-child) {
    border-right: 1px solid var(--vort-border-secondary);
}

.vort-datepicker-time-column::-webkit-scrollbar {
    width: 4px;
}

.vort-datepicker-time-column::-webkit-scrollbar-thumb {
    background: rgba(0, 0, 0, 0.15);
    border-radius: 2px;
}

.vort-datepicker-time-column::-webkit-scrollbar-track {
    background: transparent;
}

.vort-datepicker-time-column-inner {
    list-style: none;
    margin: 0;
    padding: 4px 0;
}

/* 时间单元格 */
.vort-datepicker-time-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 28px;
    margin: 0 4px;
    padding: 0 8px;
    font-size: 14px;
    color: var(--vort-text);
    cursor: pointer;
    border-radius: var(--vort-border-radius-sm, 4px);
    transition: all 0.15s;
}

.vort-datepicker-time-cell:hover:not(.vort-datepicker-time-cell-disabled):not(.vort-datepicker-time-cell-selected) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-datepicker-time-cell-selected {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
    font-weight: 500;
}

.vort-datepicker-time-cell-disabled {
    color: var(--vort-text-quaternary);
    cursor: not-allowed;
}

/* 底部 */
.vort-datepicker-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 8px 12px;
    border-top: 1px solid var(--vort-border-secondary);
}

.vort-datepicker-footer-showtime {
    justify-content: space-between;
}
</style>
