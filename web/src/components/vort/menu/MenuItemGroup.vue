<script setup lang="ts">
import { computed, inject, type Ref } from "vue";

defineOptions({ name: "VortMenuItemGroup" });

/**
 * Vort MenuItemGroup - 菜单分组组件
 */

interface Props {
    /** 分组标题（也可通过 slot 传入） */
    title?: string;
    /** 自定义类名 */
    class?: string;
}

const props = defineProps<Props>();

// 注入菜单上下文
const menu = inject<{
    mode: Ref<string>;
    inlineCollapsed: Ref<boolean>;
    inlineIndent: Ref<number>;
}>("menu");

// 注入 SubMenu 上下文（如果存在）
const subMenu = inject<{
    level: Ref<number>;
}>("subMenu", null);

// 计算当前层级
const level = computed(() => (subMenu?.level?.value ?? 0) + 1);

// 计算缩进
const paddingLeft = computed(() => {
    if (menu?.mode?.value !== "inline") return undefined;
    if (menu?.inlineCollapsed?.value) return undefined;
    return `${level.value * (menu?.inlineIndent?.value ?? 24)}px`;
});

// 样式类
const groupClasses = computed(() => {
    const classes = ["vort-menu-item-group"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <li :class="groupClasses" role="presentation">
        <!-- 分组标题 -->
        <div class="vort-menu-item-group__title" :style="{ paddingLeft }">
            <slot name="title">{{ title }}</slot>
        </div>
        <!-- 分组内容 -->
        <ul class="vort-menu-item-group__list" role="group">
            <slot />
        </ul>
    </li>
</template>
