/**
 * Slider 组件类型定义
 */

export interface Mark {
    value: number;
    label?: string;
}

export interface SliderProps {
    /** 当前值（单值模式）或范围值（范围模式 [min, max]） */
    modelValue?: number | [number, number];
    /** 最小值 */
    min?: number;
    /** 最大值 */
    max?: number;
    /** 步长，取值必须大于 0，并且可被 (max - min) 整除 */
    step?: number;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否显示 Tooltip */
    tooltip?: boolean | "always";
    /** 范围选择模式 */
    range?: boolean;
    /** 是否垂直方向 */
    vertical?: boolean;
    /** 是否反向坐标轴 */
    reverse?: boolean;
    /** 刻度标记，key 的类型必须为 number 且取值在闭区间 [min, max] 内 */
    marks?: Record<number, string | Mark>;
    /** 是否只能拖拽到刻度上 */
    dots?: boolean;
    /** 是否包含 */
    included?: boolean;
    /** 格式化 Tooltip 内容 */
    tipFormatter?: ((value: number) => string) | null;
    /** 自定义类名 */
    class?: string;
}
