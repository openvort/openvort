/**
 * Tag 组件类型定义
 */

// ==================== Tag 组件 ====================

/** 预设状态颜色 */
export type TagPresetStatusColor = "success" | "processing" | "error" | "warning" | "default";

/** 预设颜色名 */
export type TagPresetColor = "magenta" | "red" | "volcano" | "orange" | "gold" | "lime" | "green" | "cyan" | "teal" | "blue" | "geekblue" | "purple";

/** 标签颜色类型 */
export type TagColor = TagPresetStatusColor | TagPresetColor | string;

/** 标签尺寸 */
export type TagSize = "small" | "default";

/** Tag 组件 Props */
export interface TagProps {
    /** 标签色：可以是预设颜色或自定义颜色值 */
    color?: TagColor;
    /** 标签是否可关闭 */
    closable?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 简易样式（无背景色，仅文字和边框） */
    plain?: boolean;
    /** 白色背景 */
    white?: boolean;
    /** 实心模式（color 作为背景和边框色，文字白色） */
    solid?: boolean;
    /** 尺寸 */
    size?: TagSize;
    /** 自定义类名 */
    class?: string;
}

/** Tag 组件 Emits */
export interface TagEmits {
    /** 关闭时触发 */
    (e: "close", event: MouseEvent): void;
}

// ==================== CheckableTag 组件 ====================

/** CheckableTag 组件 Props */
export interface CheckableTagProps {
    /** 设置标签的选中状态 */
    checked?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** CheckableTag 组件 Emits */
export interface CheckableTagEmits {
    /** 点击标签时触发 */
    (e: "change", checked: boolean): void;
    /** v-model 支持 */
    (e: "update:checked", checked: boolean): void;
}

// ==================== DraggableTags 组件 ====================

/** 标签项数据 */
export interface TagItem {
    /** 标签唯一标识 */
    key: string | number;
    /** 标签内容 */
    label: string;
    /** 标签颜色 */
    color?: string;
    /** 是否可关闭 */
    closable?: boolean;
}

/** DraggableTags 组件 Props */
export interface DraggableTagsProps {
    /** 标签数据列表 */
    modelValue: TagItem[];
    /** 是否可拖拽 */
    draggable?: boolean;
    /** 是否显示拖拽提示图标 */
    showDragIcon?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 自定义类名 */
    class?: string;
}

/** DraggableTags 组件 Emits */
export interface DraggableTagsEmits {
    /** 标签顺序变化 */
    (e: "update:modelValue", value: TagItem[]): void;
    /** 拖拽结束 */
    (e: "dragEnd", value: TagItem[]): void;
    /** 标签关闭 */
    (e: "close", item: TagItem, index: number): void;
}
