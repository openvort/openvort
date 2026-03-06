<script setup lang="ts">
import { dialog, message } from "@/components/vort";

defineOptions({ name: "DeleteRecord" });

type ApiResponseLike = {
    code?: unknown;
    message?: unknown;
};

const getApiErrorMessage = (response: unknown): string | null => {
    if (!response || typeof response !== "object") return null;
    const res = response as ApiResponseLike;
    if (typeof res.code === "number" && res.code !== 0) {
        return typeof res.message === "string" && res.message ? res.message : "删除失败";
    }
    return null;
};

interface Props {
    /** 删除请求的 API 函数 */
    requestApi: (params: Record<string, unknown>) => Promise<unknown>;
    /** 传递给 API 的参数 */
    params?: Record<string, unknown>;
    /** 确认框标题 */
    title?: string;
    /** 删除成功后的提示消息 */
    successMessage?: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 确认按钮文字 */
    okText?: string;
    /** 取消按钮文字 */
    cancelText?: string;
    /** 是否为块级元素（用于 dropdown 等场景，使点击区域填满整个容器） */
    block?: boolean;
    /** 删除成功后的回调（用于 teleport 场景，如 dropdown 内） */
    onSuccess?: () => void;
}

const props = withDefaults(defineProps<Props>(), {
    params: () => ({}),
    title: "您确认要删除该数据吗？",
    successMessage: "删除成功",
    disabled: false,
    okText: "确定",
    cancelText: "取消",
    block: false,
    onSuccess: undefined
});

const emit = defineEmits(["afterDelete"]);

// 点击触发删除确认
const handleClick = () => {
    if (props.disabled) return;

    dialog.confirm({
        title: props.title,
        okText: props.okText,
        cancelText: props.cancelText,
        okType: "danger",
        onOk: async () => {
            let hasShownError = false;
            try {
                const response = await props.requestApi(props.params);
                const errMsg = getApiErrorMessage(response);
                if (errMsg) {
                    hasShownError = true;
                    message.error(errMsg);
                    throw new Error(errMsg);
                }
                message.success(props.successMessage);
                // 优先使用回调函数（用于 teleport 场景），否则触发事件
                if (props.onSuccess) {
                    props.onSuccess();
                } else {
                    emit("afterDelete", true);
                }
            } catch (error: unknown) {
                if (!hasShownError) {
                    const msg =
                        typeof error === "object" && error !== null && "message" in error ? (error as { message?: string }).message || "删除失败" : "删除失败";
                    message.error(msg);
                }
                throw error;
            }
        }
    });
};
</script>

<template>
    <a :class="['delete-record', { disabled: disabled, block: block }]" @click="handleClick">
        <slot />
    </a>
</template>

<style scoped>
.delete-record.disabled {
    cursor: not-allowed;
    color: rgba(0, 0, 0, 0.25);
    pointer-events: none;
}

/* 块级模式：用于 dropdown 等场景，使点击区域填满整个容器 */
.delete-record.block {
    display: block;
    margin: -5px -12px;
    padding: 5px 12px;
}
</style>
