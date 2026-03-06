<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted, useAttrs } from "vue";
import { CalendarOutlined, CloseCircleFilled } from "@/components/vort/icons";
import { Button as VortButton } from "@/components/vort/button";
import { getVortPopupContainer, useZIndex } from "@/components/vort/composables";

defineOptions({ name: "VortDatePicker", inheritAttrs: false });

// 多根节点（包含 Teleport）时，外部属性不会自动继承到根节点，需要手动透传
const attrs = useAttrs();

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popup");

/** Vort DatePicker - 日期选择器组件 */

type DatePickerSize = "large" | "middle" | "small";
type DatePickerStatus = "error" | "warning";
type PickerMode = "date" | "month" | "year";

type PresetValue = Date | string | number | null | undefined | { toDate?: () => Date } | { $d?: Date };

interface PresetItem {
    /** 预设文案 */
    label: string;
    /** 预设值（支持函数返回，便于动态计算“最近7天”等） */
    value: PresetValue | (() => PresetValue);
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
    defaultValue?: Date | string;
}

interface Props {
    /** 选中的日期 (v-model) */
    modelValue?: Date | string | number | null;
    /** 默认选中的日期 */
    defaultValue?: Date | string | number;
    /** 选择器大小 */
    size?: DatePickerSize;
    /** 是否禁用 */
    disabled?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 日期格式化字符串（显示格式） */
    format?: string;
    /** 绑定值的格式，对 value、defaultValue、defaultPickerValue 起作用。不指定则绑定值为 Date 对象 */
    valueFormat?: string;
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
    /** 是否显示今天按钮 */
    showToday?: boolean;
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
    /** 预设日期（与 Ant Design 一致，显示在弹层左侧，垂直排列） */
    presets?: PresetItem[];
}

const props = withDefaults(defineProps<Props>(), {
    size: "middle",
    disabled: false,
    placeholder: undefined,
    format: undefined,
    allowClear: true,
    showToday: true,
    picker: "date",
    showTime: false,
    showNow: true
});

const emit = defineEmits<{
    "update:modelValue": [value: Date | string | null];
    "update:open": [value: boolean];
    change: [value: Date | string | null, dateString: string];
    openChange: [open: boolean];
}>();

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
const actualPlaceholder = computed(() => {
    if (props.placeholder !== undefined) return props.placeholder;
    if (props.showTime) return "请选择日期时间";
    return "请选择日期";
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

// ============ 状态 ============
const isOpen = ref(false);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const isHovered = ref(false);
const isFocused = ref(false);
const triggerRef = ref<HTMLElement | null>(null);
const panelRef = ref<HTMLElement | null>(null);
const position = ref({ top: 0, left: 0 });
const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());

// 当前面板模式
const panelMode = ref<PickerMode>(props.picker);

// 面板显示的年月（用于导航）
const panelYear = ref(new Date().getFullYear());
const panelMonth = ref(new Date().getMonth());

// ============ 时间选择状态 ============
const selectedHour = ref(0);
const selectedMinute = ref(0);
const selectedSecond = ref(0);

// 时间选择列滚动容器引用
const hourColumnRef = ref<HTMLElement | null>(null);
const minuteColumnRef = ref<HTMLElement | null>(null);
const secondColumnRef = ref<HTMLElement | null>(null);

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

const selectedDate = computed(() => parseDate(props.modelValue));

const hasPresets = computed(() => props.picker === "date" && Array.isArray(props.presets) && props.presets.length > 0);

const getPresetDate = (preset: PresetItem): Date | null => {
    const raw = typeof preset.value === "function" ? preset.value() : preset.value;
    return parseDate(raw);
};

const isSameDay = (a: Date, b: Date): boolean => {
    return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
};

const isPresetActive = (preset: PresetItem): boolean => {
    if (!selectedDate.value) return false;
    const presetDate = getPresetDate(preset);
    if (!presetDate) return false;
    // showTime 场景下更接近“精确时间点”，否则按天对齐
    return props.showTime ? selectedDate.value.getTime() === presetDate.getTime() : isSameDay(selectedDate.value, presetDate);
};

const applyPreset = (preset: PresetItem) => {
    const presetDate = getPresetDate(preset);
    if (!presetDate) return;

    // 预设只在 date 选择中使用，切回日期面板并定位到对应月份
    panelMode.value = "date";
    panelYear.value = presetDate.getFullYear();
    panelMonth.value = presetDate.getMonth();

    selectDate(presetDate);
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

// 根据 valueFormat 返回输出值
const getOutputValue = (date: Date | null): Date | string | null => {
    if (!date) return props.valueFormat ? "" : null;
    return props.valueFormat ? formatDate(date, props.valueFormat) : date;
};

// 显示的文本
const displayText = computed(() => {
    if (!selectedDate.value) return "";
    return formatDate(selectedDate.value, actualFormat.value);
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

const minutes = computed(() => {
    const result: number[] = [];
    const step = showTimeOptions.value?.minuteStep ?? 1;
    const disabledMinutesList = props.disabledMinutes?.(selectedHour.value) || [];

    for (let i = 0; i < 60; i += step) {
        if (!disabledMinutesList.includes(i)) {
            result.push(i);
        }
    }
    return result;
});

const seconds = computed(() => {
    const result: number[] = [];
    const step = showTimeOptions.value?.secondStep ?? 1;
    const disabledSecondsList = props.disabledSeconds?.(selectedHour.value, selectedMinute.value) || [];

    for (let i = 0; i < 60; i += step) {
        if (!disabledSecondsList.includes(i)) {
            result.push(i);
        }
    }
    return result;
});

// 判断时间是否被禁用
const isHourDisabled = (hour: number): boolean => {
    return props.disabledHours?.().includes(hour) ?? false;
};

const isMinuteDisabled = (minute: number): boolean => {
    return props.disabledMinutes?.(selectedHour.value).includes(minute) ?? false;
};

const isSecondDisabled = (second: number): boolean => {
    return props.disabledSeconds?.(selectedHour.value, selectedMinute.value).includes(second) ?? false;
};

// ============ 样式类（简洁的类名切换） ============

/** 触发器类名 */
const triggerClasses = computed(() => {
    const classes = ["vort-datepicker-selector", `vort-datepicker-${props.size}`];

    if (props.status) classes.push(`vort-datepicker-${props.status}`);
    if (props.disabled) classes.push("vort-datepicker-disabled");
    if (isFocused.value || isOpen.value) classes.push("vort-datepicker-focused");
    if (props.class) classes.push(props.class);

    return classes;
});

// 是否显示清除按钮
const showClearButton = computed(() => {
    return props.allowClear && !props.disabled && selectedDate.value && isHovered.value;
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

    const hourIndex = hours.value.indexOf(selectedHour.value);
    scrollToPosition(hourColumnRef.value, hourIndex);

    const minuteIndex = minutes.value.indexOf(selectedMinute.value);
    scrollToPosition(minuteColumnRef.value, minuteIndex);

    const secondIndex = seconds.value.indexOf(selectedSecond.value);
    scrollToPosition(secondColumnRef.value, secondIndex);
};

// ============ 面板控制 ============
const openPanel = () => {
    if (props.disabled) return;
    shouldRenderTeleport.value = true; // 先渲染 Teleport
    isOpen.value = true;
    emit("update:open", true);
    emit("openChange", true);

    // 初始化面板年月和时间
    if (selectedDate.value) {
        panelYear.value = selectedDate.value.getFullYear();
        panelMonth.value = selectedDate.value.getMonth();
        // 初始化时间选择
        if (props.showTime) {
            selectedHour.value = selectedDate.value.getHours();
            selectedMinute.value = selectedDate.value.getMinutes();
            selectedSecond.value = selectedDate.value.getSeconds();
        }
    } else {
        const now = new Date();
        panelYear.value = now.getFullYear();
        panelMonth.value = now.getMonth();
        // 如果有 showTime.defaultValue，使用它作为默认时间
        if (props.showTime) {
            const defaultTime = showTimeOptions.value?.defaultValue;
            if (defaultTime) {
                const time = parseDate(defaultTime);
                if (time) {
                    selectedHour.value = time.getHours();
                    selectedMinute.value = time.getMinutes();
                    selectedSecond.value = time.getSeconds();
                } else {
                    selectedHour.value = 0;
                    selectedMinute.value = 0;
                    selectedSecond.value = 0;
                }
            } else {
                selectedHour.value = 0;
                selectedMinute.value = 0;
                selectedSecond.value = 0;
            }
        }
    }

    // 重置面板模式
    panelMode.value = props.picker;

    nextTick(() => {
        updatePosition();
        if (props.showTime) {
            scrollToSelectedTime();
        }
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

// ============ 日历数据 ============
// 从周一开始
const weekDays = ["一", "二", "三", "四", "五", "六", "日"];

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

// 生成日历网格数据
const calendarDays = computed(() => {
    const year = panelYear.value;
    const month = panelMonth.value;
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    const prevMonthDays = getDaysInMonth(year, month - 1);

    const days: Array<{ date: Date; isCurrentMonth: boolean; isToday: boolean; isSelected: boolean; isDisabled: boolean }> = [];

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // 上月的补充日期
    for (let i = firstDay - 1; i >= 0; i--) {
        const date = new Date(year, month - 1, prevMonthDays - i);
        days.push({
            date,
            isCurrentMonth: false,
            isToday: date.getTime() === today.getTime(),
            isSelected: selectedDate.value ? date.getTime() === selectedDate.value.setHours(0, 0, 0, 0) : false,
            isDisabled: props.disabledDate ? props.disabledDate(date) : false
        });
    }

    // 当月日期
    for (let i = 1; i <= daysInMonth; i++) {
        const date = new Date(year, month, i);
        days.push({
            date,
            isCurrentMonth: true,
            isToday: date.getTime() === today.getTime(),
            isSelected: selectedDate.value ? date.getTime() === new Date(selectedDate.value).setHours(0, 0, 0, 0) : false,
            isDisabled: props.disabledDate ? props.disabledDate(date) : false
        });
    }

    // 下月的补充日期（补满6行）
    const remainingDays = 42 - days.length;
    for (let i = 1; i <= remainingDays; i++) {
        const date = new Date(year, month + 1, i);
        days.push({
            date,
            isCurrentMonth: false,
            isToday: date.getTime() === today.getTime(),
            isSelected: selectedDate.value ? date.getTime() === new Date(selectedDate.value).setHours(0, 0, 0, 0) : false,
            isDisabled: props.disabledDate ? props.disabledDate(date) : false
        });
    }

    return days;
});

// 月份数据
const months = ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"];

// 年份范围（当前年份前后10年）
const yearRange = computed(() => {
    const startYear = Math.floor(panelYear.value / 10) * 10;
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

    // 如果启用了时间选择，保留当前选中的时间
    if (props.showTime) {
        newDate.setHours(selectedHour.value, selectedMinute.value, selectedSecond.value, 0);
        emit("update:modelValue", getOutputValue(newDate));
        emit("change", getOutputValue(newDate), formatDate(newDate));
        // showTime 模式下不自动关闭，需要点击确定按钮
    } else {
        emit("update:modelValue", getOutputValue(newDate));
        emit("change", getOutputValue(newDate), formatDate(newDate));
        if (props.picker === "date") {
            closePanel();
        }
    }
};

const selectMonth = (monthIndex: number) => {
    if (props.picker === "month") {
        const newDate = new Date(panelYear.value, monthIndex, 1);
        const displayFormat = props.valueFormat || "YYYY-MM";
        emit("update:modelValue", getOutputValue(newDate));
        emit("change", getOutputValue(newDate), formatDate(newDate, displayFormat));
        closePanel();
    } else {
        panelMonth.value = monthIndex;
        panelMode.value = "date";
    }
};

const selectYear = (year: number) => {
    if (props.picker === "year") {
        const newDate = new Date(year, 0, 1);
        const displayFormat = props.valueFormat || "YYYY";
        emit("update:modelValue", getOutputValue(newDate));
        emit("change", getOutputValue(newDate), formatDate(newDate, displayFormat));
        closePanel();
    } else {
        panelYear.value = year;
        if (props.picker === "month") {
            panelMode.value = "month";
        } else {
            panelMode.value = "date";
        }
    }
};

const selectToday = () => {
    const today = new Date();
    if (props.showTime) {
        // showTime 模式下的"今天"只选择日期，保留时间
        today.setHours(selectedHour.value, selectedMinute.value, selectedSecond.value, 0);
    } else {
        today.setHours(0, 0, 0, 0);
    }
    emit("update:modelValue", getOutputValue(today));
    emit("change", getOutputValue(today), formatDate(today));
    if (!props.showTime) {
        closePanel();
    }
};

// ============ 时间选择处理 ============
const selectHour = (hour: number) => {
    selectedHour.value = hour;
    updateTimeSelection();
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
    updateTimeSelection();
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
    updateTimeSelection();
    // 平滑滚动到选中的秒
    nextTick(() => {
        const itemHeight = 28;
        const secondIndex = seconds.value.indexOf(second);
        if (secondColumnRef.value && secondIndex >= 0) {
            smoothScrollTo(secondColumnRef.value, secondIndex * itemHeight, 200);
        }
    });
};

// 更新时间选择（在已选日期的基础上更新时间）
const updateTimeSelection = () => {
    if (!selectedDate.value) return;
    const newDate = new Date(selectedDate.value);
    newDate.setHours(selectedHour.value, selectedMinute.value, selectedSecond.value, 0);
    emit("update:modelValue", getOutputValue(newDate));
    emit("change", getOutputValue(newDate), formatDate(newDate));
};

// 选择"此刻"（日期+时间都设为当前）
const selectNow = () => {
    const now = new Date();
    selectedHour.value = now.getHours();
    selectedMinute.value = now.getMinutes();
    selectedSecond.value = now.getSeconds();
    emit("update:modelValue", getOutputValue(now));
    emit("change", getOutputValue(now), formatDate(now));
    closePanel();
};

// 确认选择（showTime 模式下）
const confirmSelection = () => {
    if (selectedDate.value) {
        const newDate = new Date(selectedDate.value);
        newDate.setHours(selectedHour.value, selectedMinute.value, selectedSecond.value, 0);
        emit("update:modelValue", getOutputValue(newDate));
        emit("change", getOutputValue(newDate), formatDate(newDate));
    }
    closePanel();
};

// ============ 面板导航 ============
const prevMonth = () => {
    if (panelMonth.value === 0) {
        panelMonth.value = 11;
        panelYear.value--;
    } else {
        panelMonth.value--;
    }
};

const nextMonth = () => {
    if (panelMonth.value === 11) {
        panelMonth.value = 0;
        panelYear.value++;
    } else {
        panelMonth.value++;
    }
};

const prevYear = () => {
    panelYear.value--;
};

const nextYear = () => {
    panelYear.value++;
};

const prevDecade = () => {
    panelYear.value -= 10;
};

const nextDecade = () => {
    panelYear.value += 10;
};

// ============ 清除 ============
const handleClear = (e: Event) => {
    e.stopPropagation();
    // 如果指定了 valueFormat，清除时返回空字符串；否则返回 null
    const clearValue = props.valueFormat ? "" : null;
    emit("update:modelValue", clearValue);
    emit("change", clearValue, "");
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
    const container = popupContainer.value;
    const useCustomContainer = container && container !== document.body;
    const containerRect = useCustomContainer ? container.getBoundingClientRect() : null;
    const panelTop = useCustomContainer && containerRect ? position.value.top - container.scrollTop + containerRect.top : position.value.top - window.scrollY;
    if (panelTop < triggerRect.top) {
        return "center bottom";
    }
    return "center top";
});

// 暴露方法
defineExpose({
    focus: () => triggerRef.value?.focus(),
    blur: () => triggerRef.value?.blur()
});
</script>

<template>
    <div
        ref="triggerRef"
        :class="triggerClasses"
        v-bind="attrs"
        tabindex="0"
        @click="togglePanel"
        @mouseenter="isHovered = true"
        @mouseleave="isHovered = false"
        @focus="isFocused = true"
        @blur="isFocused = false"
    >
        <!-- 日期图标 -->
        <span class="vort-datepicker-prefix">
            <CalendarOutlined />
        </span>

        <!-- 显示内容 -->
        <span class="vort-datepicker-value" :class="{ 'vort-datepicker-placeholder': !displayText }">
            {{ displayText || actualPlaceholder }}
        </span>

        <!-- 后缀图标 -->
        <span class="vort-datepicker-suffix">
            <!-- 清除按钮 -->
            <span v-if="showClearButton" class="vort-datepicker-clear" @click="handleClear" @mousedown.prevent>
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
                class="vort-datepicker-panel"
                :class="{ 'vort-datepicker-panel-showtime': showTime }"
                :style="{ ...panelStyle, '--transform-origin': transformOrigin }"
            >
                <!-- 日期选择面板 -->
                <template v-if="panelMode === 'date'">
                    <div class="vort-datepicker-panel-body">
                        <!-- 预设区域（与 Ant Design 一致，左侧垂直排列） -->
                        <div v-if="hasPresets" class="vort-datepicker-presets">
                            <button
                                v-for="preset in presets"
                                :key="preset.label"
                                type="button"
                                class="vort-datepicker-presets-item"
                                :class="isPresetActive(preset) && 'vort-datepicker-presets-item-active'"
                                @click="applyPreset(preset)"
                                @mousedown.prevent
                            >
                                {{ preset.label }}
                            </button>
                        </div>

                        <div class="vort-datepicker-panel-main">
                            <!-- 日期区域 -->
                            <div class="vort-datepicker-date-panel">
                                <!-- 头部 -->
                                <div class="vort-datepicker-header">
                                    <button type="button" class="vort-datepicker-nav-btn" @click="prevYear">
                                        <span class="vort-picker-super-prev-icon"></span>
                                    </button>
                                    <button type="button" class="vort-datepicker-nav-btn" @click="prevMonth">
                                        <span class="vort-picker-prev-icon"></span>
                                    </button>

                                    <div class="vort-datepicker-header-view">
                                        <button type="button" class="vort-datepicker-header-btn" @click="panelMode = 'year'">{{ panelYear }}年</button>
                                        <button type="button" class="vort-datepicker-header-btn" @click="panelMode = 'month'">{{ panelMonth + 1 }}月</button>
                                    </div>

                                    <button type="button" class="vort-datepicker-nav-btn" @click="nextMonth">
                                        <span class="vort-picker-next-icon"></span>
                                    </button>
                                    <button type="button" class="vort-datepicker-nav-btn" @click="nextYear">
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
                                            v-for="(day, index) in calendarDays"
                                            :key="index"
                                            type="button"
                                            :class="[
                                                'vort-datepicker-day-cell',
                                                !day.isCurrentMonth && 'vort-datepicker-day-other',
                                                day.isToday && 'vort-datepicker-day-today',
                                                day.isSelected && 'vort-datepicker-day-selected',
                                                day.isDisabled && 'vort-datepicker-day-disabled'
                                            ]"
                                            :disabled="day.isDisabled"
                                            @click="selectDate(day.date)"
                                        >
                                            {{ day.date.getDate() }}
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <!-- 时间选择区域（showTime 模式下显示） -->
                            <div v-if="showTime" class="vort-datepicker-time-panel">
                                <!-- 时间头部 -->
                                <div class="vort-datepicker-time-header">
                                    <span
                                        >{{ String(selectedHour).padStart(2, "0") }}:{{ String(selectedMinute).padStart(2, "0")
                                        }}{{ showTimeOptions?.showSecond !== false ? ":" + String(selectedSecond).padStart(2, "0") : "" }}</span
                                    >
                                </div>

                                <!-- 时间选择列 -->
                                <div class="vort-datepicker-time-content">
                                    <!-- 小时列 -->
                                    <div ref="hourColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="hour in hours"
                                                :key="hour"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    selectedHour === hour && 'vort-datepicker-time-cell-selected',
                                                    isHourDisabled(hour) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isHourDisabled(hour) && selectHour(hour)"
                                            >
                                                {{ String(hour).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>

                                    <!-- 分钟列 -->
                                    <div ref="minuteColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="minute in minutes"
                                                :key="minute"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    selectedMinute === minute && 'vort-datepicker-time-cell-selected',
                                                    isMinuteDisabled(minute) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isMinuteDisabled(minute) && selectMinute(minute)"
                                            >
                                                {{ String(minute).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>

                                    <!-- 秒列 -->
                                    <div v-if="showTimeOptions?.showSecond !== false" ref="secondColumnRef" class="vort-datepicker-time-column">
                                        <ul class="vort-datepicker-time-column-inner">
                                            <li
                                                v-for="second in seconds"
                                                :key="second"
                                                :class="[
                                                    'vort-datepicker-time-cell',
                                                    selectedSecond === second && 'vort-datepicker-time-cell-selected',
                                                    isSecondDisabled(second) && 'vort-datepicker-time-cell-disabled'
                                                ]"
                                                @click="!isSecondDisabled(second) && selectSecond(second)"
                                            >
                                                {{ String(second).padStart(2, "0") }}
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- 底部 -->
                    <div v-if="showTime" class="vort-datepicker-footer vort-datepicker-footer-showtime">
                        <VortButton v-if="showNow" variant="text" size="small" @click="selectNow"> 此刻 </VortButton>
                        <VortButton variant="primary" size="small" @click="confirmSelection"> 确定 </VortButton>
                    </div>
                    <div v-else-if="showToday && picker === 'date'" class="vort-datepicker-footer">
                        <button type="button" class="vort-datepicker-today-btn" @click="selectToday">今天</button>
                    </div>
                </template>

                <!-- 月份选择面板 -->
                <template v-else-if="panelMode === 'month'">
                    <div class="vort-datepicker-header">
                        <button type="button" class="vort-datepicker-nav-btn" @click="prevYear">
                            <span class="vort-picker-super-prev-icon"></span>
                        </button>

                        <div class="vort-datepicker-header-view">
                            <button type="button" class="vort-datepicker-header-btn" @click="panelMode = 'year'">{{ panelYear }}年</button>
                        </div>

                        <button type="button" class="vort-datepicker-nav-btn" @click="nextYear">
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
                                    selectedDate &&
                                        selectedDate.getFullYear() === panelYear &&
                                        selectedDate.getMonth() === index &&
                                        'vort-datepicker-month-selected'
                                ]"
                                @click="selectMonth(index)"
                            >
                                {{ month }}
                            </button>
                        </div>
                    </div>
                </template>

                <!-- 年份选择面板 -->
                <template v-else-if="panelMode === 'year'">
                    <div class="vort-datepicker-header">
                        <button type="button" class="vort-datepicker-nav-btn" @click="prevDecade">
                            <span class="vort-picker-super-prev-icon"></span>
                        </button>

                        <div class="vort-datepicker-header-view">
                            <span class="vort-datepicker-header-text"> {{ yearRange[1] }} - {{ yearRange[10] }} </span>
                        </div>

                        <button type="button" class="vort-datepicker-nav-btn" @click="nextDecade">
                            <span class="vort-picker-super-next-icon"></span>
                        </button>
                    </div>

                    <div class="vort-datepicker-content">
                        <div class="vort-datepicker-years">
                            <button
                                v-for="year in yearRange"
                                :key="year"
                                type="button"
                                :class="[
                                    'vort-datepicker-year-cell',
                                    (year === yearRange[0] || year === yearRange[11]) && 'vort-datepicker-year-other',
                                    selectedDate && selectedDate.getFullYear() === year && 'vort-datepicker-year-selected'
                                ]"
                                @click="selectYear(year)"
                            >
                                {{ year }}
                            </button>
                        </div>
                    </div>
                </template>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
/* ========================================
   选择器触发器
   ======================================== */
.vort-datepicker-selector {
    --_border-color: var(--vort-border, #d9d9d9);
    --_focus-color: var(--vort-primary, #1456f0);
    --_focus-shadow: var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_bg-color: #fff;

    position: relative;
    display: inline-flex;
    align-items: center;
    width: 100%;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg-color);
    cursor: pointer;
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-datepicker-selector:hover:not(.vort-datepicker-disabled) {
    border-color: var(--_focus-color);
}

.vort-datepicker-focused:not(.vort-datepicker-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

.vort-datepicker-error {
    --_border-color: var(--vort-error, #ff4d4f);
    --_focus-color: var(--vort-error, #ff4d4f);
    --_focus-shadow: rgba(255, 77, 79, 0.06);
}

.vort-datepicker-warning {
    --_border-color: var(--vort-warning, #faad14);
    --_focus-color: var(--vort-warning, #faad14);
    --_focus-shadow: rgba(250, 173, 20, 0.1);
}

.vort-datepicker-disabled {
    --_bg-color: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

/* 尺寸 */
.vort-datepicker-large {
    height: var(--vort-height-lg, 40px);
    padding: 0 11px;
    font-size: var(--vort-font-size-md, 16px);
}

.vort-datepicker-middle {
    height: var(--vort-height-md, 32px);
    padding: 0 11px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-datepicker-small {
    height: var(--vort-height-sm, 24px);
    padding: 0 7px;
    font-size: var(--vort-font-size-sm, 14px);
}

/* 前缀区域 */
.vort-datepicker-prefix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-right: 8px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* 值区域 */
.vort-datepicker-value {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-datepicker-placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* 后缀区域 */
.vort-datepicker-suffix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-left: 4px;
}

.vort-datepicker-clear {
    display: flex;
    align-items: center;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: pointer;
    transition: color var(--vort-transition-colors, 0.1s);
}

.vort-datepicker-clear:hover {
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

/* ========================================
   面板样式
   ======================================== */
.vort-datepicker-panel {
    position: absolute;
    background: #fff;
    border-radius: var(--vort-radius-lg, 8px);
    pointer-events: auto;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    overflow: hidden;
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

.vort-datepicker-today-btn {
    padding: 4px 12px;
    font-size: 14px;
    color: var(--vort-primary);
    background: transparent;
    border: none;
    border-radius: var(--vort-border-radius-sm, 4px);
    cursor: pointer;
    transition: all 0.2s;
}

.vort-datepicker-today-btn:hover {
    background: var(--vort-primary-bg);
}

/* ============ showTime 模式样式 ============ */

/* 面板容器 - showTime 模式 */
.vort-datepicker-panel-showtime {
    width: auto;
}

/* 面板主体 - flex 布局 */
.vort-datepicker-panel-body {
    display: flex;
}

.vort-datepicker-panel-main {
    display: flex;
}

.vort-datepicker-presets {
    display: flex;
    flex-direction: column;
    width: 120px;
    padding: 8px;
    border-right: 1px solid var(--vort-border-secondary);
}

.vort-datepicker-presets-item {
    display: flex;
    align-items: center;
    height: 32px;
    padding: 0 12px;
    font-size: 14px;
    color: var(--vort-text);
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.15s;
}

.vort-datepicker-presets-item:hover:not(.vort-datepicker-presets-item-active) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-datepicker-presets-item-active {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
    font-weight: 500;
}

/* 日期区域 */
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
</style>
