/**
 * Button 组件类型定义
 */

/** 按钮变体（样式类型） */
export type ButtonVariant = "primary" | "default" | "dashed" | "text" | "link" | "plain" | "soft";

/** 按钮尺寸 */
export type ButtonSize = "large" | "middle" | "small";

/** 按钮形状 */
export type ButtonShape = "default" | "round" | "circle";

/** 按钮原生 type 属性 */
export type ButtonHTMLType = "button" | "submit" | "reset";

/** Button 组件 Props */
export interface ButtonProps {
    /** 按钮变体（样式类型） */
    variant?: ButtonVariant;
    /** 按钮类型（variant 的别名，方便习惯 type="primary" 的用户） */
    type?: ButtonVariant;
    /** 按钮尺寸 */
    size?: ButtonSize;
    /** 按钮形状 */
    shape?: ButtonShape;
    /** 是否为危险按钮 */
    danger?: boolean;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否加载中 */
    loading?: boolean;
    /** 是否为幽灵按钮（背景透明） */
    ghost?: boolean;
    /** 将按钮宽度调整为其父宽度 */
    block?: boolean;
    /** 设置按钮的图标组件（仅图标按钮） */
    icon?: boolean;
    /** 原生 type 属性 */
    htmlType?: ButtonHTMLType;
    /** 自定义类名 */
    class?: string;
}

/** Button 组件 Emits */
export interface ButtonEmits {
    /** 点击事件 */
    (e: "click", event: MouseEvent): void;
}
