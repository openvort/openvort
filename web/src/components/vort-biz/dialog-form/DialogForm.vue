<script setup lang="ts">
import { ref, computed, nextTick } from "vue";
import type { Component } from "vue";
import { dialog } from "@openvort/vort-ui";

defineOptions({ name: "DialogForm", inheritAttrs: false });

/**
 * DialogForm - 弹窗/抽屉表单组件
 *
 * 封装了触发器 → 打开弹窗/抽屉 → 加载表单组件 → 处理回调的通用模式
 * 支持 Dialog 和 Drawer 两种模式
 */

interface Props {
    // ========== 核心属性 ==========
    /** 表单组件（必需） */
    component: Component;
    /** 传递给表单组件的参数 */
    params?: Record<string, unknown>;

    // ========== 模式切换 ==========
    /** 是否使用抽屉模式，默认 false（Dialog 模式） */
    isDrawer?: boolean;

    // ========== 通用属性 ==========
    /** 标题 */
    title?: string;
    /** 宽度 */
    width?: string | number;
    /** 是否显示关闭按钮，默认 true */
    closable?: boolean;
    /** 点击遮罩是否允许关闭，默认 true */
    maskClosable?: boolean;
    /** 关闭时是否销毁内容，默认 false */
    destroyOnClose?: boolean;
    /** z-index */
    zIndex?: number;

    // ========== 底部按钮属性 ==========
    /** 是否显示底部按钮区域，默认 true */
    showFooter?: boolean;
    /** 是否显示取消按钮，默认 true */
    showCancel?: boolean;
    /** 是否显示确认按钮，默认 true */
    showOk?: boolean;
    /** 确认按钮文字 */
    okText?: string;
    /** 取消按钮文字 */
    cancelText?: string;
    /** 成功回调 */
    okHandler?: (payload?: any) => void;
    /** 取消回调 */
    cancelHandler?: () => void;

    // ========== Dialog 特有属性 ==========
    /** 垂直居中展示（仅 Dialog 模式） */
    centered?: boolean;
    /** body 区域是否无内边距 */
    bodyNoPadding?: boolean;

    // ========== Drawer 特有属性 ==========
    /** 抽屉方向（仅 Drawer 模式），默认 right */
    placement?: "left" | "right" | "top" | "bottom";

    // ========== 关闭确认属性 ==========
    /** 是否启用关闭确认（当表单有未保存的更改时提示用户），默认 false */
    closeConfirm?: boolean;
    /** 关闭确认弹窗标题 */
    closeConfirmTitle?: string;
    /** 关闭确认弹窗内容 */
    closeConfirmContent?: string;

    // ========== 内容区域背景色 ==========
    /** 内容区域背景色 */
    contentBg?: string;
}

const props = withDefaults(defineProps<Props>(), {
    params: () => ({}),
    isDrawer: false,
    closable: true,
    maskClosable: true,
    destroyOnClose: false,
    zIndex: 1000,
    showFooter: true,
    showCancel: true,
    showOk: true,
    okText: "确认",
    cancelText: "取消",
    okHandler: () => {},
    cancelHandler: () => {},
    centered: false,
    bodyNoPadding: false,
    placement: "right",
    closeConfirm: false,
    closeConfirmTitle: "退出当前编辑？",
    closeConfirmContent: "退出后，当前修改的内容不会被保存",
    contentBg: "#fff"
});

const emit = defineEmits<{
    /** 表单提交成功后触发（可选携带回传数据） */
    ok: [payload?: unknown];
    /** 取消/关闭时触发 */
    cancel: [];
    /** 关闭动画结束后触发 */
    afterClose: [];
}>();

// 是否已加载（延迟渲染优化，首次打开后才渲染弹窗）
const loaded = ref(false);

// 弹窗/抽屉是否可见
const visible = ref(false);

// 确认按钮 loading 状态
const confirmLoading = ref(false);

// 子组件引用（扩展类型，支持 isDirty 属性）
const submitFormRef = ref<{
    onFormSubmit?: () => void;
    isDirty?: { value: boolean } | boolean; // 支持 ref 或 computed
} | null>(null);

// 获取子组件的脏状态
const getIsDirty = (): boolean => {
    if (!props.closeConfirm) return false;
    const dirty = submitFormRef.value?.isDirty;
    if (dirty === undefined) return false;
    // 支持 ref 和 computed（都有 .value 属性）
    return typeof dirty === "object" && "value" in dirty ? dirty.value : !!dirty;
};

// 计算宽度，根据模式设置默认值
const computedWidth = computed(() => {
    if (props.width) return props.width;
    return props.isDrawer ? 378 : 520;
});

// 打开弹窗/抽屉（延迟渲染优化）
const open = () => {
    loaded.value = true;
    visible.value = true;
};

// 关闭弹窗/抽屉
const close = () => {
    visible.value = false;
    confirmLoading.value = false;
};

// 表单组件调用的成功回调（支持透传 payload）
const handleOk = (payload?: unknown) => {
    close();
    props.okHandler?.(payload);
    emit("ok", payload);
};

// 表单组件调用的取消回调（直接关闭，无确认）
const handleCancel = () => {
    close();
    props.cancelHandler?.();
    emit("cancel");
};

// 关闭前确认（用于用户点击关闭按钮、遮罩、ESC 等场景）
const handleCloseWithConfirm = () => {
    if (getIsDirty()) {
        dialog.confirm({
            title: props.closeConfirmTitle,
            content: props.closeConfirmContent,
            okType: "danger",
            onOk: () => {
                close();
                emit("cancel");
            }
        });
    } else {
        close();
        emit("cancel");
    }
};

// 处理 open 状态更新（拦截关闭操作以实现确认功能）
const handleOpenUpdate = (newOpen: boolean) => {
    if (newOpen) {
        // 打开操作直接执行
        visible.value = true;
    } else {
        // 关闭操作需要检查是否需要确认
        handleCloseWithConfirm();
    }
};

// 确认按钮点击 - 调用子组件的 onFormSubmit 方法
// 自动处理 loading 状态：如果 onFormSubmit 返回 Promise，自动管理 confirmLoading
const handleConfirm = async () => {
    try {
        // 兼容少数弹窗/抽屉实现：内容区可能在打开后下一帧才挂载，
        // 用户快速点击“确认”会导致 ref 尚未就绪，从而误报未暴露方法。
        for (let i = 0; i < 3 && !submitFormRef.value?.onFormSubmit; i++) {
            await nextTick();
        }
        if (!submitFormRef.value?.onFormSubmit) {
            dialog.error({
                title: "无法提交",
                content: "表单组件未暴露 onFormSubmit（ref 未就绪或未 defineExpose），请检查表单组件是否 defineExpose({ onFormSubmit })"
            });
            return;
        }

        const result = submitFormRef.value.onFormSubmit() as unknown;
        // 如果返回 Promise，自动处理 loading 状态
        if (result && typeof result === "object" && "then" in result) {
            confirmLoading.value = true;
            try {
                await (result as Promise<unknown>);
            } finally {
                confirmLoading.value = false;
            }
        }
    } catch (error: unknown) {
        confirmLoading.value = false;
        const errorMessage = error instanceof Error ? error.message : "提交失败";
        dialog.error({
            title: "操作失败",
            content: errorMessage
        });
    }
};

// 关闭动画结束后
const handleAfterClose = () => {
    emit("afterClose");
};

// 暴露方法供外部调用
defineExpose({
    open,
    close
});
</script>

<template>
    <!-- 触发器插槽（.stop 阻止冒泡，避免触发父元素事件如表格行点击） -->
    <span class="dialog-form-trigger" @click="open">
        <slot />
    </span>

    <!-- Dialog 模式（延迟渲染：首次打开后才挂载组件） -->
    <vort-dialog
        v-if="loaded && !isDrawer"
        :open="visible"
        :title="title"
        :width="computedWidth"
        :closable="closable"
        :mask-closable="maskClosable"
        :z-index="zIndex"
        :centered="centered"
        :footer="showFooter"
        :confirm-loading="confirmLoading"
        :ok-text="okText"
        :cancel-text="cancelText"
        :body-no-padding="bodyNoPadding"
        :content-bg="contentBg"
        @update:open="handleOpenUpdate"
        @ok="handleConfirm"
        @after-close="handleAfterClose"
    >
        <component
            ref="submitFormRef"
            :is="component"
            :params="params"
            v-bind="$attrs"
            v-model:confirm-loading="confirmLoading"
            :ok-handler="handleOk"
            :cancel-handler="handleCancel"
        />
        <!-- 自定义 footer 插槽（仅当需要自定义按钮显示时） -->
        <template v-if="showFooter && (!showCancel || !showOk)" #footer>
            <vort-button v-if="showCancel" @click="handleCloseWithConfirm">
                {{ cancelText }}
            </vort-button>
            <vort-button v-if="showOk" variant="primary" :loading="confirmLoading" @click="handleConfirm">
                {{ okText }}
            </vort-button>
        </template>
    </vort-dialog>

    <!-- Drawer 模式（延迟渲染：首次打开后才挂载组件） -->
    <vort-drawer
        v-if="loaded && isDrawer"
        :open="visible"
        :title="title"
        :width="computedWidth"
        :closable="closable"
        :mask-closable="maskClosable"
        :z-index="zIndex"
        :placement="placement"
        :destroy-on-close="destroyOnClose"
        :footer="showFooter"
        :content-bg="contentBg"
        @update:open="handleOpenUpdate"
        @after-open-change="(open: boolean) => !open && handleAfterClose()"
    >
        <component
            ref="submitFormRef"
            :is="component"
            :params="params"
            v-bind="$attrs"
            v-model:confirm-loading="confirmLoading"
            :ok-handler="handleOk"
            :cancel-handler="handleCancel"
        />
        <!-- Drawer 底部按钮区域 -->
        <template v-if="showFooter" #footer>
            <div class="dialog-form-footer">
                <vort-button v-if="showCancel" @click="handleCloseWithConfirm">
                    {{ cancelText }}
                </vort-button>
                <vort-button v-if="showOk" variant="primary" :loading="confirmLoading" @click="handleConfirm">
                    {{ okText }}
                </vort-button>
            </div>
        </template>
    </vort-drawer>
</template>

<style scoped>
.dialog-form-trigger {
    display: inline-block;
    cursor: pointer;
}

.dialog-form-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}
</style>
