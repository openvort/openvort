<script setup lang="ts">
import { computed, provide, watch, ref, onMounted, onUnmounted, nextTick } from "vue";
import { useForm } from "vee-validate";
import { toTypedSchema } from "@vee-validate/zod";
import type { ZodType } from "zod";

// 生成唯一 ID 的计数器
let formItemIdCounter = 0;

defineOptions({ name: "VortForm" });

/** Vort Form - 表单组件 */

type FormLayout = "horizontal" | "vertical" | "inline";
type FormSize = "large" | "middle" | "small";
type LabelAlign = "left" | "right";
type ValidateTrigger = "change" | "blur" | Array<"change" | "blur">;

interface ColProps {
    /** 栅格占位格数 */
    span?: number;
    /** 栅格左侧的间隔格数 */
    offset?: number;
}

interface Props {
    /** 表单数据对象 */
    model?: Record<string, unknown>;
    /** 表单验证规则（支持 zod schema 或自定义规则对象） */
    rules?: ZodType | Record<string, unknown>;
    /** 表单布局 */
    layout?: FormLayout;
    /** label 标签的文本对齐方式 */
    labelAlign?: LabelAlign;
    /** 标签的长度，例如 '50px'。作为 Form 直接子元素的 form-item 会继承该值。可以使用 'auto' */
    labelWidth?: string;
    /** label 标签布局 */
    labelCol?: ColProps;
    /** 控件布局 */
    wrapperCol?: ColProps;
    /** 配置 Form.Item 的 colon 的默认值 */
    colon?: boolean;
    /** 是否禁用该表单内的所有组件 */
    disabled?: boolean;
    /** 设置字段组件的尺寸 */
    size?: FormSize;
    /** 统一设置字段触发验证的时机 */
    validateTrigger?: ValidateTrigger;
    /** 是否显示必填标记 */
    requiredMark?: boolean | "optional";
    /** 是否启用响应式布局（小屏幕自动切换为垂直布局） */
    responsive?: boolean;
    /** 响应式断点，单位 px，默认 576（对应 sm 断点） */
    responsiveBreakpoint?: number;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    layout: "horizontal",
    labelAlign: "right",
    colon: true,
    disabled: false,
    size: "middle",
    validateTrigger: "change",
    requiredMark: true,
    responsive: true,
    responsiveBreakpoint: 576
});

// 响应式布局状态：是否处于小屏幕模式
const isSmallScreen = ref(false);

// 实际使用的布局（考虑响应式）
const effectiveLayout = computed<FormLayout>(() => {
    // 如果启用响应式且当前是小屏幕，且原布局是 horizontal，则切换为 vertical
    if (props.responsive && isSmallScreen.value && props.layout === "horizontal") {
        return "vertical";
    }
    return props.layout;
});

// 媒体查询监听器
let mediaQueryList: MediaQueryList | null = null;

const handleMediaChange = (e: MediaQueryListEvent | MediaQueryList) => {
    isSmallScreen.value = !e.matches;
};

onMounted(() => {
    if (props.responsive && typeof window !== "undefined") {
        // 创建媒体查询
        mediaQueryList = window.matchMedia(`(min-width: ${props.responsiveBreakpoint}px)`);
        // 初始化状态
        handleMediaChange(mediaQueryList);
        // 监听变化
        mediaQueryList.addEventListener("change", handleMediaChange);
    }
});

onUnmounted(() => {
    if (mediaQueryList) {
        mediaQueryList.removeEventListener("change", handleMediaChange);
        mediaQueryList = null;
    }
});

const emit = defineEmits<{
    /** 表单提交且验证通过时触发 */
    finish: [values: Record<string, unknown>];
    /** 表单提交且验证失败时触发 */
    finishFailed: [errors: Record<string, string>];
    /** 字段值变更时触发 */
    valuesChange: [changedValues: Record<string, unknown>, allValues: Record<string, unknown>];
}>();

// 解析验证 schema
const validationSchema = computed(() => {
    if (!props.rules) return undefined;
    // 如果是 zod schema，转换为 vee-validate schema
    if (typeof props.rules === "object" && "_def" in props.rules) {
        return toTypedSchema(props.rules as ZodType);
    }
    return undefined;
});

// 使用 vee-validate 的 useForm
const { handleSubmit, resetForm, setFieldValue, setFieldError, validate, errors, values } = useForm({
    validationSchema: validationSchema.value,
    initialValues: props.model
});

/**
 * 递归遍历对象，生成带路径的键值对
 * @param obj 要遍历的对象
 * @param prefix 路径前缀
 * @param result 结果数组
 */
const isPlainObject = (val: unknown): val is Record<string, unknown> => {
    return Object.prototype.toString.call(val) === "[object Object]";
};

const flattenObject = (obj: unknown, prefix = "", result: Array<{ path: string; value: unknown }> = []) => {
    if (obj === null || obj === undefined) {
        result.push({ path: prefix, value: obj });
        return result;
    }

    // Date / 非纯对象：作为“叶子值”处理（否则会被当成 object 递归，导致字段值无法同步进 vee-validate）
    if (obj instanceof Date || (typeof obj === "object" && !Array.isArray(obj) && !isPlainObject(obj))) {
        result.push({ path: prefix, value: obj });
        return result;
    }

    if (Array.isArray(obj)) {
        // 数组：遍历每个元素
        obj.forEach((item, index) => {
            const path = prefix ? `${prefix}[${index}]` : `[${index}]`;
            if (typeof item === "object" && item !== null) {
                flattenObject(item, path, result);
            } else {
                result.push({ path, value: item });
            }
        });
    } else if (typeof obj === "object" && isPlainObject(obj)) {
        // 对象：遍历每个属性
        for (const [key, value] of Object.entries(obj)) {
            const path = prefix ? `${prefix}.${key}` : key;
            if (typeof value === "object" && value !== null) {
                flattenObject(value, path, result);
            } else {
                result.push({ path, value });
            }
        }
    } else {
        result.push({ path: prefix, value: obj });
    }

    return result;
};

/**
 * 从 vee-validate values 中按路径获取值
 */
const getValueByPath = (obj: Record<string, unknown>, path: string): unknown => {
    // 处理路径如 "promotionTypeData[0].minAmount"
    const keys = path.replace(/\[(\d+)\]/g, ".$1").split(".");
    let current: unknown = obj;
    for (const key of keys) {
        if (current === null || current === undefined) return undefined;
        current = (current as Record<string, unknown>)[key];
    }
    return current;
};

// 监听 model 变化，同步到 vee-validate（实现双向绑定校验）
watch(
    () => props.model,
    (newModel) => {
        if (newModel) {
            // 递归遍历所有嵌套字段
            const flatFields = flattenObject(newModel);
            for (const { path, value } of flatFields) {
                // 只同步发生变化的字段
                const currentValue = getValueByPath(values, path);
                if (currentValue !== value) {
                    setFieldValue(path, value);
                }
            }
        }
    },
    { deep: true }
);

// 表单样式
const formClasses = computed(() => {
    const classes = ["vort-form"];
    if (effectiveLayout.value === "horizontal") classes.push("vort-form-horizontal");
    if (effectiveLayout.value === "vertical") classes.push("vort-form-vertical");
    if (effectiveLayout.value === "inline") classes.push("vort-form-inline");
    if (props.class) classes.push(props.class);
    return classes;
});

// ==================== labelWidth="auto" 自动计算最大宽度逻辑 ====================

// 存储所有 FormItem 注册的 label 宽度
const labelWidthMap = ref<Map<string, number>>(new Map());

// 计算是否启用自动宽度
const isAutoLabelWidth = computed(() => props.labelWidth === "auto");

// 计算所有 label 的最大宽度
const autoLabelWidth = computed(() => {
    if (!isAutoLabelWidth.value) return undefined;
    const widths = Array.from(labelWidthMap.value.values());
    if (widths.length === 0) return "auto";
    const maxWidth = Math.max(...widths);
    return maxWidth ? `${maxWidth}px` : "auto";
});

// 生成唯一 ID
const generateLabelId = () => {
    return `form-item-label-${++formItemIdCounter}`;
};

// 注册 label 宽度
const registerLabelWidth = (id: string, width: number) => {
    labelWidthMap.value.set(id, width);
};

// 更新 label 宽度
const updateLabelWidth = (id: string, width: number) => {
    labelWidthMap.value.set(id, width);
};

// 注销 label 宽度
const unregisterLabelWidth = (id: string) => {
    labelWidthMap.value.delete(id);
};

// ==================== 提供给子组件的上下文 ====================

// 提供给子组件的上下文（使用 computed 保持响应性）
const formContext = computed(() => ({
    layout: effectiveLayout.value,
    labelAlign: props.labelAlign,
    labelWidth: props.labelWidth,
    autoLabelWidth: autoLabelWidth.value,
    labelCol: props.labelCol,
    wrapperCol: props.wrapperCol,
    colon: props.colon,
    disabled: props.disabled,
    size: props.size,
    requiredMark: props.requiredMark,
    validateTrigger: props.validateTrigger,
    errors: errors.value,
    setFieldValue,
    setFieldError,
    // labelWidth="auto" 相关方法
    registerLabelWidth,
    updateLabelWidth,
    unregisterLabelWidth,
    generateLabelId
}));

provide("formContext", formContext);

// 表单提交
const onSubmit = handleSubmit(
    (formValues) => {
        emit("finish", formValues);
    },
    (validationErrors) => {
        const errorMap: Record<string, string> = {};
        for (const key in validationErrors.errors) {
            errorMap[key] = validationErrors.errors[key] || "";
        }
        emit("finishFailed", errorMap);
    }
);

// 重置表单
const resetFields = () => {
    resetForm({
        values: props.model
    });
};

// 验证表单
const validateFields = async (names?: string | string[]) => {
    const result = await validate();
    if (names) {
        const nameArr = Array.isArray(names) ? names : [names];
        const filteredErrors: Record<string, string> = {};
        for (const name of nameArr) {
            if (errors.value[name]) {
                filteredErrors[name] = errors.value[name] || "";
            }
        }
        return {
            valid: Object.keys(filteredErrors).length === 0,
            errors: filteredErrors
        };
    }
    return result;
};

/**
 * - 校验通过：resolve(true)
 * - 校验失败：reject({ errorFields })，不提供 message，避免业务层误弹 toast
 */
const validateCompat = async (names?: string | string[]) => {
    const result = (await validateFields(names)) as unknown as { valid?: boolean; errors?: Record<string, string> };
    const isValid = result?.valid ?? true;
    if (!isValid) {
        return Promise.reject({
            errorFields: result?.errors || {}
        });
    }
    return true;
};

// 清除验证
const clearValidate = (names?: string | string[]) => {
    if (names) {
        const nameArr = Array.isArray(names) ? names : [names];
        for (const name of nameArr) {
            setFieldError(name, "");
        }
    } else {
        for (const key in errors.value) {
            setFieldError(key, "");
        }
    }
};

// 设置字段值
const setFieldsValue = (fieldsValue: Record<string, unknown>) => {
    for (const [key, value] of Object.entries(fieldsValue)) {
        setFieldValue(key, value);
    }
};

// 获取字段值
const getFieldsValue = (names?: string | string[]) => {
    if (names) {
        const nameArr = Array.isArray(names) ? names : [names];
        const result: Record<string, unknown> = {};
        for (const name of nameArr) {
            result[name] = values[name];
        }
        return result;
    }
    return { ...values };
};

// 暴露方法
defineExpose({
    /** 提交表单 */
    submit: onSubmit,
    /** 重置表单 */
    resetFields,
    /** 兼容：validate() */
    validate: validateCompat,
    /** 验证表单 */
    validateFields,
    /** 清除验证 */
    clearValidate,
    /** 设置字段值 */
    setFieldsValue,
    /** 获取字段值 */
    getFieldsValue
});
</script>

<template>
    <form :class="formClasses" @submit.prevent="onSubmit">
        <slot />
    </form>
</template>

<style scoped>
.vort-form {
    font-size: 14px;
    color: var(--vort-text);
}

/* 水平布局 - 样式由 FormItem 处理 */

/* 垂直布局 - 样式由 FormItem 处理 */

/* 行内布局 */
.vort-form-inline {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
}

.vort-form-inline :deep(.vort-form-item) {
    margin-bottom: 0;
}

/* 响应式布局过渡效果 */
.vort-form :deep(.vort-form-item) {
    transition:
        flex-direction 0.2s ease,
        padding 0.2s ease;
}

.vort-form :deep(.vort-form-item-label) {
    transition:
        width 0.2s ease,
        padding 0.2s ease,
        text-align 0.2s ease,
        justify-content 0.2s ease;
}

.vort-form :deep(.vort-form-item-control) {
    transition: width 0.2s ease;
}
</style>
