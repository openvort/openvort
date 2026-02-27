<script setup lang="ts">
import { ref, computed, watch, nextTick } from "vue";
import type { FloatingPlacement } from "@/components/vort/composables";
import type { PopFormInputType } from "./types";
import { message } from "@/components/vort/message";
import { Popconfirm } from "@/components/vort/popconfirm";

defineOptions({ name: "PopForm" });

/**
 * PopForm - 气泡表单快速编辑组件
 *
 * 点击触发器弹出气泡框，支持快速编辑字段值
 * 基于 Popconfirm 组件实现
 */

interface Props {
    // ========== 核心属性 ==========
    /** 原始值（双向绑定） */
    orgValue?: string | number;
    /** 输入类型：input/textarea/integer/decimal，默认 input */
    type?: PopFormInputType;
    /** 字段标签 */
    label?: string;
    /** 额外说明文字 */
    extra?: string;
    /** 是否为价格类型（decimal时使用，精度为2位小数） */
    isPrice?: boolean;

    // ========== 验证属性 ==========
    /** 是否必填 */
    required?: boolean;
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
    /** 气泡框位置，默认 bottom */
    placement?: FloatingPlacement;
    /** 确认按钮文字 */
    okText?: string;
    /** 取消按钮文字 */
    cancelText?: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 输入框宽度 */
    inputWidth?: number | string;
    /** 弹窗宽度，默认 320 */
    width?: number | string;
    /** 自定义类名 */
    class?: string;

    // ========== 兼容旧版 PopFormElm ==========
    /** 是否直接确认：不调用 requestApi，只更新 orgValue 并触发 ok 事件 */
    isDirect?: boolean;
    /** 是否 hover 模式：hover 时才展示编辑图标；非 hover 模式用于表格等需要居中展示的场景 */
    isHover?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    type: "input",
    label: "",
    extra: "",
    required: true,
    params: () => ({}),
    placement: "bottom",
    okText: "确定",
    cancelText: "取消",
    disabled: false,
    inputWidth: 200,
    width: 320,
    isDirect: false,
    isHover: true
});

const emit = defineEmits<{
    "update:orgValue": [value: string | number];
    ok: [value: string | number];
    cancel: [];
}>();

// 状态
const loading = ref(false);
const inputValue = ref<string | number>("");
const errorMessage = ref(""); // 错误信息
const popconfirmRef = ref<InstanceType<typeof Popconfirm> | null>(null);
const inputRef = ref<{ focus: () => void } | null>(null);

// 计算输入框样式
const inputWidthStyle = computed(() => {
    const w = props.inputWidth;
    return typeof w === "number" ? `${w}px` : w;
});

// 计算显示的 extra 提示文字
const displayExtra = computed(() => {
    // 如果用户已提供 extra，直接使用
    if (props.extra) {
        return props.extra;
    }

    const label = props.label || "内容";

    // 数字范围提示
    if (props.minNum !== undefined && props.maxNum !== undefined && props.minNum > 0 && props.maxNum > 0) {
        return `请输入${props.minNum}-${props.maxNum}之间的数字`;
    }

    // 固定长度提示
    if (props.len !== undefined && props.len > 0) {
        return `请输入${props.len}个字符的${label}`;
    }

    // 最大长度提示
    if (props.max !== undefined && props.max > 0) {
        return `请输入不超过${props.max}个字符的${label}`;
    }

    // 最小长度提示
    if (props.min !== undefined && props.min > 0) {
        return `请输入不少于${props.min}个字符的${label}`;
    }

    return "";
});

// 同步原始值到输入值
watch(
    () => props.orgValue,
    (val) => {
        inputValue.value = val ?? "";
    },
    { immediate: true }
);

// 处理打开后聚焦
const handleAfterOpen = () => {
    // 重置输入值为原始值
    inputValue.value = props.orgValue ?? "";
    // 清除错误信息
    errorMessage.value = "";
    nextTick(() => {
        inputRef.value?.focus();
    });
};

// 是否为数字类型
const isNumberType = computed(() => props.type === "integer" || props.type === "decimal");

// 验证输入
const validate = (): string | null => {
    const value = String(inputValue.value).trim();
    const label = props.label || "输入";

    // 必填验证
    if (props.required) {
        // 字符串类型：空字符串或纯空格
        if (!isNumberType.value && value === "") {
            return `请输入${label}`;
        }
        // 数字类型：空、0、NaN
        if (isNumberType.value) {
            const numValue = Number(inputValue.value);
            if (inputValue.value === "" || inputValue.value === null || isNaN(numValue)) {
                return `请输入${label}`;
            }
        }
    }

    // 固定长度验证
    if (props.len !== undefined && props.len > 0 && value.length !== props.len) {
        return `${label}长度必须为 ${props.len} 个字符`;
    }

    // 最大长度验证
    if (props.max !== undefined && props.max > 0 && value.length > props.max) {
        return `${label}长度不能超过 ${props.max} 个字符`;
    }

    // 最小长度验证
    if (props.min !== undefined && props.min > 0 && value.length < props.min) {
        return `${label}长度不能少于 ${props.min} 个字符`;
    }

    // 整数类型验证
    if (props.type === "integer") {
        if (!/^-?\d*$/.test(value)) {
            return `${label}必须为整数`;
        }
    }

    // 小数类型验证
    if (props.type === "decimal") {
        if (!/^-?\d*\.?\d*$/.test(value)) {
            return `${label}必须为数字`;
        }
    }

    // 数值范围验证（整数和小数通用）
    if (isNumberType.value) {
        const numValue = Number(inputValue.value);
        if (props.minNum !== undefined && numValue < props.minNum) {
            return `${label}不能小于 ${props.minNum}`;
        }
        if (props.maxNum !== undefined && numValue > props.maxNum) {
            return `${label}不能大于 ${props.maxNum}`;
        }
    }

    return null;
};

// 确认提交
const handleConfirm = async () => {
    // 验证
    const error = validate();
    if (error) {
        errorMessage.value = error;
        return;
    }
    // 验证通过，清除错误
    errorMessage.value = "";

    // 根据类型处理值
    let value: string | number = inputValue.value;
    if (isNumberType.value) {
        value = Number(inputValue.value);
        // 价格类型保留两位小数
        if (props.type === "decimal" && props.isPrice) {
            value = Number(value.toFixed(2));
        }
    }

    // 兼容旧版 isDirect：强制走“直接确认”，跳过 requestApi
    // 或者没有 requestApi 时，也直接更新值并关闭
    if (props.isDirect || !props.requestApi) {
        emit("update:orgValue", value);
        emit("ok", value);
        popconfirmRef.value?.hide();
        return;
    }

    // 调用 API
    loading.value = true;
    try {
        await props.requestApi({
            ...props.params,
            val: value
        });
        message.success("修改成功");
        emit("update:orgValue", value);
        emit("ok", value);
        // 先重置 loading，等待 Vue 响应式更新后再关闭
        // 否则 Popconfirm 的 hide 方法会因为 props.loading 仍为 true 而直接返回
        loading.value = false;
        await nextTick();
        popconfirmRef.value?.hide();
    } catch (error: unknown) {
        const err = error as { message?: string };
        message.error(err.message || "操作失败");
        loading.value = false;
    }
};

// 取消（来自 Popconfirm 的事件）
const handleCancel = () => {
    emit("cancel");
    loading.value = false;
};

// 取消按钮点击
const handleCancelClick = () => {
    emit("cancel");
    popconfirmRef.value?.hide();
};

// 回车提交
const handleKeydown = (e: KeyboardEvent) => {
    if (e.key === "Enter" && props.type !== "textarea") {
        e.preventDefault();
        handleConfirm();
    }
    if (e.key === "Escape") {
        popconfirmRef.value?.hide();
    }
};

// 暴露方法供外部调用
const show = () => popconfirmRef.value?.show();
const hide = () => popconfirmRef.value?.hide();

defineExpose({
    show,
    hide
});
</script>

<template>
    <Popconfirm
        ref="popconfirmRef"
        :placement="placement"
        :disabled="disabled"
        :width="width"
        :loading="loading"
        :show-buttons="false"
        :class="props.class"
        @cancel="handleCancel"
        @after-open="handleAfterOpen"
    >
        <!-- 触发器（.stop 阻止冒泡，避免触发父元素事件如表格行点击） -->
        <span
            class="pop-form-trigger"
            :class="{
                'is-disabled': disabled,
                'is-hover': props.isHover,
                'is-not-hover': !props.isHover
            }"
        >
            <slot />
            <svg v-if="!disabled" class="pop-form-edit-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
                <path
                    d="M644.288 201.344l114.24 112.8a31.616 31.616 0 0 1 0 45.12l-91.392 90.24-159.936-157.92 91.392-90.24a32.608 32.608 0 0 1 45.696 0z m-22.848 67.68l-22.848 22.56 68.544 67.68 22.848-22.56-68.544-67.68z m120.64 499.2V832H225.088v-63.808H742.08z m-257.728-454.08l159.936 157.888-251.328 248.16-134.496 8.864a32.16 32.16 0 0 1-34.4-33.984l8.96-132.8 251.328-248.128z m0 90.24L295.904 590.4l-4.896 72.512 73.44-4.8 188.48-186.112-68.576-67.648z"
                    fill="currentColor"
                />
            </svg>
        </span>

        <!-- 自定义内容 -->
        <template #content>
            <!-- 表单行：label 和输入框左右布局 -->
            <div class="pop-form-row">
                <!-- 标签 -->
                <label v-if="label" class="pop-form-label">{{ label }}:</label>

                <!-- 输入区域 -->
                <div class="pop-form-input-wrapper" :style="{ width: inputWidthStyle }">
                    <div :class="{ 'pop-form-input-error': errorMessage }">
                        <vort-textarea
                            v-if="type === 'textarea'"
                            ref="inputRef"
                            :model-value="String(inputValue)"
                            size="small"
                            :maxlength="max"
                            :rows="3"
                            class="w-full"
                            @update:model-value="
                                (val: string) => {
                                    inputValue = val;
                                    errorMessage = '';
                                }
                            "
                            @keydown="handleKeydown"
                        />
                        <vort-input-number
                            v-else-if="type === 'integer'"
                            ref="inputRef"
                            :model-value="Number(inputValue) || null"
                            size="small"
                            :controls="false"
                            class="w-full"
                            style="margin-top: 5px"
                            @update:model-value="
                                (val: number | null) => {
                                    inputValue = val ?? 0;
                                    errorMessage = '';
                                }
                            "
                            @press-enter="handleConfirm"
                        />
                        <vort-input-number
                            v-else-if="type === 'decimal'"
                            ref="inputRef"
                            :model-value="Number(inputValue) || null"
                            size="small"
                            :controls="false"
                            :precision="isPrice ? 2 : undefined"
                            :step="isPrice ? 0.01 : 0.1"
                            class="w-full"
                            style="margin-top: 5px"
                            @update:model-value="
                                (val: number | null) => {
                                    inputValue = val ?? 0;
                                    errorMessage = '';
                                }
                            "
                            @press-enter="handleConfirm"
                        />
                        <vort-input
                            v-else
                            ref="inputRef"
                            :model-value="String(inputValue)"
                            size="small"
                            :maxlength="max || len"
                            class="w-full"
                            style="margin-top: 5px"
                            @update:model-value="
                                (val: string) => {
                                    inputValue = val;
                                    errorMessage = '';
                                }
                            "
                            @press-enter="handleConfirm"
                        />
                    </div>
                    <!-- 错误信息 -->
                    <Transition name="pop-form-error">
                        <div v-if="errorMessage" class="pop-form-error-text">{{ errorMessage }}</div>
                    </Transition>
                    <!-- 额外说明 -->
                    <div v-if="displayExtra && !errorMessage" class="pop-form-extra">{{ displayExtra }}</div>
                </div>
            </div>

            <!-- 按钮区域（自己管理以控制 loading） -->
            <div class="pop-form-buttons">
                <button class="pop-form-btn" :disabled="loading" @click="handleCancelClick">
                    {{ cancelText }}
                </button>
                <button class="pop-form-btn pop-form-btn-primary" :class="{ 'is-loading': loading }" :disabled="loading" @click="handleConfirm">
                    <span v-if="loading" class="pop-form-btn-loading" />
                    {{ okText }}
                </button>
            </div>
        </template>
    </Popconfirm>
</template>

<style scoped>
.pop-form-trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
}

.pop-form-trigger.is-disabled {
    cursor: not-allowed;
}

.pop-form-edit-icon {
    width: 16px;
    height: 16px;
    color: #666;
    opacity: 0;
    transition: opacity 0.2s;
    flex-shrink: 0;
}

.pop-form-trigger.is-hover:hover .pop-form-edit-icon {
    opacity: 1;
}

/* 非 hover 模式：用于表格等场景，触发器占满并居中，编辑图标常显 */
.pop-form-trigger.is-not-hover {
    width: 100%;
    justify-content: center;
}

.pop-form-trigger.is-not-hover .pop-form-edit-icon {
    opacity: 1;
}

/* 表单行：左右布局 */
.pop-form-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-top: 8px;
}

.pop-form-label {
    font-size: 14px;
    color: rgba(0, 0, 0, 0.88);
    line-height: 32px;
    white-space: nowrap;
    flex-shrink: 0;
}

.pop-form-input-wrapper {
    width: 200px;
}

.pop-form-extra {
    font-size: 12px;
    color: rgba(0, 0, 0, 0.45);
    line-height: 1.5;
    margin-top: 4px;
}

/* 错误状态 - 输入框边框变红 */
.pop-form-input-error :deep(.vort-input),
.pop-form-input-error :deep(.vort-textarea),
.pop-form-input-error :deep(.vort-input-number) {
    border-color: var(--vort-error) !important;
}

.pop-form-input-error :deep(.vort-input:focus-within),
.pop-form-input-error :deep(.vort-textarea:focus-within),
.pop-form-input-error :deep(.vort-input-number:focus-within) {
    border-color: var(--vort-error) !important;
    box-shadow: 0 0 0 2px rgba(255, 77, 79, 0.06) !important;
}

/* 错误信息文字 */
.pop-form-error-text {
    font-size: 12px;
    color: var(--vort-error);
    line-height: 1.5;
    margin-top: 4px;
}

/* 错误信息动画 */
.pop-form-error-enter-active,
.pop-form-error-leave-active {
    transition:
        opacity 0.15s ease-in-out,
        transform 0.15s ease-in-out;
}

.pop-form-error-enter-from,
.pop-form-error-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

/* 按钮区域 */
.pop-form-buttons {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
}

.pop-form-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 24px;
    padding: 0 8px;
    font-size: 12px;
    font-weight: 400;
    border-radius: 2px;
    cursor: pointer;
    transition: all 0.2s;
    background: #fff;
    border: 1px solid var(--vort-border);
    color: rgba(0, 0, 0, 0.88);
}

.pop-form-btn:hover {
    color: var(--vort-primary-hover);
    border-color: var(--vort-primary-hover);
}

.pop-form-btn:active {
    color: var(--vort-primary-active);
    border-color: var(--vort-primary-active);
}

.pop-form-btn-primary {
    background: var(--vort-primary);
    border-color: var(--vort-primary);
    color: #fff;
}

.pop-form-btn-primary:hover {
    background: var(--vort-primary-hover);
    border-color: var(--vort-primary-hover);
    color: #fff;
}

.pop-form-btn-primary:active {
    background: var(--vort-primary-active);
    border-color: var(--vort-primary-active);
    color: #fff;
}

.pop-form-btn:disabled {
    cursor: not-allowed;
    opacity: 0.65;
}

.pop-form-btn.is-loading {
    position: relative;
    pointer-events: none;
}

.pop-form-btn-loading {
    display: inline-block;
    width: 12px;
    height: 12px;
    margin-right: 4px;
    border: 1.5px solid currentColor;
    border-top-color: transparent;
    border-radius: 50%;
    animation: pop-form-spin 0.8s linear infinite;
}

@keyframes pop-form-spin {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}
</style>
