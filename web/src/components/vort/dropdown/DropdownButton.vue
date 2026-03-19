<script lang="ts">
/** Vort DropdownButton - 下拉按钮组件 */
export type DropdownButtonType = "primary" | "default" | "dashed";
export type DropdownButtonSize = "large" | "middle" | "small";
export type DropdownButtonTrigger = "hover" | "click";
export type DropdownButtonPlacement = "bottom" | "bottomLeft" | "bottomRight" | "top" | "topLeft" | "topRight";

interface Props {
    /** 下拉菜单是否显示（受控模式） */
    open?: boolean;
    /** 按钮类型 */
    type?: DropdownButtonType;
    /** 按钮尺寸 */
    size?: DropdownButtonSize;
    /** 是否为危险按钮 */
    danger?: boolean;
    /** 左侧按钮是否禁用 */
    disabled?: boolean;
    /** 整个按钮组是否禁用（包括下拉触发按钮） */
    buttonsDisabled?: boolean;
    /** 是否加载中 */
    loading?: boolean;
    /** 触发下拉的行为 */
    trigger?: DropdownButtonTrigger | DropdownButtonTrigger[];
    /** 菜单弹出位置 */
    placement?: DropdownButtonPlacement;
    /** 下拉菜单的 class */
    overlayClassName?: string;
    /** 下拉菜单的 style */
    overlayStyle?: Record<string, string>;
    /** 是否显示箭头 */
    arrow?: boolean | { pointAtCenter: boolean };
    /** 关闭后是否销毁 Dropdown 内容 */
    destroyOnHidden?: boolean;
    /** 下拉框距触发元素的距离 */
    offset?: number;
    /** 菜单渲染父节点 */
    getPopupContainer?: () => HTMLElement;
    /** 鼠标移入后延迟多少时间显示 Dropdown，单位：毫秒 */
    mouseEnterDelay?: number;
    /** 鼠标移出后延迟多少时间关闭 Dropdown，单位：毫秒 */
    mouseLeaveDelay?: number;
}

export type { Props as DropdownButtonProps };
</script>

<script setup lang="ts">
import { computed, ref } from "vue";
import { DownOutlined } from "@/components/vort/icons";
import { Button } from "@/components/vort/button";
import Dropdown from "./Dropdown.vue";
import type { DropdownPlacement } from "./Dropdown.vue";

defineOptions({ name: "VortDropdownButton" });

const props = withDefaults(defineProps<Props>(), {
    open: undefined,
    type: "default",
    size: "middle",
    danger: false,
    disabled: false,
    buttonsDisabled: undefined,
    loading: false,
    trigger: "hover",
    placement: "bottomRight",
    overlayClassName: "",
    overlayStyle: () => ({}),
    arrow: false,
    destroyOnHidden: true,
    offset: 4,
    mouseEnterDelay: 100,
    mouseLeaveDelay: 100
});

const emit = defineEmits<{
    /** 左侧按钮点击事件 */
    click: [event: MouseEvent];
    /** 下拉菜单显示状态改变时调用 */
    "update:open": [open: boolean];
    /** 下拉菜单显示状态改变时调用 */
    openChange: [open: boolean];
}>();

// 内部 open 状态
const internalOpen = ref(false);

// 计算实际的 open 状态
const isOpen = computed({
    get: () => (props.open !== undefined ? props.open : internalOpen.value),
    set: (val) => {
        if (props.open === undefined) {
            internalOpen.value = val;
        }
        emit("update:open", val);
        emit("openChange", val);
    }
});

// 是否禁用下拉触发按钮
const isDropdownDisabled = computed(() => props.buttonsDisabled ?? false);

// 是否禁用左侧按钮
const isLeftDisabled = computed(() => props.disabled || props.loading || (props.buttonsDisabled ?? false));

// 右侧按钮的样式类
const rightButtonClass = computed(() => {
    const classes = ["vort-dropdown-button-right"];
    if (!isDropdownDisabled.value && props.type === "primary") {
        classes.push(props.danger ? "vort-dropdown-button-right--danger" : "vort-dropdown-button-right--primary");
    }
    return classes.join(" ");
});

// ============ 事件处理 ============
const handleLeftClick = (event: MouseEvent) => {
    emit("click", event);
};

const handleOpenChange = (open: boolean) => {
    isOpen.value = open;
};
</script>

<template>
    <div class="vort-dropdown-button">
        <!-- 左侧主按钮 -->
        <Button :type="type" :size="size" :danger="danger" :disabled="isLeftDisabled" :loading="loading" class="vort-dropdown-button-left" @click="handleLeftClick">
            <slot />
        </Button>

        <!-- 右侧下拉触发按钮 -->
        <Dropdown
            :open="isOpen"
            :trigger="trigger"
            :placement="placement as DropdownPlacement"
            :disabled="isDropdownDisabled"
            :overlay-class-name="overlayClassName"
            :overlay-style="overlayStyle"
            :arrow="arrow"
            :destroy-on-hidden="destroyOnHidden"
            :offset="offset"
            :get-popup-container="getPopupContainer"
            :mouse-enter-delay="mouseEnterDelay"
            :mouse-leave-delay="mouseLeaveDelay"
            @update:open="handleOpenChange"
        >
            <Button :type="type" :size="size" :danger="danger" :disabled="isDropdownDisabled" icon :class="rightButtonClass">
                <slot name="icon">
                    <DownOutlined class="vort-dropdown-button-icon" />
                </slot>
            </Button>
            <template #overlay>
                <slot name="overlay" />
            </template>
        </Dropdown>
    </div>
</template>

<style scoped>
/* 按钮组容器 */
.vort-dropdown-button {
    display: inline-flex;
    align-items: stretch;
}

/* 按钮组内所有按钮：默认 z-index: 1 */
.vort-dropdown-button :deep(button) {
    position: relative;
    z-index: 1;
}

/* hover/focus/active 时提升 z-index */
.vort-dropdown-button :deep(button:hover),
.vort-dropdown-button :deep(button:focus),
.vort-dropdown-button :deep(button:active) {
    z-index: 2;
}

/* 左侧按钮：去掉右侧圆角 */
.vort-dropdown-button :deep(.vort-dropdown-button-left) {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}

/* 右侧按钮：去掉左侧圆角，负 margin 合并边框 */
.vort-dropdown-button :deep(.vort-dropdown-button-right) {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    margin-left: -1px;
}

/* primary 类型：左边框使用主色 hover 色分隔 */
.vort-dropdown-button :deep(.vort-dropdown-button-right--primary) {
    border-left-color: var(--vort-primary-hover);
}

/* danger + primary 类型：左边框使用错误 hover 色分隔 */
.vort-dropdown-button :deep(.vort-dropdown-button-right--danger) {
    border-left-color: var(--vort-error-hover);
}

/* 图标尺寸 */
.vort-dropdown-button-icon {
    width: 12px;
    height: 12px;
}
</style>
