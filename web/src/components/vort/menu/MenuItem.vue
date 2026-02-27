<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, nextTick, type Ref } from "vue";

defineOptions({ name: "VortMenuItem" });

/**
 * Vort MenuItem - 菜单项组件
 *
 * 结构设计参考 Ant Design 6.x:
 * - <li> 始终作为根元素，保持正确的 HTML 语义（ul > li）
 * - 折叠时的 Tooltip 使用 Teleport 渲染到 body，不破坏结构
 */

interface Props {
    /** 唯一标识 */
    itemKey: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否危险项（红色） */
    danger?: boolean;
    /** 菜单标题（也可通过 slot 传入） */
    title?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false,
    danger: false
});

const emit = defineEmits<{
    /** 点击菜单项时触发 */
    click: [event: MouseEvent];
}>();

// 注入菜单上下文
const menu = inject<{
    mode: Ref<string>;
    theme: Ref<string>;
    selectedKeys: Ref<string[]>;
    inlineCollapsed: Ref<boolean>;
    inlineIndent: Ref<number>;
    registerItem: (key: string, parentSubMenuKeys?: string[]) => void;
    unregisterItem: (key: string) => void;
    selectItem: (key: string) => void;
}>("menu");

// 注入 SubMenu 上下文（如果存在）
const subMenu = inject<{
    level: Ref<number>;
    parentKey: Ref<string>;
    parentKeys: Ref<string[]>;
}>("subMenu", null);

// 计算当前层级
const level = computed(() => (subMenu?.level?.value ?? 0) + 1);

// 计算是否选中
const isSelected = computed(() => menu?.selectedKeys?.value?.includes(props.itemKey) ?? false);

// 是否折叠状态
const isCollapsed = computed(() => menu?.inlineCollapsed?.value ?? false);

// 是否是根级别（用于折叠时显示 tooltip）
const isRootLevel = computed(() => level.value === 1);

// 是否需要显示 Tooltip（折叠状态下的根级菜单项）
const needTooltip = computed(() => isCollapsed.value && isRootLevel.value && !subMenu);

// 计算缩进
const paddingLeft = computed(() => {
    if (menu?.mode?.value !== "inline") return undefined;
    if (isCollapsed.value) return undefined;
    return `${level.value * (menu?.inlineIndent?.value ?? 24)}px`;
});

// 注册/注销
onMounted(() => {
    const parentKeys = subMenu?.parentKeys?.value ?? [];
    menu?.registerItem?.(props.itemKey, parentKeys);
});

onUnmounted(() => {
    menu?.unregisterItem?.(props.itemKey);
});

// 点击处理
const handleClick = (event: MouseEvent) => {
    if (props.disabled) return;
    emit("click", event);
    menu?.selectItem?.(props.itemKey);
};

// 样式类
const itemClasses = computed(() => {
    const classes = ["vort-menu-item"];
    if (isSelected.value) classes.push("vort-menu-item--selected");
    if (props.disabled) classes.push("vort-menu-item--disabled");
    if (props.danger) classes.push("vort-menu-item--danger");
    if (props.class) classes.push(props.class);
    return classes;
});

// 是否深色主题
const isDarkTheme = computed(() => menu?.theme?.value === "dark");

// ==================== 内置 Tooltip 实现 ====================
const itemRef = ref<HTMLElement | null>(null);
const tooltipVisible = ref(false);
const tooltipPosition = ref({ top: 0, left: 0 });
let enterTimer: ReturnType<typeof setTimeout> | null = null;
let leaveTimer: ReturnType<typeof setTimeout> | null = null;

const clearTimers = () => {
    if (enterTimer) {
        clearTimeout(enterTimer);
        enterTimer = null;
    }
    if (leaveTimer) {
        clearTimeout(leaveTimer);
        leaveTimer = null;
    }
};

const updateTooltipPosition = () => {
    if (!itemRef.value) return;
    const rect = itemRef.value.getBoundingClientRect();
    tooltipPosition.value = {
        top: rect.top + rect.height / 2,
        left: rect.right + 4
    };
};

const showTooltip = () => {
    if (!needTooltip.value || !props.title) return;
    clearTimers();
    enterTimer = setTimeout(() => {
        updateTooltipPosition();
        tooltipVisible.value = true;
    }, 100);
};

const hideTooltip = () => {
    clearTimers();
    leaveTimer = setTimeout(() => {
        tooltipVisible.value = false;
    }, 100);
};

// 清理
onUnmounted(() => {
    clearTimers();
});
</script>

<template>
    <li
        ref="itemRef"
        :class="itemClasses"
        :style="{ paddingLeft }"
        role="menuitem"
        :aria-disabled="disabled"
        :aria-selected="isSelected"
        @click="handleClick"
        @mouseenter="showTooltip"
        @mouseleave="hideTooltip"
    >
        <!-- 图标插槽 -->
        <span v-if="$slots.icon" class="vort-menu-item__icon">
            <slot name="icon" />
        </span>
        <!-- 标题内容（CSS 控制折叠时淡出） -->
        <span class="vort-menu-item__content">
            <slot>{{ title }}</slot>
        </span>

        <!-- 内置 Tooltip：折叠状态下显示，使用 Teleport 到 body 保持 HTML 语义 -->
        <Teleport to="body">
            <Transition name="vort-menu-tooltip">
                <div
                    v-if="tooltipVisible && needTooltip && title"
                    class="vort-menu-inline-tooltip"
                    :class="{ 'vort-menu-inline-tooltip--dark': isDarkTheme }"
                    :style="{
                        top: `${tooltipPosition.top}px`,
                        left: `${tooltipPosition.left}px`
                    }"
                    @mouseenter="showTooltip"
                    @mouseleave="hideTooltip"
                >
                    <div class="vort-menu-inline-tooltip__arrow" />
                    <div class="vort-menu-inline-tooltip__content">{{ title }}</div>
                </div>
            </Transition>
        </Teleport>
    </li>
</template>

<style scoped>
/* 内置 Tooltip 样式 */
.vort-menu-inline-tooltip {
    position: fixed;
    z-index: 1070;
    padding: 6px 8px;
    background: #fff;
    color: rgba(0, 0, 0, 0.88);
    font-size: 14px;
    line-height: 1.5;
    border-radius: 6px;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
    transform: translateY(-50%);
    pointer-events: auto;
}

.vort-menu-inline-tooltip--dark {
    background: #222;
    color: #fff;
}

.vort-menu-inline-tooltip__arrow {
    position: absolute;
    left: -4px;
    top: 50%;
    width: 8px;
    height: 8px;
    background: inherit;
    transform: translateY(-50%) rotate(45deg);
    border-radius: 0 0 0 2px;
}

.vort-menu-inline-tooltip__content {
    position: relative;
    white-space: nowrap;
}

/* Tooltip 动画 */
.vort-menu-tooltip-enter-active,
.vort-menu-tooltip-leave-active {
    transition:
        opacity 0.1s ease,
        transform 0.1s ease;
}

.vort-menu-tooltip-enter-from,
.vort-menu-tooltip-leave-to {
    opacity: 0;
    transform: translateY(-50%) scale(0.9);
}
</style>
