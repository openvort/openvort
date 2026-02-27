/**
 * Switch 组件类型定义
 */

/** 开关尺寸 */
export type SwitchSize = "default" | "small";

/** 开关值类型 */
export type SwitchValue = boolean | number | string;

/** Switch 组件 Props */
export interface SwitchProps {
    /** 指定当前值（v-model:checked），支持 boolean / number / string */
    checked?: SwitchValue;
    /** 是否禁用 */
    disabled?: boolean;
    /** 加载中 */
    loading?: boolean;
    /** 开关大小 */
    size?: SwitchSize;
    /** 选中时对应的值（启用值映射模式） */
    checkedValue?: SwitchValue;
    /** 非选中时对应的值（启用值映射模式） */
    uncheckedValue?: SwitchValue;
    /** 选中时的内容 */
    checkedChildren?: string;
    /** 非选中时的内容 */
    uncheckedChildren?: string;
    /** 自定义类名 */
    class?: string;
    /** 切换前的钩子，返回 false 或 Promise reject 会阻止切换 */
    beforeChange?: () => Promise<boolean> | boolean;
}

/** Switch 组件 Emits */
export interface SwitchEmits {
    /** 更新选中状态 */
    (e: "update:checked", value: SwitchValue): void;
    /** 状态变化事件 */
    (e: "change", value: SwitchValue, event: MouseEvent): void;
}
