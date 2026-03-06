<script setup lang="ts">
/** Vort DropdownMenuSub - 下拉菜单子菜单组件 */
import { computed, ref, watch } from "vue";
import { DropdownMenuSub as RekaDropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuPortal, DropdownMenuSubContent } from "reka-ui";
import { ChevronRightOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortDropdownMenuSub" });

interface Props {
    /** 子菜单标题 */
    title?: string;
    /** 是否禁用 */
    disabled?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    title: "",
    disabled: false
});

const isOpen = ref(false);
const shouldRenderPortal = ref(false); // 控制 Portal 是否渲染，避免产生 <!--v-if--> 注释

// 监听打开状态
watch(isOpen, (val) => {
    if (val) {
        shouldRenderPortal.value = true;
    }
});

// 处理关闭动画完成后移除 Portal
const handleAnimationEnd = () => {
    if (!isOpen.value) {
        shouldRenderPortal.value = false;
    }
};

const triggerClasses = computed(() => {
    const classes = ["vort-dropdown-menu-sub-trigger"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <RekaDropdownMenuSub v-model:open="isOpen">
        <DropdownMenuSubTrigger :class="triggerClasses" :disabled="disabled">
            <slot name="title">{{ title }}</slot>
            <ChevronRightOutlined class="vort-dropdown-menu-sub-trigger-arrow" />
        </DropdownMenuSubTrigger>

        <DropdownMenuPortal v-if="shouldRenderPortal">
            <DropdownMenuSubContent class="vort-dropdown-menu-sub-content vort-dropdown" :side-offset="4" :align-offset="-4" @animationend="handleAnimationEnd">
                <slot />
            </DropdownMenuSubContent>
        </DropdownMenuPortal>
    </RekaDropdownMenuSub>
</template>
