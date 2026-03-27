/**
 * Input 组件类型定义
 */

/** 输入框尺寸 */
export type InputSize = "large" | "middle" | "small";

/** 输入框状态 */
export type InputStatus = "error" | "warning";

/**
 * 输入框形态变体
 * - outlined: 默认有边框
 * - filled: 填充背景
 * - borderless: 无边框
 * - underlined: 下划线
 */
export type InputVariant = "outlined" | "filled" | "borderless" | "underlined";

/** Input 组件 Props */
export interface InputProps {
    /** 输入框内容（v-model） */
    modelValue?: string | number;
    /** 默认值（非受控模式） */
    defaultValue?: string | number;
    /** 尺寸 */
    size?: InputSize;
    /** 输入框状态 */
    status?: InputStatus;
    /** 输入框形态变体 */
    variant?: InputVariant;
    /** 是否禁用 */
    disabled?: boolean;
    bordered?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 自定义类名 */
    class?: string;
    /** 可以点击清除图标删除内容 */
    allowClear?: boolean;
    /** 最大输入长度 */
    maxlength?: number;
    /** 是否展示字数 */
    showCount?: boolean;
    /** 紧凑模式，用于 addonBefore/addonAfter 放置 Select 等组件 */
    compact?: boolean;
    /** 按钮模式，用于 addonAfter 放置 Button（透明容器，无 padding 和背景） */
    addonButtonMode?: boolean;
}

/** Input 组件 Emits */
export interface InputEmits {
    /** 值更新事件 */
    (e: "update:modelValue", value: string): void;
    /** 原生 change 事件 */
    (e: "change", event: Event): void;
    /** 原生 input 事件 */
    (e: "input", event: Event): void;
    /** 获得焦点事件 */
    (e: "focus", event: FocusEvent): void;
    /** 失去焦点事件 */
    (e: "blur", event: FocusEvent): void;
    /** 按下回车键事件 */
    (e: "pressEnter", event: KeyboardEvent): void;
    /** 清除内容事件 */
    (e: "clear"): void;
}

/** InputNumber 组件 Props */
export interface InputNumberProps {
    /** 当前值（v-model） */
    modelValue?: number | null;
    /** 默认值 */
    defaultValue?: number;
    /** 最小值 */
    min?: number;
    /** 最大值 */
    max?: number;
    /** 每次改变步数，可以为小数 */
    step?: number | string;
    /** 数值精度（小数位数） */
    precision?: number;
    /** 尺寸 */
    size?: InputSize;
    /** 输入框状态 */
    status?: InputStatus;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否只读 */
    readOnly?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 输入框占位文本 */
    placeholder?: string;
    /** 自定义类名 */
    class?: string;
    /** 是否隐藏控制按钮 */
    controls?: boolean;
    /** 指定输入框展示值的格式 */
    formatter?: (value: number | string | undefined) => string;
    /** 指定从 formatter 里转换回数字的方式 */
    parser?: (value: string | undefined) => number | string;
    /** 带有前缀图标的 input */
    prefix?: string;
    /** 是否启用键盘快捷行为（上下箭头调整值） */
    keyboard?: boolean;
    /** 是否严格校验，在失焦时校验并矫正数值 */
    stringMode?: boolean;
    /** 紧凑模式，用于 addonBefore/addonAfter 放置 Select 等组件 */
    compact?: boolean;
}

/** InputPassword 组件 Props */
export interface InputPasswordProps extends Omit<InputProps, "modelValue" | "defaultValue"> {
    /** 输入框内容（v-model） */
    modelValue?: string;
    /** 默认值（非受控模式） */
    defaultValue?: string;
    /** 是否显示切换密码可见按钮 */
    visibilityToggle?: boolean;
}

/** InputSearch 组件 Props */
export interface InputSearchProps extends Omit<InputProps, "modelValue" | "defaultValue"> {
    /** 输入框内容（v-model） */
    modelValue?: string;
    /** 默认值（非受控模式） */
    defaultValue?: string;
    /** 是否有确认按钮（可设为按钮文字），true 为蓝色按钮，false 为白色按钮 */
    enterButton?: boolean | string;
    /** 搜索按钮加载状态 */
    loading?: boolean;
}
