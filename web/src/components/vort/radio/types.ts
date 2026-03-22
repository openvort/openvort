/**
 * Radio 组件类型定义
 */

/** Radio 尺寸 */
export type RadioSize = "large" | "middle" | "small";

/** RadioButton 的风格样式 */
export type RadioButtonStyle = "outline" | "solid" | "plain";

/** 用于设置 Radio options 类型 */
export type RadioOptionType = "default" | "button";

/** Radio 组件 Props */
export interface RadioProps {
    /** 单选框的值 */
    value?: string | number;
    /** 是否选中（仅在非 RadioGroup 下使用） */
    checked?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** Radio 组件 Emits */
export interface RadioEmits {
    /** 选中状态变化 */
    (e: "update:checked", checked: boolean): void;
    /** change 事件 */
    (e: "change", event: Event): void;
}

/** RadioButton 组件 Props */
export interface RadioButtonProps extends RadioProps {
    /** 按钮样式类型 */
    buttonStyle?: "outline" | "solid";
}

/** RadioGroup 选项 */
export interface RadioOption {
    /** 选项值 */
    value: string | number;
    /** 选项标签 */
    label: string;
    /** 是否禁用 */
    disabled?: boolean;
}

/** RadioGroup 组件 Props */
export interface RadioGroupProps {
    /** 选中的值（v-model） */
    modelValue?: string | number;
    /** 默认选中的值 */
    defaultValue?: string | number;
    /** 选项列表（简化用法，也可用 Radio 子组件） */
    options?: (string | number | RadioOption)[];
    /** 是否禁用所有选项 */
    disabled?: boolean;
    /** input 的 name 属性 */
    name?: string;
    /** 尺寸 */
    size?: RadioSize;
    /** 按钮风格的 RadioGroup（使用 RadioButton） */
    optionType?: RadioOptionType;
    /** 按钮样式类型 */
    buttonStyle?: RadioButtonStyle;
    /** 自定义类名 */
    class?: string;
}

/** RadioGroup 组件 Emits */
export interface RadioGroupEmits {
    /** 值变化 */
    (e: "update:modelValue", value: string | number): void;
    /** change 事件 */
    (e: "change", event: Event): void;
}

/** RadioGroup 注入的上下文类型 */
export interface RadioGroupContext {
    /** input name 属性 */
    name: { value: string | undefined };
    /** 是否禁用 */
    disabled: { value: boolean };
    /** 尺寸 */
    size: { value: RadioSize };
    /** 选中的值 */
    value: { value: string | number | undefined };
    /** 值变化回调 */
    onChange: (value: string | number, event: Event) => void;
}
