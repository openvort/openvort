<script setup lang="ts">
import { computed, inject, ref, useSlots, Transition, type ComputedRef, onMounted, onUnmounted, onBeforeUnmount, watch, nextTick } from "vue";
import { useField } from "vee-validate";
import { CheckCircleFilled, CloseCircleFilled, ExclamationCircleFilled, LoadingOutlined, QuestionOutlined } from "@/components/vort/icons";
import { Tooltip } from "@/components/vort/tooltip";

defineOptions({ name: "VortFormItem" });

/** Vort FormItem - 表单项组件 */

type ValidateStatus = "success" | "warning" | "error" | "validating" | "";
type RuleValidator = (rule: Record<string, unknown>, value: unknown, callback: (error?: Error | string) => void) => void;
type RuleRecord = Record<string, unknown> & { validator?: RuleValidator };

interface ColProps {
    /** 栅格占位格数 */
    span?: number;
    /** 栅格左侧的间隔格数 */
    offset?: number;
}

interface Props {
    /** 字段名，用于表单验证 */
    name?: string;
    /** label 标签的文本 */
    label?: string;
    /** 是否必填 */
    required?: boolean;
    /** 验证规则 */
    rules?: unknown[];
    /** 标签的长度，例如 '50px'。可以使用 'auto'（会覆盖 Form 的 labelWidth） */
    labelWidth?: string;
    /** label 标签布局（会覆盖 Form 的 labelCol） */
    labelCol?: ColProps;
    /** 控件布局（会覆盖 Form 的 wrapperCol） */
    wrapperCol?: ColProps;
    /** 是否显示 label 后面的冒号 */
    colon?: boolean;
    /** 提示信息 */
    help?: string;
    /** 额外的提示信息 */
    extra?: string;
    /** 校验状态 */
    validateStatus?: ValidateStatus;
    /** 是否展示校验状态图标 */
    hasFeedback?: boolean;
    /** 提示信息 */
    tooltip?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    required: false,
    hasFeedback: false
});

const slots = useSlots();

// 注入 Form 上下文
interface FormContext {
    layout: string;
    labelAlign: string;
    labelWidth?: string;
    autoLabelWidth?: string;
    labelCol?: ColProps;
    wrapperCol?: ColProps;
    colon: boolean;
    disabled: boolean;
    size: string;
    requiredMark: boolean | "optional";
    validateTrigger: string | string[];
    errors: Record<string, string>;
    // labelWidth="auto" 相关方法
    registerLabelWidth?: (id: string, width: number) => void;
    updateLabelWidth?: (id: string, width: number) => void;
    unregisterLabelWidth?: (id: string) => void;
    generateLabelId?: () => string;
}

const formContext = inject<ComputedRef<FormContext | undefined>>("formContext");

// Label 元素引用
const labelRef = ref<HTMLElement | null>(null);

// 当前 FormItem 的 label ID（用于注册宽度）
let labelId: string | null = null;

// 是否使用自动宽度
const isAutoLabelWidth = computed(() => {
    const width = props.labelWidth || formContext?.value?.labelWidth;
    return width === "auto";
});

// 测量并注册 label 宽度
const measureAndRegisterLabelWidth = () => {
    if (!isAutoLabelWidth.value || !labelRef.value) return;

    const ctx = formContext?.value;
    if (!ctx?.registerLabelWidth || !ctx?.generateLabelId) return;

    // 获取 label 内部文本元素的宽度
    const labelTextEl = labelRef.value.querySelector(".vort-form-item-label-text") as HTMLElement;
    if (!labelTextEl) return;

    const width = labelTextEl.offsetWidth;

    if (!labelId) {
        labelId = ctx.generateLabelId();
        ctx.registerLabelWidth(labelId, width);
    } else if (ctx.updateLabelWidth) {
        ctx.updateLabelWidth(labelId, width);
    }
};

// 注销 label 宽度
const unregisterLabel = () => {
    if (labelId && formContext?.value?.unregisterLabelWidth) {
        formContext.value.unregisterLabelWidth(labelId);
        labelId = null;
    }
};

onMounted(() => {
    // 延迟测量，确保 DOM 渲染完成
    nextTick(() => {
        measureAndRegisterLabelWidth();
    });
});

onBeforeUnmount(() => {
    unregisterLabel();
});

// 监听 label 变化，重新测量
watch(
    () => props.label,
    () => {
        nextTick(() => {
            measureAndRegisterLabelWidth();
        });
    }
);

// ===================== 自定义规则验证器 =====================
/**
 * 将 Ant Design 风格的 rules 转换为 vee-validate 验证函数
 * 支持的规则格式：
 * - { required: true, message: '必填' }
 * - { type: 'number', min: 0, message: '...' }
 * - { validator: (rule, value, callback) => void }
 */
const createRulesValidator = (rules: unknown[]) => {
    return async (value: unknown) => {
        if (!rules || rules.length === 0) return true;

        for (const rule of rules) {
            const r = rule as RuleRecord;

            // 自定义验证器
            if (typeof r.validator === "function") {
                const validator = r.validator;
                try {
                    await new Promise<void>((resolve, reject) => {
                        validator(r, value, (error?: Error | string) => {
                            if (error) {
                                reject(typeof error === "string" ? new Error(error) : error);
                            } else {
                                resolve();
                            }
                        });
                    });
                } catch (e: any) {
                    return e.message || "验证失败";
                }
                continue;
            }

            // 必填验证
            if (r.required) {
                const isEmpty = value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);
                if (isEmpty) {
                    return (r.message as string) || "此项为必填项";
                }
            }

            // 类型验证
            if (r.type === "number" && value !== undefined && value !== null && value !== "") {
                const numValue = Number(value);
                if (isNaN(numValue)) {
                    return (r.message as string) || "请输入数字";
                }
                if (typeof r.min === "number" && numValue < r.min) {
                    return (r.message as string) || `不能小于 ${r.min}`;
                }
                if (typeof r.max === "number" && numValue > r.max) {
                    return (r.message as string) || `不能大于 ${r.max}`;
                }
            }

            // 字符串长度验证
            if (r.type === "string" || (!r.type && typeof value === "string")) {
                const strValue = String(value || "");
                if (typeof r.min === "number" && strValue.length < r.min) {
                    return (r.message as string) || `长度不能小于 ${r.min}`;
                }
                if (typeof r.max === "number" && strValue.length > r.max) {
                    return (r.message as string) || `长度不能大于 ${r.max}`;
                }
            }

            // 正则验证
            if (r.pattern && value) {
                const regex = r.pattern instanceof RegExp ? r.pattern : new RegExp(r.pattern as string);
                if (!regex.test(String(value))) {
                    return (r.message as string) || "格式不正确";
                }
            }
        }

        return true;
    };
};

// 使用 vee-validate 的 useField（仅在有 name 时）
const fieldName = computed(() => props.name || "");
const rulesValidator = computed(() => {
    if (props.rules && Array.isArray(props.rules) && props.rules.length > 0) {
        return createRulesValidator(props.rules);
    }
    return undefined;
});

const {
    errorMessage,
    meta,
    validate: validateField
} = props.name
    ? useField(fieldName, rulesValidator, {
          validateOnValueUpdate: true
      })
    : { errorMessage: ref(""), meta: ref({}), validate: () => Promise.resolve({ valid: true }) };

// 计算最终的 labelWidth
const finalLabelWidth = computed(() => {
    const width = props.labelWidth || formContext?.value?.labelWidth;
    // 如果是 auto，返回 Form 计算的自动宽度
    if (width === "auto") {
        return formContext?.value?.autoLabelWidth || "auto";
    }
    return width;
});

// 计算最终的 labelCol
const finalLabelCol = computed(() => {
    return props.labelCol || formContext?.value?.labelCol || { span: 8 };
});

// 计算最终的 wrapperCol
const finalWrapperCol = computed(() => {
    return props.wrapperCol || formContext?.value?.wrapperCol || { span: 16 };
});

// 计算是否显示冒号
const showColon = computed(() => {
    // 如果 FormItem 明确设置了 colon，使用它
    if (props.colon !== undefined) return props.colon;
    // 否则使用 Form 的 colon 设置，默认为 true
    return formContext?.value?.colon ?? true;
});

// 计算布局
const layout = computed(() => formContext?.value?.layout || "horizontal");
const labelAlign = computed(() => formContext?.value?.labelAlign || "right");

// 验证状态
const validateStatus = computed<ValidateStatus>(() => {
    if (props.validateStatus) return props.validateStatus;
    if (!props.name) return "";

    // 从 form context 获取错误信息
    const contextError = formContext?.value?.errors?.[props.name];
    if (contextError || errorMessage.value) return "error";
    if ("value" in meta && (meta.value as { valid?: boolean })?.valid) return "success";
    return "";
});

// 验证消息
const validationMessage = computed(() => {
    if (props.help) return props.help;
    if (!props.name) return "";
    return formContext?.value?.errors?.[props.name] || errorMessage.value || "";
});

// 是否显示必填标记
const showRequired = computed(() => {
    const requiredMark = formContext?.value?.requiredMark ?? true;
    if (!requiredMark) return false;
    if (requiredMark === "optional") {
        // optional 模式下，非必填项显示"（可选）"
        return !props.required;
    }
    // 默认模式下，必填项显示 *
    return props.required;
});

// 是否为 optional 模式
const isOptionalMode = computed(() => {
    return formContext?.value?.requiredMark === "optional";
});

// 表单项样式
const formItemClasses = computed(() => {
    const classes = ["vort-form-item"];
    if (layout.value === "horizontal") classes.push("vort-form-item-horizontal");
    if (layout.value === "vertical") classes.push("vort-form-item-vertical");
    if (layout.value === "inline") classes.push("vort-form-item-inline");
    if (validateStatus.value === "error") classes.push("vort-form-item-has-error");
    if (validateStatus.value === "success") classes.push("vort-form-item-has-success");
    if (validateStatus.value === "warning") classes.push("vort-form-item-has-warning");
    if (validateStatus.value === "validating") classes.push("vort-form-item-is-validating");
    if (props.hasFeedback) classes.push("vort-form-item-has-feedback");
    if (props.class) classes.push(props.class);
    return classes;
});

// Label 样式
const labelClasses = computed(() => {
    const classes = ["vort-form-item-label"];
    if (labelAlign.value === "left") classes.push("vort-form-item-label-left");
    if (labelAlign.value === "right") classes.push("vort-form-item-label-right");
    return classes;
});

// 栅格宽度计算
const labelStyle = computed(() => {
    if (layout.value !== "horizontal") return {};

    // 如果是 auto 模式
    if (isAutoLabelWidth.value) {
        const autoWidth = formContext?.value?.autoLabelWidth;
        // 如果已经计算出了自动宽度，使用它
        if (autoWidth && autoWidth !== "auto") {
            return {
                width: autoWidth,
                flexShrink: 0
            };
        }
        // 否则让 label 以自然宽度渲染（用于测量）
        return {
            width: "auto",
            flexShrink: 0
        };
    }

    // 如果设置了固定的 labelWidth
    if (finalLabelWidth.value) {
        return {
            width: finalLabelWidth.value,
            flexShrink: 0
        };
    }

    // 否则使用栅格系统
    const span = finalLabelCol.value.span || 8;
    const offset = finalLabelCol.value.offset || 0;
    return {
        width: `${(span / 24) * 100}%`,
        marginLeft: offset ? `${(offset / 24) * 100}%` : undefined
    };
});

const wrapperStyle = computed(() => {
    if (layout.value !== "horizontal") return {};

    // 如果使用了 labelWidth（包括 auto），wrapper 自动占用剩余空间
    if (isAutoLabelWidth.value || finalLabelWidth.value) {
        return {
            flex: 1,
            minWidth: 0
        };
    }

    // 否则使用栅格系统
    const span = finalWrapperCol.value.span || 16;
    const offset = finalWrapperCol.value.offset || 0;
    return {
        width: `${(span / 24) * 100}%`,
        marginLeft: offset ? `${(offset / 24) * 100}%` : undefined
    };
});

// 错误信息行的样式（在水平布局下需要和控件区域对齐）
const explainRowStyle = computed(() => {
    if (layout.value !== "horizontal") return {};

    // 如果是 auto 模式
    if (isAutoLabelWidth.value) {
        const autoWidth = formContext?.value?.autoLabelWidth;
        if (autoWidth && autoWidth !== "auto") {
            return {
                marginLeft: autoWidth
            };
        }
        // auto 还没计算出来时，不设置左边距
        return {};
    }

    // 如果设置了固定的 labelWidth
    if (finalLabelWidth.value) {
        return {
            marginLeft: finalLabelWidth.value
        };
    }

    // 否则使用栅格系统计算
    const labelSpan = finalLabelCol.value.span || 8;
    const labelOffset = finalLabelCol.value.offset || 0;
    const wrapperOffset = finalWrapperCol.value.offset || 0;
    // 错误信息行的左边距 = label 宽度 + label offset + wrapper offset
    const totalOffset = labelSpan + labelOffset + wrapperOffset;
    return {
        marginLeft: `${(totalOffset / 24) * 100}%`
    };
});

// 反馈图标
const feedbackIcon = computed(() => {
    if (!props.hasFeedback) return null;
    switch (validateStatus.value) {
        case "success":
            return CheckCircleFilled;
        case "error":
            return CloseCircleFilled;
        case "warning":
            return ExclamationCircleFilled;
        case "validating":
            return LoadingOutlined;
        default:
            return null;
    }
});

// 反馈图标颜色
const feedbackIconClass = computed(() => {
    switch (validateStatus.value) {
        case "success":
            return "vort-form-item-feedback-success";
        case "error":
            return "vort-form-item-feedback-error";
        case "warning":
            return "vort-form-item-feedback-warning";
        case "validating":
            return "vort-form-item-feedback-validating";
        default:
            return "";
    }
});
</script>

<template>
    <div :class="formItemClasses">
        <!-- Label 区域 -->
        <div v-if="label || $slots.label" ref="labelRef" :class="labelClasses" :style="labelStyle">
            <label :for="name" class="vort-form-item-label-text">
                <!-- 必填标记（非 optional 模式） -->
                <span v-if="props.required && !isOptionalMode" class="vort-form-item-required-mark">*</span>
                <!-- Label 文本 -->
                <slot name="label">{{ label }}</slot>
                <!-- 可选标记（optional 模式下的非必填项） -->
                <span v-if="!props.required && isOptionalMode" class="vort-form-item-optional-mark">（可选）</span>
                <!-- 冒号 -->
                <span v-if="showColon" class="vort-form-item-colon">:</span>
                <!-- Tooltip -->
                <Tooltip v-if="tooltip" placement="bottom" style="padding: 12px 16px">
                    <template #title>{{ tooltip }}</template>
                    <span class="vort-form-item-tooltip">
                        <QuestionOutlined />
                    </span>
                </Tooltip>
            </label>
        </div>

        <!-- 控件区域 -->
        <div class="vort-form-item-control" :style="wrapperStyle">
            <div class="vort-form-item-control-input">
                <div class="vort-form-item-control-input-content">
                    <slot />
                </div>
                <!-- 反馈图标 -->
                <span v-if="hasFeedback && feedbackIcon" class="vort-form-item-feedback-icon" :class="feedbackIconClass">
                    <component :is="feedbackIcon" :class="{ 'animate-spin': validateStatus === 'validating' }" />
                </span>
            </div>

            <!-- 额外信息 -->
            <div v-if="extra || $slots.extra" class="vort-form-item-extra">
                <slot name="extra">{{ extra }}</slot>
            </div>
        </div>

        <!-- 错误/帮助信息  -->
        <div v-if="layout !== 'inline'" class="vort-form-item-explain-row" :style="explainRowStyle">
            <Transition name="vort-form-explain">
                <div v-if="validationMessage" class="vort-form-item-explain">
                    <div
                        class="vort-form-item-explain-text"
                        :class="{
                            'vort-form-item-explain-error': validateStatus === 'error',
                            'vort-form-item-explain-warning': validateStatus === 'warning',
                            'vort-form-item-explain-success': validateStatus === 'success'
                        }"
                    >
                        {{ validationMessage }}
                    </div>
                </div>
            </Transition>
        </div>
    </div>
</template>

<style scoped>
.vort-form-item {
    margin-bottom: 24px;
    position: relative;
}

/* 水平布局 */
.vort-form-item-horizontal {
    display: flex;
    flex-wrap: wrap;
}

.vort-form-item-horizontal .vort-form-item-label {
    flex-shrink: 0;
}

.vort-form-item-horizontal .vort-form-item-control {
    flex: 1;
    min-width: 0;
}

/* 垂直布局 */
.vort-form-item-vertical {
    display: flex;
    flex-direction: column;
}

.vort-form-item-vertical .vort-form-item-label {
    padding: 0 0 8px;
    line-height: 1.5;
    text-align: left !important;
    justify-content: flex-start !important;
}

/* 行内布局 */
.vort-form-item-inline {
    display: inline-flex;
    flex-wrap: nowrap;
    margin-right: 16px;
    margin-bottom: 0;
}

.vort-form-item-inline .vort-form-item-label {
    flex-shrink: 0;
}

/* Label 样式 */
.vort-form-item-label {
    display: flex;
    align-items: flex-start;
    color: var(--vort-text);
    font-size: 14px;
    height: 32px;
    box-sizing: border-box;
    white-space: nowrap;
    overflow: hidden;
}

.vort-form-item-label-text {
    display: inline-flex;
    align-items: center;
    height: 32px;
    line-height: 32px;
    position: relative;
}

.vort-form-item-label-left {
    justify-content: flex-start;
}

.vort-form-item-label-left .vort-form-item-label-text {
    padding-right: 12px;
}

.vort-form-item-label-right {
    justify-content: flex-end;
}

.vort-form-item-label-right .vort-form-item-label-text {
    padding-right: 12px;
}

/* 必填标记 - Ant Design 样式 */
.vort-form-item-required-mark {
    display: inline-block;
    margin-inline-end: 4px;
    color: var(--vort-error);
    font-size: 14px;
    font-family: SimSun, sans-serif;
    line-height: 1;
}

/* 可选标记 */
.vort-form-item-optional-mark {
    color: var(--vort-text-quaternary);
    font-size: 14px;
    margin-inline-start: 4px;
}

/* 冒号 - Ant Design 样式：紧跟文字，无间距 */
.vort-form-item-colon {
    position: relative;
    margin-block: 0;
    margin-inline-start: 2px;
    margin-inline-end: 8px;
}

/* Tooltip */
.vort-form-item-tooltip {
    color: var(--vort-text-quaternary);
    margin-inline-start: 4px;
    display: inline-flex;
    align-items: center;
}

.vort-form-item-tooltip:hover {
    color: var(--vort-text-secondary);
}

/* 控件区域 */
.vort-form-item-control {
    display: flex;
    flex-direction: column;
    flex-grow: 1;
}

.vort-form-item-control-input {
    position: relative;
    display: flex;
    align-items: center;
    min-height: 32px;
}

.vort-form-item-control-input-content {
    flex: auto;
    max-width: 100%;
}

/* 反馈图标 */
.vort-form-item-feedback-icon {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 14px;
    line-height: 1;
    pointer-events: none;
    z-index: 1;
}

/* 错误/帮助信息行 - Ant Design 风格
 * 放在表单项主行之外，使用负 margin 占用 margin-bottom 空间
 * 这样错误信息出现时不会挤占其他表单项的空间
 */
.vort-form-item-explain-row {
    /* 占据整行宽度，让它换行显示 */
    width: 100%;
    flex-basis: 100%;
    /* 预留高度用于显示错误信息 */
    min-height: 24px;
    /* 使用负 margin 占用表单项的 margin-bottom 空间 */
    margin-top: 0;
    margin-bottom: -24px;
}
.vort-form-item {
    .vort-form-item {
        margin-bottom: 0;
        .vort-form-item-explain-row {
            margin-left: 1px !important;
            position: absolute;
            top: 100%;
        }
    }
}

.vort-form-item-explain {
    font-size: 14px;
    line-height: 1.5715;
    color: var(--vort-text-secondary);
}

.vort-form-item-explain-text {
    color: var(--vort-error);
}

.vort-form-item-explain-error {
    color: var(--vort-error);
}

.vort-form-item-explain-warning {
    color: var(--vort-warning);
}

.vort-form-item-explain-success {
    color: var(--vort-success);
}

/* 反馈图标颜色 */
.vort-form-item-feedback-success {
    color: var(--vort-success);
}

.vort-form-item-feedback-error {
    color: var(--vort-error);
}

.vort-form-item-feedback-warning {
    color: var(--vort-warning);
}

.vort-form-item-feedback-validating {
    color: var(--vort-primary);
}

/* 错误信息展示动画 */
.vort-form-explain-enter-active,
.vort-form-explain-leave-active {
    transition:
        opacity 0.15s ease-in-out,
        transform 0.15s ease-in-out;
}

.vort-form-explain-enter-from,
.vort-form-explain-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

/* 额外信息 */
.vort-form-item-extra {
    color: var(--vort-form-extra-color);
    font-size: 12px;
    line-height: 1.5715;
    padding-top: 2px;
}

/* 校验状态样式 */
.vort-form-item-has-error :deep(input),
.vort-form-item-has-error :deep(.vort-input),
.vort-form-item-has-error :deep(.vort-input-wrapper),
.vort-form-item-has-error :deep(.vort-input-number),
.vort-form-item-has-error :deep(.vort-select-trigger) {
    border-color: var(--vort-error) !important;
}

.vort-form-item-has-error :deep(input:focus),
.vort-form-item-has-error :deep(.vort-input:focus-within),
.vort-form-item-has-error :deep(.vort-input-wrapper:focus-within),
.vort-form-item-has-error :deep(.vort-input-number:focus-within),
.vort-form-item-has-error :deep(.vort-select-trigger:focus) {
    border-color: var(--vort-error) !important;
    box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.06) !important;
}

.vort-form-item-has-warning :deep(input),
.vort-form-item-has-warning :deep(.vort-input),
.vort-form-item-has-warning :deep(.vort-input-wrapper),
.vort-form-item-has-warning :deep(.vort-input-number),
.vort-form-item-has-warning :deep(.vort-select-trigger) {
    border-color: var(--vort-warning) !important;
}

.vort-form-item-has-warning :deep(input:focus),
.vort-form-item-has-warning :deep(.vort-input:focus-within),
.vort-form-item-has-warning :deep(.vort-input-wrapper:focus-within),
.vort-form-item-has-warning :deep(.vort-input-number:focus-within),
.vort-form-item-has-warning :deep(.vort-select-trigger:focus) {
    border-color: var(--vort-warning) !important;
    box-shadow: 0 0 0 2px rgba(250, 173, 20, 0.1) !important;
}

.vort-form-item-has-success :deep(input),
.vort-form-item-has-success :deep(.vort-input),
.vort-form-item-has-success :deep(.vort-input-wrapper),
.vort-form-item-has-success :deep(.vort-input-number),
.vort-form-item-has-success :deep(.vort-select-trigger) {
    border-color: var(--vort-success) !important;
}

/* 加载动画 */
@keyframes spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

.animate-spin {
    animation: spin 1s linear infinite;
}
</style>
