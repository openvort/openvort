<script setup lang="ts">
import { computed, ref, provide, watch, toRef, type Ref } from "vue";
import type { MenuMode, MenuTheme } from "./types";
import "./menu.css";

defineOptions({ name: "VortMenu" });

/**
 * Vort Menu - 菜单组件
 *
 * 设计规范参考 Ant Design 5.x
 * - 支持垂直、水平、内联三种模式
 * - 支持亮色/暗色主题
 * - 支持多级子菜单
 * - 支持折叠模式
 */

interface Props {
    /** 菜单模式 */
    mode?: MenuMode;
    /** 菜单主题 */
    theme?: MenuTheme;
    /** 当前选中的菜单项 key 数组 */
    selectedKeys?: string[];
    /** 默认选中的菜单项 key 数组 */
    defaultSelectedKeys?: string[];
    /** 当前展开的 SubMenu 菜单项 key 数组 */
    openKeys?: string[];
    /** 默认展开的 SubMenu 菜单项 key 数组 */
    defaultOpenKeys?: string[];
    /** inline 模式下菜单是否折叠 */
    inlineCollapsed?: boolean;
    /** inline 模式的菜单缩进宽度 */
    inlineIndent?: number;
    /** 是否允许多选 */
    multiple?: boolean;
    /** 是否允许选中 */
    selectable?: boolean;
    /** 子菜单展开/关闭的触发行为（仅 horizontal 和 vertical 模式有效） */
    triggerSubMenuAction?: "hover" | "click";
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    mode: "vertical",
    theme: "light",
    selectedKeys: undefined,
    defaultSelectedKeys: () => [],
    openKeys: undefined,
    defaultOpenKeys: () => [],
    inlineCollapsed: false,
    inlineIndent: 24,
    multiple: false,
    selectable: true,
    triggerSubMenuAction: "hover"
});

const emit = defineEmits<{
    /** 选中菜单项时触发 */
    select: [info: { key: string; keyPath: string[]; selectedKeys: string[] }];
    /** 取消选中菜单项时触发（仅多选模式） */
    deselect: [info: { key: string; keyPath: string[]; selectedKeys: string[] }];
    /** 点击菜单项时触发 */
    click: [info: { key: string; keyPath: string[] }];
    /** SubMenu 展开/关闭时触发 */
    openChange: [openKeys: string[]];
    /** 选中的菜单项变化时触发 */
    "update:selectedKeys": [keys: string[]];
    /** 展开的子菜单变化时触发 */
    "update:openKeys": [keys: string[]];
}>();

// ==================== 内部状态 ====================

// 已注册的菜单项
const registeredItems = ref<Set<string>>(new Set());

// MenuItem 到其所有父级 SubMenu 的映射
const itemParentMap = ref<Map<string, string[]>>(new Map());

// 内部选中状态
const internalSelectedKeys = ref<string[]>([...props.defaultSelectedKeys]);

// 内部展开状态
const internalOpenKeys = ref<string[]>([...props.defaultOpenKeys]);

// 折叠前的展开状态（用于恢复）
const preCollapsedOpenKeys = ref<string[]>([]);

// 计算实际的选中 keys（支持受控和非受控）
const selectedKeys = computed({
    get: () => (props.selectedKeys !== undefined ? props.selectedKeys : internalSelectedKeys.value),
    set: (val) => {
        if (props.selectedKeys === undefined) {
            internalSelectedKeys.value = val;
        }
        emit("update:selectedKeys", val);
    }
});

// 计算实际的展开 keys（支持受控和非受控）
const openKeys = computed({
    get: () => (props.openKeys !== undefined ? props.openKeys : internalOpenKeys.value),
    set: (val) => {
        if (props.openKeys === undefined) {
            internalOpenKeys.value = val;
        }
        emit("update:openKeys", val);
        emit("openChange", val);
    }
});

// 实际模式：折叠时强制使用 vertical 模式（子菜单弹出）
const realMode = computed(() => {
    if (props.mode === "inline" && props.inlineCollapsed) {
        return "vertical";
    }
    return props.mode;
});

// ==================== 方法 ====================

// 注册菜单项（同时记录其所有父级 SubMenu）
const registerItem = (key: string, parentSubMenuKeys: string[] = []) => {
    registeredItems.value.add(key);
    if (parentSubMenuKeys.length > 0) {
        itemParentMap.value.set(key, parentSubMenuKeys);
    }
};

// 取消注册菜单项
const unregisterItem = (key: string) => {
    registeredItems.value.delete(key);
    itemParentMap.value.delete(key);
};


// 选择菜单项
const selectItem = (key: string) => {
    if (!props.selectable) return;

    const keyPath = [key]; // TODO: 计算完整路径

    // 触发点击事件
    emit("click", { key, keyPath });

    if (props.multiple) {
        // 多选模式
        const index = selectedKeys.value.indexOf(key);
        if (index > -1) {
            // 取消选中
            const newKeys = [...selectedKeys.value];
            newKeys.splice(index, 1);
            selectedKeys.value = newKeys;
            emit("deselect", { key, keyPath, selectedKeys: newKeys });
        } else {
            // 选中
            const newKeys = [...selectedKeys.value, key];
            selectedKeys.value = newKeys;
            emit("select", { key, keyPath, selectedKeys: newKeys });
        }
    } else {
        // 单选模式
        if (!selectedKeys.value.includes(key)) {
            selectedKeys.value = [key];
            emit("select", { key, keyPath, selectedKeys: [key] });
        }
    }
};

// 切换子菜单展开状态
const toggleSubMenu = (key: string) => {
    const index = openKeys.value.indexOf(key);
    if (index > -1) {
        // 关闭
        const newKeys = [...openKeys.value];
        newKeys.splice(index, 1);
        openKeys.value = newKeys;
    } else {
        // 展开
        if (realMode.value === "inline") {
            // inline 模式支持多个展开
            openKeys.value = [...openKeys.value, key];
        } else {
            // vertical/horizontal 模式只展开一个
            openKeys.value = [key];
        }
    }
};

// 设置展开的子菜单
const setOpenKeys = (keys: string[]) => {
    openKeys.value = keys;
};

// ==================== 上下文 ====================

// 使用响应式 provide
provide("menu", {
    mode: realMode,
    theme: toRef(props, "theme"),
    selectedKeys,
    openKeys,
    inlineCollapsed: toRef(props, "inlineCollapsed"),
    inlineIndent: toRef(props, "inlineIndent"),
    triggerSubMenuAction: toRef(props, "triggerSubMenuAction"),
    level: 0,
    registerItem,
    unregisterItem,
    selectItem,
    toggleSubMenu,
    setOpenKeys,
    itemParentMap
});

// ==================== 样式 ====================

const menuClasses = computed(() => {
    const classes = ["vort-menu", `vort-menu--${realMode.value}`, `vort-menu--${props.theme}`];
    if (props.inlineCollapsed && props.mode === "inline") {
        classes.push("vort-menu--collapsed");
    }
    if (props.class) {
        classes.push(props.class);
    }
    return classes;
});

// 监听折叠状态变化
watch(
    () => props.inlineCollapsed,
    (collapsed) => {
        if (collapsed) {
            // 折叠时保存当前展开状态
            preCollapsedOpenKeys.value = [...openKeys.value];
            openKeys.value = [];
        } else {
            // 展开时恢复之前的状态
            openKeys.value = preCollapsedOpenKeys.value;
        }
    }
);
</script>

<template>
    <ul :class="menuClasses" role="menu">
        <slot />
    </ul>
</template>
