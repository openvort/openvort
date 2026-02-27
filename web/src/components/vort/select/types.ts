/**
 * Select 组件类型定义
 */

/** 选择器尺寸 */
export type SelectSize = "large" | "middle" | "small";

/** 选择器校验状态 */
export type SelectStatus = "error" | "warning";

/** 选择器模式（多选/标签） */
export type SelectMode = "multiple" | "tags";

/** 选项接口 */
export interface SelectOption {
    /** 选项值 */
    value: string | number;
    /** 选项标签 */
    label: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义渲染内容（VNode 数组） */
    render?: () => any;
}

/** 子组件注册上下文类型 */
export interface SelectOptionContext {
    registerOption: (option: SelectOption) => void;
    unregisterOption: (value: string | number) => void;
}

/** Select 组件 Props */
export interface SelectProps {
    /** 选中的值 (v-model) - 单选时为 string | number，多选时为数组 */
    modelValue?: string | number | (string | number)[];
    /** 选项列表 */
    options?: SelectOption[];
    /** 选择框占位文本 */
    placeholder?: string;
    /** 选择框大小 */
    size?: SelectSize;
    /** 是否禁用 */
    disabled?: boolean;
    /** 设置校验状态 */
    status?: SelectStatus;
    /** 自定义类名 */
    class?: string;
    /** 设置 Select 的模式为多选或标签 */
    mode?: SelectMode;
    /** 是否支持搜索 */
    showSearch?: boolean;
    /** 是否支持清除 */
    allowClear?: boolean;
    /** 最多显示多少个 tag，响应式模式会对性能产生损耗 */
    maxTagCount?: number | "responsive";
    /** 隐藏 tag 时显示的内容 */
    maxTagPlaceholder?: string | ((omittedValues: SelectOption[]) => string);
    /** 搜索时过滤对应的 option 属性 */
    filterOption?: boolean | ((inputValue: string, option: SelectOption) => boolean);
    /** 搜索框占位文本 */
    searchPlaceholder?: string;
    /** 空数据时显示的内容 */
    notFoundContent?: string;
    /** 下拉菜单的最大高度 */
    listHeight?: number;
    /** 是否在选中项后清空搜索框 */
    autoClearSearchValue?: boolean;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 下拉面板额外 class */
    popupClass?: string;
    /** 是否有边框 */
    bordered?: boolean;
}

/** Select 组件 Emits */
export interface SelectEmits {
    /** 选中值变化 */
    (e: "update:modelValue", value: string | number | (string | number)[] | undefined): void;
    /** 选中值变化（带选项） */
    (e: "change", value: string | number | (string | number)[] | undefined, option: SelectOption | SelectOption[] | undefined): void;
    /** 搜索时触发 */
    (e: "search", value: string): void;
    /** 选中选项时触发 */
    (e: "select", value: string | number, option: SelectOption): void;
    /** 取消选中选项时触发（多选） */
    (e: "deselect", value: string | number, option: SelectOption): void;
    /** 清空时触发 */
    (e: "clear"): void;
    /** 获得焦点时触发 */
    (e: "focus", event: FocusEvent): void;
    /** 失去焦点时触发 */
    (e: "blur", event: FocusEvent): void;
}
