/**
 * DatePicker / RangePicker 组件类型定义
 */

/** 日期选择器尺寸 */
export type DatePickerSize = "large" | "middle" | "small";

/** 日期选择器校验状态 */
export type DatePickerStatus = "error" | "warning";

/** 选择器类型 */
export type PickerMode = "date" | "month" | "year";

/** 预设值类型（支持 Date、字符串、时间戳、dayjs 对象等） */
export type PresetValue = Date | string | number | null | undefined | { toDate?: () => Date } | { $d?: Date };

/** 范围值类型 */
export type RangeValue = [Date | null, Date | null] | null;

/** showTime 配置选项 */
export interface ShowTimeOptions {
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

/** RangePicker showTime 配置选项 */
export interface RangeShowTimeOptions {
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

/** 预设日期项（DatePicker） */
export interface PresetItem {
    /** 预设文案 */
    label: string;
    /** 预设值（支持函数返回，便于动态计算"最近7天"等） */
    value: PresetValue | (() => PresetValue);
}

/** 预设范围项（RangePicker） */
export interface RangePresetItem {
    /** 预设文案 */
    label: string;
    /** 预设值（支持函数返回，便于动态计算"最近7天"等） */
    value: [PresetValue, PresetValue] | (() => [PresetValue, PresetValue]);
}

/** DatePicker 组件 Props */
export interface DatePickerProps {
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

/** DatePicker 组件 Emits */
export interface DatePickerEmits {
    /** 值更新事件 */
    (e: "update:modelValue", value: Date | string | null): void;
    /** 弹层显示状态更新事件 */
    (e: "update:open", value: boolean): void;
    /** 日期变化事件 */
    (e: "change", value: Date | string | null, dateString: string): void;
    /** 弹层显示状态变化事件 */
    (e: "openChange", open: boolean): void;
}

/** RangePicker 组件 Props */
export interface RangePickerProps {
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
    showTime?: boolean | RangeShowTimeOptions;
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

/** RangePicker 组件 Emits */
export interface RangePickerEmits {
    /** 值更新事件 */
    (e: "update:modelValue", value: RangeValue): void;
    /** 弹层显示状态更新事件 */
    (e: "update:open", value: boolean): void;
    /** 日期范围变化事件 */
    (e: "change", value: RangeValue, dateStrings: [string, string]): void;
    /** 弹层显示状态变化事件 */
    (e: "openChange", open: boolean): void;
    /** 日历变化事件（选择过程中触发） */
    (e: "calendarChange", dates: RangeValue, dateStrings: [string, string], info: { range: "start" | "end" }): void;
}
