import type { FloatingPlacement } from "@/components/vort";

/**
 * PopForm 输入类型
 * - input: 普通文本输入
 * - textarea: 多行文本输入
 * - integer: 整数输入
 * - decimal: 小数/金额输入
 */
export type PopFormInputType = "input" | "textarea" | "integer" | "decimal";

/**
 * PopForm 组件 Props
 */
export interface PopFormProps {
    // ========== 核心属性 ==========
    /** 原始值（双向绑定） */
    orgValue?: string | number;
    /** 输入类型：input/textarea/integer，默认 input */
    type?: PopFormInputType;
    /** 字段标签 */
    label?: string;
    /** 额外说明文字 */
    extra?: string;

    // ========== 验证属性 ==========
    /** 最小长度 */
    min?: number;
    /** 最大长度 */
    max?: number;
    /** 固定长度 */
    len?: number;
    /** 最小数值 */
    minNum?: number;
    /** 最大数值 */
    maxNum?: number;

    // ========== API 属性 ==========
    /** 传递给 API 的参数 */
    params?: Record<string, unknown>;
    /** 提交 API 函数 */
    requestApi?: (params: Record<string, unknown>) => Promise<unknown>;

    // ========== Popconfirm 属性 ==========
    /** 气泡框位置，默认 top */
    placement?: FloatingPlacement;
    /** 确认按钮文字，默认 "确定" */
    okText?: string;
    /** 取消按钮文字，默认 "取消" */
    cancelText?: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 输入框宽度，默认 200 */
    inputWidth?: number | string;
    /** 弹窗宽度，默认 320 */
    width?: number | string;
}

/**
 * PopForm 组件 Emits
 */
export interface PopFormEmits {
    /** 原始值更新 */
    "update:orgValue": [value: string | number];
    /** 提交成功后触发 */
    ok: [value: string | number];
    /** 取消时触发 */
    cancel: [];
}
