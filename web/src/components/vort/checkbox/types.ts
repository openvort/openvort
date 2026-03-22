/**
 * Checkbox 组件类型定义
 */

/** Checkbox 组件 Props */
export interface CheckboxProps {
    /** 复选框的值（在 CheckboxGroup 中使用） */
    value?: string | number;
    /** 是否选中（v-model:checked） */
    checked?: boolean;
    /** 设置 indeterminate 状态，只负责样式控制 */
    indeterminate?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** Checkbox 组件 Emits */
export interface CheckboxEmits {
    /** 选中状态变化 */
    (e: "update:checked", checked: boolean): void;
    /** change 事件 */
    (e: "change", event: Event, checked: boolean): void;
}

/** CheckboxGroup 选项 */
export interface CheckboxOption {
    /** 选项值 */
    value: string | number;
    /** 选项标签 */
    label: string;
    /** 是否禁用 */
    disabled?: boolean;
}

/** CheckboxGroup 组件 Props */
export interface CheckboxGroupProps {
    /** 选中的值数组（v-model） */
    modelValue?: (string | number)[];
    /** 默认选中的值 */
    defaultValue?: (string | number)[];
    /** 选项列表（简化用法，也可用 Checkbox 子组件） */
    options?: (string | number | CheckboxOption)[];
    /** 是否禁用所有选项 */
    disabled?: boolean;
    /** input 的 name 属性 */
    name?: string;
    /** 自定义类名 */
    class?: string;
}

/** CheckboxGroup 组件 Emits */
export interface CheckboxGroupEmits {
    /** 值变化 */
    (e: "update:modelValue", value: (string | number)[]): void;
    /** change 事件 */
    (e: "change", value: (string | number)[]): void;
}

/** CheckboxGroup 注入的上下文类型 */
export interface CheckboxGroupContext {
    /** input name 属性 */
    name: { value: string | undefined };
    /** 是否禁用 */
    disabled: { value: boolean };
    /** 选中的值数组 */
    value: { value: (string | number)[] };
    /** 值变化回调 */
    onChange: (value: string | number, checked: boolean, event: Event) => void;
}
