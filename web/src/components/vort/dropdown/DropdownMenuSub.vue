<script setup lang="ts">
/** Vort DropdownMenuSub - 下拉菜单子菜单组件 */
import { computed, ref, watch, nextTick, onMounted, onBeforeUnmount } from "vue";
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
const shouldRenderPortal = ref(false);
const triggerRef = ref<HTMLElement | null>(null);
const contentRef = ref<HTMLElement | null>(null);
const contentPosition = ref({ top: 0, left: 0 });
const actualSide = ref<"left" | "right">("right");
let enterTimer: ReturnType<typeof setTimeout> | null = null;
let leaveTimer: ReturnType<typeof setTimeout> | null = null;

watch(isOpen, (val) => {
    if (val) {
        shouldRenderPortal.value = true;
        nextTick(updatePosition);
    }
});

const handleAnimationEnd = () => {
    if (!isOpen.value) {
        shouldRenderPortal.value = false;
    }
};

const updatePosition = () => {
    if (!triggerRef.value || !contentRef.value) return;
    const rect = triggerRef.value.getBoundingClientRect();
    const contentWidth = contentRef.value.offsetWidth;
    const contentHeight = contentRef.value.offsetHeight;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const gap = 4;

    let left = rect.right + gap;
    let top = rect.top - 4;
    let side: "left" | "right" = "right";

    if (left + contentWidth > vw - 8) {
        left = rect.left - contentWidth - gap;
        side = "left";
    }
    if (left < 8) {
        left = 8;
        side = "right";
    }

    top = Math.max(8, Math.min(top, vh - contentHeight - 8));

    contentPosition.value = { top, left };
    actualSide.value = side;
};

const clearTimers = () => {
    if (enterTimer) { clearTimeout(enterTimer); enterTimer = null; }
    if (leaveTimer) { clearTimeout(leaveTimer); leaveTimer = null; }
};

const handleMouseEnter = () => {
    if (props.disabled) return;
    clearTimers();
    enterTimer = setTimeout(() => { isOpen.value = true; }, 100);
};

const handleMouseLeave = () => {
    clearTimers();
    leaveTimer = setTimeout(() => { isOpen.value = false; }, 150);
};

const handleContentMouseEnter = () => {
    clearTimers();
};

const handleContentMouseLeave = () => {
    clearTimers();
    leaveTimer = setTimeout(() => { isOpen.value = false; }, 150);
};

const handleKeydown = (e: KeyboardEvent) => {
    if (props.disabled) return;
    if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        isOpen.value = true;
        nextTick(() => {
            const firstItem = contentRef.value?.querySelector<HTMLElement>('[role="menuitem"]:not([data-disabled])');
            firstItem?.focus();
        });
    }
};

const handleContentKeydown = (e: KeyboardEvent) => {
    if (e.key === "ArrowLeft" || e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        isOpen.value = false;
        triggerRef.value?.focus();
    }
};

const handleDocumentMouseDown = (e: MouseEvent) => {
    if (!isOpen.value) return;
    const target = e.target as Node;
    if (triggerRef.value?.contains(target) || contentRef.value?.contains(target)) return;
    isOpen.value = false;
};

onMounted(() => {
    document.addEventListener("mousedown", handleDocumentMouseDown);
});

onBeforeUnmount(() => {
    document.removeEventListener("mousedown", handleDocumentMouseDown);
    clearTimers();
});

const triggerClasses = computed(() => {
    const classes = ["vort-dropdown-menu-sub-trigger"];
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <div
        ref="triggerRef"
        :class="triggerClasses"
        role="menuitem"
        :tabindex="disabled ? undefined : -1"
        :data-disabled="disabled ? '' : undefined"
        :data-state="isOpen ? 'open' : 'closed'"
        aria-haspopup="menu"
        :aria-expanded="isOpen"
        @mouseenter="handleMouseEnter"
        @mouseleave="handleMouseLeave"
        @keydown="handleKeydown"
    >
        <slot name="title">{{ title }}</slot>
        <ChevronRightOutlined class="vort-dropdown-menu-sub-trigger-arrow" />
    </div>

    <Teleport v-if="shouldRenderPortal" to="body">
        <div
            ref="contentRef"
            class="vort-dropdown-menu-sub-content vort-dropdown"
            :style="{ position: 'fixed', top: `${contentPosition.top}px`, left: `${contentPosition.left}px`, zIndex: 1060 }"
            :data-state="isOpen ? 'open' : 'closed'"
            :data-side="actualSide"
            data-slot="dropdown-content"
            role="menu"
            tabindex="-1"
            @mouseenter="handleContentMouseEnter"
            @mouseleave="handleContentMouseLeave"
            @animationend="handleAnimationEnd"
            @keydown="handleContentKeydown"
        >
            <slot />
        </div>
    </Teleport>
</template>
