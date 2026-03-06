<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from "vue";
import { Input } from "@/components/vort/input";
import { getVortPopupContainer, useZIndex } from "@/components/vort/composables";

defineOptions({ name: "VortAutoComplete" });

// 使用 z-index 上下文，在 Dialog/Drawer 内时自动获得更高的层级
const zIndex = useZIndex("popup");
const popupContainer = computed(() => getVortPopupContainer());

/** Vort AutoComplete - 自动完成组件 */

export interface AutoCompleteOption {
    /** 选项值 */
    value: string | number;
    /** 选项标签（显示文本），不传则使用 value */
    label?: string;
    /** 是否禁用 */
    disabled?: boolean;
}

type InputSize = "large" | "middle" | "small";
type InputStatus = "error" | "warning";

interface Props {
    /** 输入框内容（v-model） */
    modelValue?: string;
    /** 默认值 */
    defaultValue?: string;
    /** 选项数据源 */
    options?: AutoCompleteOption[];
    /** 输入框占位文本 */
    placeholder?: string;
    /** 输入框尺寸 */
    size?: InputSize;
    /** 输入框状态 */
    status?: InputStatus;
    /** 是否禁用 */
    disabled?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 是否支持清除 */
    allowClear?: boolean;
    /** 自定义类名 */
    class?: string;
    /** 空数据时显示的内容 */
    notFoundContent?: string | null;
    /** 是否根据输入项进行筛选，默认按 value 进行筛选 */
    filterOption?: boolean | ((inputValue: string, option: AutoCompleteOption) => boolean);
    /** 是否默认高亮第一个选项 */
    defaultActiveFirstOption?: boolean;
    /** 使浮层跟随滚动（默认 false） */
    autoAdjustOverflow?: boolean;
    /** 下拉菜单的最大高度 */
    listHeight?: number;
    /** 是否在选中后自动失焦 */
    autoBlur?: boolean;
    /** 选中后是否回填到输入框 */
    backfill?: boolean;
    /** 是否打开下拉菜单 */
    open?: boolean;
    /** 默认是否打开下拉菜单 */
    defaultOpen?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
    modelValue: undefined,
    defaultValue: "",
    options: () => [],
    placeholder: "请输入",
    size: "middle",
    disabled: false,
    bordered: true,
    allowClear: false,
    notFoundContent: undefined,
    filterOption: true,
    defaultActiveFirstOption: true,
    autoAdjustOverflow: true,
    listHeight: 256,
    autoBlur: false,
    backfill: false,
    open: undefined,
    defaultOpen: false
});

const emit = defineEmits<{
    "update:modelValue": [value: string];
    "update:open": [value: boolean];
    change: [value: string];
    search: [value: string];
    select: [value: string, option: AutoCompleteOption];
    focus: [event: FocusEvent];
    blur: [event: FocusEvent];
    clear: [];
    dropdownVisibleChange: [visible: boolean];
}>();

// ============ 组件状态 ============
const inputRef = ref<InstanceType<typeof Input> | null>(null);
const dropdownRef = ref<HTMLElement | null>(null);
const triggerRef = ref<HTMLElement | null>(null);
const isOpen = ref(props.defaultOpen);
const shouldRenderTeleport = ref(false); // 控制 Teleport 是否渲染，避免产生 <!--v-if--> 注释
const innerValue = ref(props.modelValue ?? props.defaultValue ?? "");
const activeIndex = ref(-1);
const position = ref({ top: 0, left: 0, width: 0 });
const isFocused = ref(false);
const placement = ref<"top" | "bottom">("bottom");
const justSelected = ref(false); // 标记是否刚选择了选项，防止重新打开

// ============ 受控/非受控模式 ============
const isControlledOpen = computed(() => props.open !== undefined);
const dropdownVisible = computed(() => {
    if (isControlledOpen.value) {
        return props.open;
    }
    return isOpen.value;
});

// ============ 过滤后的选项 ============
const filteredOptions = computed(() => {
    if (!props.filterOption || !innerValue.value) {
        return props.options;
    }

    const searchValue = innerValue.value.toLowerCase();

    const filterOption = props.filterOption;
    if (typeof filterOption === "function") {
        return props.options.filter((opt) => filterOption(innerValue.value, opt));
    }

    // 默认过滤逻辑：匹配 value 或 label
    return props.options.filter((opt) => {
        const label = (opt.label ?? String(opt.value)).toLowerCase();
        const value = String(opt.value).toLowerCase();
        return label.includes(searchValue) || value.includes(searchValue);
    });
});

// ============ 是否显示空状态 ============
const showEmpty = computed(() => {
    return filteredOptions.value.length === 0 && props.notFoundContent !== null;
});

// ============ 监听 modelValue 变化 ============
watch(
    () => props.modelValue,
    (newVal) => {
        if (newVal !== undefined) {
            innerValue.value = newVal;
        }
    }
);

// ============ 计算下拉位置 ============
const updatePosition = () => {
    if (!triggerRef.value) return;

    const rect = triggerRef.value.getBoundingClientRect();
    const dropdownHeight = Math.min(props.listHeight + 16, 300); // 估算高度用于判断空间
    const viewportHeight = window.innerHeight;

    let top = rect.bottom + 4;

    // 边界检测：如果下方空间不够，则显示在上方
    if (props.autoAdjustOverflow && top + dropdownHeight > viewportHeight) {
        // 向上弹出：设置为输入框顶部减去间距，用 transform 偏移自身高度
        placement.value = "top";
        top = rect.top - 4;
    } else {
        placement.value = "bottom";
    }

    position.value = {
        top,
        left: rect.left,
        width: rect.width
    };
};

// ============ 打开/关闭下拉 ============
const openDropdown = () => {
    if (props.disabled) return;

    // 先计算位置，再打开下拉，避免动画从 (0,0) 开始
    updatePosition();

    shouldRenderTeleport.value = true; // 先渲染 Teleport
    if (!isControlledOpen.value) {
        isOpen.value = true;
    }
    emit("update:open", true);
    emit("dropdownVisibleChange", true);

    nextTick(() => {
        // 默认高亮第一个选项
        if (props.defaultActiveFirstOption && filteredOptions.value.length > 0) {
            activeIndex.value = 0;
        }
    });
};

const closeDropdown = () => {
    if (!isControlledOpen.value) {
        isOpen.value = false;
    }
    emit("update:open", false);
    emit("dropdownVisibleChange", false);
    activeIndex.value = -1;
};

// Transition 离开动画完成后移除 Teleport
const handleAfterLeave = () => {
    shouldRenderTeleport.value = false;
};

// ============ 事件处理 ============
const handleInput = (e: Event) => {
    const target = e.target as HTMLInputElement;
    const value = target.value;

    innerValue.value = value;
    emit("update:modelValue", value);
    emit("change", value);
    emit("search", value);

    // 输入时打开下拉
    if (!dropdownVisible.value) {
        openDropdown();
    } else {
        // 更新位置和重置高亮
        updatePosition();
        if (props.defaultActiveFirstOption && filteredOptions.value.length > 0) {
            activeIndex.value = 0;
        } else {
            activeIndex.value = -1;
        }
    }
};

const handleFocus = (e: FocusEvent) => {
    isFocused.value = true;
    emit("focus", e);

    // 如果是刚选择完选项后的聚焦，不重新打开下拉
    if (justSelected.value) {
        justSelected.value = false;
        return;
    }

    // 聚焦时打开下拉（如果有选项）
    if (props.options.length > 0) {
        openDropdown();
    }
};

const handleBlur = (e: FocusEvent) => {
    isFocused.value = false;
    emit("blur", e);

    // 延迟关闭，允许点击选项
    setTimeout(() => {
        if (!isFocused.value) {
            closeDropdown();
        }
    }, 150);
};

const handleClear = () => {
    innerValue.value = "";
    emit("update:modelValue", "");
    emit("change", "");
    emit("clear");
    inputRef.value?.focus();
};

const handleSelect = (option: AutoCompleteOption) => {
    if (option.disabled) return;

    const value = option.label ?? String(option.value);

    innerValue.value = value;
    emit("update:modelValue", value);
    emit("change", value);
    emit("select", value, option);

    closeDropdown();

    if (props.autoBlur) {
        inputRef.value?.blur();
    } else {
        // 设置标志，防止 focus 事件重新打开下拉
        justSelected.value = true;
        inputRef.value?.focus();
    }
};

const handleOptionMouseEnter = (index: number) => {
    const option = filteredOptions.value[index];
    if (option && !option.disabled) {
        activeIndex.value = index;
    }
};

const handleKeydown = (e: KeyboardEvent) => {
    if (!dropdownVisible.value) {
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            openDropdown();
            return;
        }
        return;
    }

    switch (e.key) {
        case "ArrowDown":
            e.preventDefault();
            navigateOptions(1);
            break;
        case "ArrowUp":
            e.preventDefault();
            navigateOptions(-1);
            break;
        case "Enter":
            e.preventDefault();
            if (activeIndex.value >= 0) {
                const option = filteredOptions.value[activeIndex.value];
                if (option && !option.disabled) {
                    handleSelect(option);
                }
            }
            break;
        case "Escape":
            e.preventDefault();
            closeDropdown();
            break;
    }
};

const navigateOptions = (direction: number) => {
    const options = filteredOptions.value;
    if (options.length === 0) return;

    let newIndex = activeIndex.value + direction;

    // 循环导航
    if (newIndex < 0) {
        newIndex = options.length - 1;
    } else if (newIndex >= options.length) {
        newIndex = 0;
    }

    // 跳过禁用选项
    const startIndex = newIndex;
    while (options[newIndex]?.disabled) {
        newIndex += direction;
        if (newIndex < 0) newIndex = options.length - 1;
        if (newIndex >= options.length) newIndex = 0;
        if (newIndex === startIndex) break; // 所有选项都禁用
    }

    activeIndex.value = newIndex;

    // backfill：将高亮选项回填到输入框
    const option = options[newIndex];
    if (props.backfill && option) {
        innerValue.value = option.label ?? String(option.value);
        emit("update:modelValue", innerValue.value);
    }

    // 滚动到可视区域
    scrollToOption(newIndex);
};

const scrollToOption = (index: number) => {
    nextTick(() => {
        const dropdown = dropdownRef.value;
        if (!dropdown) return;

        const items = dropdown.querySelectorAll(".vort-auto-complete-item");
        const item = items[index] as HTMLElement;
        if (!item) return;

        const dropdownRect = dropdown.getBoundingClientRect();
        const itemRect = item.getBoundingClientRect();

        if (itemRect.top < dropdownRect.top) {
            item.scrollIntoView({ block: "start" });
        } else if (itemRect.bottom > dropdownRect.bottom) {
            item.scrollIntoView({ block: "end" });
        }
    });
};

// ============ 点击外部关闭 ============
const handleClickOutside = (e: MouseEvent) => {
    const target = e.target as Node;
    if (triggerRef.value?.contains(target) || dropdownRef.value?.contains(target)) {
        return;
    }
    closeDropdown();
};

// ============ 滚动/resize 时更新位置 ============
const handleScroll = () => {
    if (dropdownVisible.value) {
        updatePosition();
    }
};

// ============ 生命周期 ============
onMounted(() => {
    document.addEventListener("click", handleClickOutside);
    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", handleScroll);
});

onUnmounted(() => {
    document.removeEventListener("click", handleClickOutside);
    window.removeEventListener("scroll", handleScroll, true);
    window.removeEventListener("resize", handleScroll);
});

// ============ 样式类（简洁的类名切换） ============

/** 选项类名 */
const getItemClasses = (index: number, option: AutoCompleteOption) => {
    const classes = ["vort-auto-complete-item"];

    if (index === activeIndex.value && !option.disabled) {
        classes.push("vort-auto-complete-item-active");
    }
    if (option.disabled) {
        classes.push("vort-auto-complete-item-disabled");
    }

    return classes;
};

// ============ 暴露方法 ============
defineExpose({
    /** 聚焦输入框 */
    focus: () => inputRef.value?.focus(),
    /** 失焦输入框 */
    blur: () => inputRef.value?.blur(),
    /** 获取输入框元素 */
    input: inputRef
});
</script>

<template>
    <div ref="triggerRef" class="vort-auto-complete" :class="props.class">
        <!-- 输入框 -->
        <Input
            ref="inputRef"
            :model-value="innerValue"
            :placeholder="placeholder"
            :size="size"
            :status="status"
            :disabled="disabled"
            :bordered="bordered"
            :allow-clear="allowClear"
            @input="handleInput"
            @focus="handleFocus"
            @blur="handleBlur"
            @keydown="handleKeydown"
            @clear="handleClear"
        >
            <template v-if="$slots.prefix" #prefix>
                <slot name="prefix" />
            </template>
            <template v-if="$slots.suffix" #suffix>
                <slot name="suffix" />
            </template>
        </Input>

        <!-- 下拉菜单 -->
        <Teleport v-if="shouldRenderTeleport" :to="popupContainer">
            <Transition :name="placement === 'top' ? 'vort-slide-down' : 'vort-slide-up'" appear @after-leave="handleAfterLeave">
                <div
                    v-if="dropdownVisible && (filteredOptions.length > 0 || showEmpty)"
                    ref="dropdownRef"
                    class="vort-auto-complete-dropdown"
                    :style="{
                        top: `${position.top}px`,
                        left: `${position.left}px`,
                        width: `${position.width}px`,
                        zIndex: zIndex,
                        transform: placement === 'top' ? 'translateY(-100%)' : 'none'
                    }"
                >
                    <div class="vort-auto-complete-list" :style="{ maxHeight: `${listHeight}px` }">
                        <!-- 选项列表 -->
                        <template v-if="filteredOptions.length > 0">
                            <div
                                v-for="(option, index) in filteredOptions"
                                :key="String(option.value)"
                                :class="getItemClasses(index, option)"
                                @click="handleSelect(option)"
                                @mouseenter="handleOptionMouseEnter(index)"
                            >
                                <!-- 自定义选项渲染 -->
                                <slot name="option" :option="option" :index="index">
                                    {{ option.label ?? option.value }}
                                </slot>
                            </div>
                        </template>

                        <!-- 空状态 -->
                        <div v-else-if="showEmpty" class="vort-auto-complete-empty">
                            <slot name="notFoundContent">
                                {{ notFoundContent ?? "无匹配结果" }}
                            </slot>
                        </div>
                    </div>
                </div>
            </Transition>
        </Teleport>
    </div>
</template>

<style scoped>
/* ========================================
   基础样式
   ======================================== */
.vort-auto-complete {
    display: inline-block;
    width: 100%;
}

/* ========================================
   下拉面板
   ======================================== */
.vort-auto-complete-dropdown {
    position: fixed;
    background: #fff;
    border-radius: var(--vort-radius-lg, 8px);
    overflow: hidden;
    padding: 4px;
    box-shadow:
        0 6px 16px 0 rgba(0, 0, 0, 0.08),
        0 3px 6px -4px rgba(0, 0, 0, 0.12),
        0 9px 28px 8px rgba(0, 0, 0, 0.05);
}

/* ========================================
   选项列表
   ======================================== */
.vort-auto-complete-list {
    overflow-y: auto;
}

.vort-auto-complete-item {
    padding: 5px 12px;
    font-size: var(--vort-font-size-sm, 14px);
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    cursor: pointer;
    user-select: none;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    border-radius: var(--vort-radius-sm, 4px);
    transition: background-color var(--vort-transition-colors, 0.15s);
}

.vort-auto-complete-item:hover:not(.vort-auto-complete-item-disabled) {
    background: rgba(0, 0, 0, 0.04);
}

.vort-auto-complete-item-active {
    background: rgba(0, 0, 0, 0.04);
}

.vort-auto-complete-item-disabled {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

/* ========================================
   空状态
   ======================================== */
.vort-auto-complete-empty {
    padding: 24px 12px;
    text-align: center;
    font-size: var(--vort-font-size-sm, 14px);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   动画 - 复用 motion.css 中的通用下拉动画
   ======================================== */
.vort-slide-up-enter-active {
    animation: vort-dropdown-slide-up-in var(--vort-duration-normal, 150ms) var(--vort-ease-decelerate, cubic-bezier(0, 0, 0.2, 1));
    transform-origin: top center;
}

.vort-slide-up-leave-active {
    animation: vort-dropdown-slide-up-out var(--vort-duration-normal, 150ms) var(--vort-ease-accelerate, cubic-bezier(0.4, 0, 1, 1));
    transform-origin: top center;
}

.vort-slide-down-enter-active {
    animation: vort-dropdown-slide-down-in var(--vort-duration-normal, 150ms) var(--vort-ease-decelerate, cubic-bezier(0, 0, 0.2, 1));
    transform-origin: bottom center;
}

.vort-slide-down-leave-active {
    animation: vort-dropdown-slide-down-out var(--vort-duration-normal, 150ms) var(--vort-ease-accelerate, cubic-bezier(0.4, 0, 1, 1));
    transform-origin: bottom center;
}

/* ========================================
   滚动条样式
   ======================================== */
.vort-auto-complete-list::-webkit-scrollbar {
    width: 6px;
}

.vort-auto-complete-list::-webkit-scrollbar-thumb {
    background-color: rgba(0, 0, 0, 0.15);
    border-radius: 3px;
}

.vort-auto-complete-list::-webkit-scrollbar-track {
    background: transparent;
}

/* ========================================
   响应用户"减少动画"偏好设置
   ======================================== */
@media (prefers-reduced-motion: reduce) {
    .vort-slide-up-enter-active,
    .vort-slide-up-leave-active,
    .vort-slide-down-enter-active,
    .vort-slide-down-leave-active {
        animation-duration: 0ms;
    }
}
</style>
