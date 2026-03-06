<script setup lang="ts">
import { computed, inject, provide, ref, onUnmounted, watch, nextTick, toRef, type Ref } from "vue";
import { RightOutlined, DownOutlined } from "../icons";

defineOptions({ name: "VortSubMenu" });

/**
 * Vort SubMenu - 子菜单组件
 */

interface Props {
    /** 唯一标识 */
    itemKey: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 子菜单标题（也可通过 slot 传入） */
    title?: string;
    /** 弹出菜单的类名 */
    popupClassName?: string;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    disabled: false
});

// 注入菜单上下文
const menu = inject<{
    mode: Ref<string>;
    theme: Ref<string>;
    selectedKeys: Ref<string[]>;
    openKeys: Ref<string[]>;
    inlineCollapsed: Ref<boolean>;
    inlineIndent: Ref<number>;
    triggerSubMenuAction: Ref<string>;
    toggleSubMenu: (key: string) => void;
    itemParentMap: Ref<Map<string, string[]>>;
}>("menu");

// 注入父级 SubMenu 上下文（如果存在）
const parentSubMenu = inject<{
    level: Ref<number>;
    parentKey: Ref<string>;
    parentKeys: Ref<string[]>;
} | null>("subMenu", null);

// 当前 SubMenu 及其所有父级的 key 列表
const allParentKeys = computed(() => {
    const parentKeys = parentSubMenu?.parentKeys?.value ?? [];
    return [...parentKeys, props.itemKey];
});

// 计算当前层级
const level = computed(() => (parentSubMenu?.level?.value ?? 0) + 1);

// 是否展开
const isOpen = computed(() => menu?.openKeys?.value?.includes(props.itemKey) ?? false);

// 是否折叠状态
const isCollapsed = computed(() => menu?.inlineCollapsed?.value ?? false);

// 是否是根级别
const isRootLevel = computed(() => level.value === 1);

// 实际模式
const realMode = computed(() => menu?.mode?.value ?? "vertical");

// 是否使用弹出模式（非 inline 模式，或折叠状态）
const usePopup = computed(() => realMode.value !== "inline");

// 是否有选中的子项
const hasSelectedChild = computed(() => {
    const selectedKeys = menu?.selectedKeys?.value ?? [];
    const itemParentMap = menu?.itemParentMap?.value;
    if (!itemParentMap) return false;

    for (const selectedKey of selectedKeys) {
        const parents = itemParentMap.get(selectedKey);
        if (parents && parents.includes(props.itemKey)) {
            return true;
        }
    }
    return false;
});

// 计算缩进
const paddingLeft = computed(() => {
    if (realMode.value !== "inline") return undefined;
    if (isCollapsed.value) return undefined;
    return `${level.value * (menu?.inlineIndent?.value ?? 24)}px`;
});

// Hover 相关状态
const isHovered = ref(false);
const hoverTimeout = ref<ReturnType<typeof setTimeout> | null>(null);
const subMenuRef = ref<HTMLElement | null>(null);
const popupRef = ref<HTMLElement | null>(null);

// 清除定时器
const clearHoverTimeout = () => {
    if (hoverTimeout.value) {
        clearTimeout(hoverTimeout.value);
        hoverTimeout.value = null;
    }
};

// 处理鼠标进入
const handleMouseEnter = () => {
    if (props.disabled) return;
    if (!usePopup.value) return;
    if (menu?.triggerSubMenuAction?.value !== "hover") return;

    clearHoverTimeout();
    isHovered.value = true;

    if (!isOpen.value) {
        menu?.toggleSubMenu?.(props.itemKey);
    }
};

// 处理鼠标离开
const handleMouseLeave = () => {
    if (props.disabled) return;
    if (!usePopup.value) return;
    if (menu?.triggerSubMenuAction?.value !== "hover") return;

    clearHoverTimeout();
    hoverTimeout.value = setTimeout(() => {
        isHovered.value = false;
        if (isOpen.value) {
            menu?.toggleSubMenu?.(props.itemKey);
        }
    }, 100);
};

// 处理点击
const handleTitleClick = () => {
    if (props.disabled) return;

    // inline 模式或 click 触发时，点击切换展开状态
    if (!usePopup.value || menu?.triggerSubMenuAction?.value === "click") {
        menu?.toggleSubMenu?.(props.itemKey);
    }
};

// 提供子菜单上下文
provide("subMenu", {
    level: computed(() => level.value),
    parentKey: toRef(props, "itemKey"),
    parentKeys: allParentKeys,
    isOpen
});

// 重新 provide menu 上下文，确保 Teleport 内部的组件也能访问
if (menu) {
    provide("menu", menu);
}

// 样式类
const subMenuClasses = computed(() => {
    const classes = ["vort-menu-submenu", `vort-menu-submenu--${realMode.value}`];
    if (isOpen.value) classes.push("vort-menu-submenu--open");
    if (props.disabled) classes.push("vort-menu-submenu--disabled");
    if (hasSelectedChild.value) classes.push("vort-menu-submenu--selected");
    if (props.class) classes.push(props.class);
    return classes;
});

const titleClasses = computed(() => {
    const classes = ["vort-menu-submenu__title"];
    if (isOpen.value) classes.push("vort-menu-submenu__title--open");
    return classes;
});

const popupClasses = computed(() => {
    const classes = ["vort-menu-submenu__popup", `vort-menu--${menu?.theme?.value ?? "light"}`];
    if (props.popupClassName) classes.push(props.popupClassName);
    return classes;
});

// 是否显示 inline 内容
const showInlineContent = computed(() => !usePopup.value && isOpen.value);

// 是否显示弹出层
const showPopup = computed(() => usePopup.value && isOpen.value);

// 计算弹出层位置
const popupStyle = ref<Record<string, string>>({});

// 更新弹出层位置
const updatePopupPosition = () => {
    if (!subMenuRef.value || !showPopup.value) return;

    const rect = subMenuRef.value.getBoundingClientRect();
    const mode = realMode.value;

    if (mode === "horizontal" && isRootLevel.value) {
        // 水平模式的一级菜单：弹出层在下方
        popupStyle.value = {
            top: `${rect.bottom}px`,
            left: `${rect.left}px`,
            minWidth: `${rect.width}px`
        };
    } else {
        // 垂直模式或子级：弹出层在右侧
        // 折叠状态下，找到菜单容器的右边缘
        let rightEdge = rect.right;
        if (isCollapsed.value && isRootLevel.value) {
            // 折叠状态下使用菜单容器的右边缘
            const menuEl = subMenuRef.value.closest(".vort-menu");
            if (menuEl) {
                const menuRect = menuEl.getBoundingClientRect();
                rightEdge = menuRect.right;
            }
        }
        popupStyle.value = {
            top: `${rect.top}px`,
            left: `${rightEdge + 4}px`
        };
    }
};

// 监听展开状态，更新位置
watch(isOpen, (open) => {
    if (open && usePopup.value) {
        nextTick(updatePopupPosition);
    }
});

// 清理
onUnmounted(() => {
    clearHoverTimeout();
});

// 展开箭头方向
const arrowIcon = computed(() => {
    if (realMode.value === "horizontal" && isRootLevel.value) {
        return DownOutlined;
    }
    if (realMode.value === "inline") {
        return DownOutlined;
    }
    return RightOutlined;
});
</script>

<template>
    <li
        ref="subMenuRef"
        :class="subMenuClasses"
        role="menuitem"
        :aria-disabled="disabled"
        :aria-expanded="isOpen"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
    >
        <!-- SubMenu 标题（折叠时不显示 tooltip，因为已有弹出菜单） -->
        <div :class="titleClasses" :style="{ paddingLeft }" @click="handleTitleClick">
            <!-- 图标插槽 -->
            <span v-if="$slots.icon" class="vort-menu-submenu__icon">
                <slot name="icon" />
            </span>
            <!-- 标题内容（CSS 控制折叠时淡出） -->
            <span class="vort-menu-submenu__title-content">
                <slot name="title">{{ title }}</slot>
            </span>
            <!-- 展开箭头（CSS 控制折叠时淡出） -->
            <span class="vort-menu-submenu__arrow">
                <component :is="arrowIcon" />
            </span>
        </div>

        <!-- Inline 模式内容 -->
        <Transition v-if="!usePopup" name="vort-menu-collapse">
            <ul v-show="isOpen" class="vort-menu-submenu__content vort-menu vort-menu--inline" role="menu">
                <slot />
            </ul>
        </Transition>

        <!--
            弹出层（vertical/horizontal/collapsed 模式）
            注意：使用 v-show 而非 v-if，确保子组件始终渲染，
            这样 MenuItem 的 onMounted 能正常执行，itemParentMap 能正确记录父子关系，
            从而让 hasSelectedChild 能正确计算，折叠时父级 SubMenu 能显示选中高亮。
        -->
        <Teleport v-if="usePopup" to="body">
            <Transition name="vort-menu-popup">
                <div v-show="isOpen" :class="popupClasses" :style="popupStyle" @mouseenter="handleMouseEnter" @mouseleave="handleMouseLeave">
                    <ul class="vort-menu vort-menu--vertical vort-menu--popup" role="menu">
                        <slot />
                    </ul>
                </div>
            </Transition>
        </Teleport>
    </li>
</template>
