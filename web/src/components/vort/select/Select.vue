<script lang="ts">
// ============ 全局 Select 实例管理器（模块级别，所有实例共享） ============
const selectInstances = new Set<() => void>();

const closeAllOtherSelects = (currentClose: () => void) => {
    selectInstances.forEach((closeFunc) => {
        if (closeFunc !== currentClose) closeFunc();
    });
};

// ============ 导出类型 ============
export type { SelectProps, SelectOption, SelectOptionContext, SelectSize, SelectStatus, SelectMode } from "./types";
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, useAttrs, watch } from "vue";
import type { StyleValue } from "vue";
import type { SelectProps, SelectOption, SelectOptionContext } from "./types";
import "./select.css";
import { CloseCircleFilled, CloseOutlined, DownOutlined, CheckOutlined } from "@/components/vort/icons";
import { getVortPopupContainer, useZIndex } from "@/components/vort/composables";
import { useLocale } from "@/components/vort/locale/useLocale";

defineOptions({ name: "VortSelect", inheritAttrs: false });

const { t: selT } = useLocale("Select");

const attrs = useAttrs();
const attrsStyle = computed<StyleValue | undefined>(() => attrs.style as StyleValue | undefined);

const props = withDefaults(defineProps<SelectProps>(), {
    modelValue: undefined,
    options: () => [],
    placeholder: undefined,
    size: "middle",
    disabled: false,
    status: undefined,
    mode: undefined,
    showSearch: false,
    allowClear: false,
    maxTagCount: undefined,
    maxTagPlaceholder: undefined,
    filterOption: true,
    searchPlaceholder: undefined,
    notFoundContent: undefined,
    listHeight: 256,
    autoClearSearchValue: true,
    getPopupContainer: undefined,
    popupClass: undefined,
    bordered: true
});

const popupContainer = computed(() => props.getPopupContainer?.() ?? getVortPopupContainer());
const placeholder = computed(() => props.placeholder ?? selT("placeholder"));
const notFoundContent = computed(() => props.notFoundContent ?? selT("no_match"));

const zIndex = useZIndex("popup");

const emit = defineEmits<{
    "update:modelValue": [value: string | number | (string | number)[] | undefined];
    change: [value: string | number | (string | number)[] | undefined, option: SelectOption | SelectOption[] | undefined];
    search: [value: string];
    select: [value: string | number, option: SelectOption];
    deselect: [value: string | number, option: SelectOption];
    clear: [];
    focus: [event: FocusEvent];
    blur: [event: FocusEvent];
}>();

// ============ 组件实例状态 ============
const isOpen = ref(false);
const shouldRenderPortal = ref(false);
const searchValue = ref("");
const isHovered = ref(false);
const isFocused = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);
const selectorRef = ref<HTMLElement | null>(null);
const contentRef = ref<HTMLElement | null>(null);
const viewportRef = ref<HTMLElement | null>(null);
const highlightedIndex = ref(-1);

// ============ 定位状态 ============
const dropdownPosition = ref({ top: 0, left: 0, width: 0 });
const actualSide = ref<"top" | "bottom">("bottom");

// 从子组件收集的选项
const slotOptions = ref<SelectOption[]>([]);

// ============ 关闭当前 Select ============
const closeThis = () => {
    isOpen.value = false;
    if (props.autoClearSearchValue) searchValue.value = "";
    isFocused.value = false;
};

selectInstances.add(closeThis);
onBeforeUnmount(() => { selectInstances.delete(closeThis); });

// ============ 子组件选项注册机制 ============
provide<SelectOptionContext>("vortSelectContext", {
    registerOption: (option: SelectOption) => {
        const existIndex = slotOptions.value.findIndex((o) => o.value === option.value);
        if (existIndex === -1) slotOptions.value.push(option);
        else slotOptions.value[existIndex] = option;
    },
    unregisterOption: (value: string | number) => {
        const index = slotOptions.value.findIndex((o) => o.value === value);
        if (index !== -1) slotOptions.value.splice(index, 1);
    }
});

// ============ 计算属性 ============

const mergedOptions = computed(() => {
    if (props.options && props.options.length > 0) return props.options;
    return slotOptions.value;
});

const isMultiple = computed(() => props.mode === "multiple" || props.mode === "tags");

const selectedValues = computed<(string | number)[]>(() => {
    if (props.modelValue === undefined || props.modelValue === null) return [];
    if (isMultiple.value) {
        const arr = Array.isArray(props.modelValue) ? props.modelValue : [props.modelValue];
        return arr.flat() as (string | number)[];
    }
    return [props.modelValue as string | number];
});

const isValueSelected = (val: string | number): boolean => {
    return selectedValues.value.some((v) => String(v) === String(val));
};

const selectedOptions = computed(() => {
    if (isMultiple.value) {
        return selectedValues.value.map((v) => mergedOptions.value.find((o) => String(o.value) === String(v))).filter(Boolean) as SelectOption[];
    }
    return mergedOptions.value.find((o) => String(o.value) === String(props.modelValue));
});

const displayedTags = computed(() => {
    if (!isMultiple.value) return [];
    const all = selectedOptions.value as SelectOption[];
    if (props.maxTagCount === undefined || props.maxTagCount === "responsive") return all;
    return all.slice(0, props.maxTagCount);
});

const hiddenTagCount = computed(() => {
    if (!isMultiple.value) return 0;
    const all = selectedOptions.value as SelectOption[];
    if (props.maxTagCount === undefined || props.maxTagCount === "responsive") return 0;
    return Math.max(0, all.length - (props.maxTagCount as number));
});

const hiddenTagPlaceholder = computed(() => {
    if (hiddenTagCount.value <= 0) return "";
    if (typeof props.maxTagPlaceholder === "function") {
        const all = selectedOptions.value as SelectOption[];
        return props.maxTagPlaceholder(all.slice(props.maxTagCount as number));
    }
    if (props.maxTagPlaceholder) return props.maxTagPlaceholder;
    return `+ ${hiddenTagCount.value} ...`;
});

const filteredOptions = computed(() => {
    if (!searchValue.value || !props.filterOption) return mergedOptions.value;
    const search = searchValue.value.toLowerCase();
    if (typeof props.filterOption === "function") {
        return mergedOptions.value.filter((opt) => (props.filterOption as Function)(searchValue.value, opt));
    }
    return mergedOptions.value.filter((opt) => opt.label.toLowerCase().includes(search) || String(opt.value).toLowerCase().includes(search));
});

const showClearButton = computed(() => {
    if (!props.allowClear || props.disabled) return false;
    return selectedValues.value.length > 0;
});

const isClearButtonVisible = computed(() => showClearButton.value && isHovered.value);

const showPlaceholder = computed(() => {
    return selectedValues.value.length === 0 && !searchValue.value;
});

const displayText = computed(() => {
    if (isMultiple.value) return "";
    const opt = selectedOptions.value as SelectOption | undefined;
    return opt?.label ?? "";
});

// ============ 样式类 ============
const triggerClasses = computed(() => {
    const classes = ["vort-select-selector", `vort-select-${props.size}`];
    if (isMultiple.value) classes.push("vort-select-multiple");
    if (props.status) classes.push(`vort-select-${props.status}`);
    if (props.disabled) classes.push("vort-select-disabled");
    if (!props.bordered) classes.push("vort-select-borderless");
    if (isFocused.value || isOpen.value) classes.push("vort-select-focused");
    if (props.class) classes.push(props.class);
    return classes;
});

const contentClasses = computed(() => {
    const classes = ["vort-select-dropdown"];
    if (props.popupClass) classes.push(props.popupClass);
    return classes;
});

const tagClasses = computed(() => ["vort-select-tag", `vort-select-tag-${props.size}`]);

// ============ 定位 ============
const updatePosition = () => {
    if (!selectorRef.value) return;
    const rect = selectorRef.value.getBoundingClientRect();
    const vh = window.innerHeight;
    const gap = 4;

    const contentEl = contentRef.value;
    const contentHeight = contentEl?.offsetHeight ?? props.listHeight;

    let top = rect.bottom + gap;
    let side: "top" | "bottom" = "bottom";

    if (top + contentHeight > vh - 8 && rect.top - contentHeight - gap >= 8) {
        top = rect.top - contentHeight - gap;
        side = "top";
    }

    dropdownPosition.value = { top, left: rect.left, width: rect.width };
    actualSide.value = side;
};

// ============ 打开/关闭 ============
const openDropdown = () => {
    if (props.disabled || isOpen.value) return;
    closeAllOtherSelects(closeThis);
    shouldRenderPortal.value = true;
    isOpen.value = true;

    const currentVal = isMultiple.value ? undefined : String(props.modelValue ?? "");
    const idx = filteredOptions.value.findIndex((o) => String(o.value) === currentVal);
    highlightedIndex.value = idx >= 0 ? idx : 0;

    nextTick(() => {
        updatePosition();
        if (props.showSearch) inputRef.value?.focus();
        scrollHighlightedIntoView();
    });
};

const closeDropdown = () => {
    if (!isOpen.value) return;
    isOpen.value = false;
    if (props.autoClearSearchValue) searchValue.value = "";
    highlightedIndex.value = -1;
};

const handleAnimationEnd = () => {
    if (!isOpen.value) shouldRenderPortal.value = false;
};

// ============ 事件处理 ============
const handleTriggerClick = () => {
    if (props.disabled) return;
    if (isOpen.value) closeDropdown();
    else openDropdown();
};

const handleOptionClick = (option: SelectOption) => {
    if (option.disabled) return;
    const val = option.value;

    if (isMultiple.value) {
        const current = [...selectedValues.value];
        const strVal = String(val);
        const existIdx = current.findIndex((v) => String(v) === strVal);

        if (existIdx >= 0) {
            current.splice(existIdx, 1);
            emit("update:modelValue", current);
            const opts = current.map((v) => mergedOptions.value.find((o) => String(o.value) === String(v))!).filter(Boolean);
            emit("change", current, opts);
            emit("deselect", val, option);
        } else {
            current.push(val);
            emit("update:modelValue", current);
            const opts = current.map((v) => mergedOptions.value.find((o) => String(o.value) === String(v))!).filter(Boolean);
            emit("change", current, opts);
            emit("select", val, option);
        }
        if (props.autoClearSearchValue) searchValue.value = "";
    } else {
        emit("update:modelValue", val);
        emit("change", val, option);
        emit("select", val, option);
        setTimeout(closeDropdown, 80);
    }
};

const handleClear = (e: Event) => {
    e.stopPropagation();
    if (isMultiple.value) emit("update:modelValue", []);
    else emit("update:modelValue", undefined);
    searchValue.value = "";
    emit("clear");
};

const handleRemoveTag = (val: string | number) => {
    if (props.disabled) return;
    const current = selectedValues.value.filter((v) => String(v) !== String(val));
    emit("update:modelValue", current);
    const opt = mergedOptions.value.find((o) => String(o.value) === String(val));
    if (opt) emit("deselect", val, opt);
};

const handleSearchInput = (e: Event) => {
    const val = (e.target as HTMLInputElement).value;
    searchValue.value = val;
    emit("search", val);
    highlightedIndex.value = 0;
    if (!isOpen.value) openDropdown();
};

const handleFocus = (e: FocusEvent) => {
    isFocused.value = true;
    emit("focus", e);
};

const handleBlur = (e: FocusEvent) => {
    isFocused.value = false;
    emit("blur", e);
};

// ============ 键盘导航 ============
const scrollHighlightedIntoView = () => {
    nextTick(() => {
        const el = viewportRef.value?.querySelector("[data-highlighted]") as HTMLElement | null;
        el?.scrollIntoView({ block: "nearest" });
    });
};

const handleKeydown = (e: KeyboardEvent) => {
    if (!isOpen.value) {
        if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openDropdown();
        }
        return;
    }

    const opts = filteredOptions.value;
    if (!opts.length) return;

    switch (e.key) {
        case "ArrowDown": {
            e.preventDefault();
            let next = highlightedIndex.value + 1;
            while (next < opts.length && opts[next]?.disabled) next++;
            if (next >= opts.length) next = 0;
            while (next < opts.length && opts[next]?.disabled) next++;
            highlightedIndex.value = next;
            scrollHighlightedIntoView();
            break;
        }
        case "ArrowUp": {
            e.preventDefault();
            let prev = highlightedIndex.value - 1;
            while (prev >= 0 && opts[prev]?.disabled) prev--;
            if (prev < 0) prev = opts.length - 1;
            while (prev >= 0 && opts[prev]?.disabled) prev--;
            highlightedIndex.value = prev;
            scrollHighlightedIntoView();
            break;
        }
        case "Enter": {
            e.preventDefault();
            const opt = opts[highlightedIndex.value];
            if (opt && !opt.disabled) handleOptionClick(opt);
            break;
        }
        case "Escape":
            e.preventDefault();
            closeDropdown();
            selectorRef.value?.focus();
            break;
        case "Backspace":
            if (isMultiple.value && !searchValue.value && selectedValues.value.length > 0) {
                const lastVal = selectedValues.value[selectedValues.value.length - 1]!;
                handleRemoveTag(lastVal);
            }
            break;
    }
};

// ============ 点击外部关闭（不使用遮罩，不拦截事件） ============
const handleDocumentMouseDown = (e: MouseEvent) => {
    if (!isOpen.value) return;
    const target = e.target as Node;
    if (selectorRef.value?.contains(target) || contentRef.value?.contains(target)) return;
    closeDropdown();
};

// ============ 滚动/resize 更新位置 ============
const handleScrollOrResize = () => {
    if (isOpen.value) updatePosition();
};

// ============ 监听搜索值变化重置高亮 ============
watch(filteredOptions, () => {
    highlightedIndex.value = 0;
});

// ============ 生命周期 ============
onMounted(() => {
    document.addEventListener("mousedown", handleDocumentMouseDown);
    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
});

onBeforeUnmount(() => {
    document.removeEventListener("mousedown", handleDocumentMouseDown);
    window.removeEventListener("scroll", handleScrollOrResize, true);
    window.removeEventListener("resize", handleScrollOrResize);
});

// ============ 暴露方法 ============
defineExpose({
    focus: () => {
        if (inputRef.value) inputRef.value.focus();
        else selectorRef.value?.focus();
    },
    blur: () => {
        inputRef.value?.blur();
        selectorRef.value?.blur();
    }
});
</script>

<template>
    <div class="vort-select">
    <!-- 隐藏的插槽容器，用于收集 VortSelectOption 子组件 -->
    <div v-show="false">
        <slot />
    </div>

    <!-- 多选模式 -->
    <div
        v-if="isMultiple"
        ref="selectorRef"
        :class="triggerClasses"
        :style="attrsStyle"
        tabindex="0"
        @mouseenter="isHovered = true"
        @mouseleave="isHovered = false"
        @click="handleTriggerClick"
        @keydown="handleKeydown"
        @focus="handleFocus"
        @blur="handleBlur"
    >
        <span v-if="$slots.prefix" class="vort-select-prefix">
            <slot name="prefix" />
        </span>

        <div class="vort-select-selection">
            <!-- 已选标签 -->
            <span v-for="option in displayedTags" :key="String(option.value)" :class="tagClasses">
                <span class="vort-select-tag-text">{{ option.label }}</span>
                <span v-if="!disabled" class="vort-select-tag-remove" @click.stop="handleRemoveTag(option.value)">
                    <CloseOutlined class="vort-select-tag-remove-icon" />
                </span>
            </span>

            <span v-if="hiddenTagCount > 0" class="vort-select-tag vort-select-tag-placeholder">
                {{ hiddenTagPlaceholder }}
            </span>

            <!-- 搜索输入框 -->
            <input
                v-if="showSearch"
                ref="inputRef"
                :value="searchValue"
                :placeholder="showPlaceholder ? placeholder : ''"
                :disabled="disabled"
                class="vort-select-search-input"
                autocomplete="off"
                @input="handleSearchInput"
                @keydown="handleKeydown"
            />

            <span v-else-if="showPlaceholder" class="vort-select-placeholder">
                {{ placeholder }}
            </span>
        </div>

        <span class="vort-select-suffix">
            <slot name="suffix" />
            <span class="vort-select-indicator">
                <span class="vort-select-clear" :class="{ 'vort-select-clear-visible': isClearButtonVisible }" @click="handleClear" @mousedown.prevent>
                    <CloseCircleFilled />
                </span>
                <span class="vort-select-arrow-wrapper" :class="{ 'vort-select-arrow-wrapper-hidden': isClearButtonVisible }">
                    <DownOutlined :class="['vort-select-arrow', isOpen && 'vort-select-arrow-open']" />
                </span>
            </span>
        </span>
    </div>

    <!-- 单选模式 -->
    <div
        v-else
        ref="selectorRef"
        :class="triggerClasses"
        :style="attrsStyle"
        tabindex="0"
        @mouseenter="isHovered = true"
        @mouseleave="isHovered = false"
        @click="handleTriggerClick"
        @keydown="handleKeydown"
        @focus="handleFocus"
        @blur="handleBlur"
    >
        <span v-if="$slots.prefix" class="vort-select-prefix">
            <slot name="prefix" />
        </span>

        <div class="vort-select-selection">
            <input
                v-if="showSearch"
                ref="inputRef"
                :value="isOpen ? searchValue : displayText"
                :placeholder="displayText || placeholder"
                :disabled="disabled"
                class="vort-select-search-input"
                autocomplete="off"
                @input="handleSearchInput"
                @keydown="handleKeydown"
            />

            <template v-else>
                <span v-if="selectedOptions && !isMultiple" :class="['vort-select-value', isOpen && 'vort-select-value-focused']">
                    <component v-if="(selectedOptions as SelectOption).render" :is="(selectedOptions as SelectOption).render" />
                    <template v-else>{{ displayText }}</template>
                </span>
                <span v-else-if="!displayText" class="vort-select-placeholder">
                    {{ placeholder }}
                </span>
            </template>
        </div>

        <span class="vort-select-suffix">
            <slot name="suffix" />
            <span class="vort-select-indicator">
                <span class="vort-select-clear" :class="{ 'vort-select-clear-visible': isClearButtonVisible }" @click="handleClear" @mousedown.prevent>
                    <CloseCircleFilled />
                </span>
                <span class="vort-select-arrow-wrapper" :class="{ 'vort-select-arrow-wrapper-hidden': isClearButtonVisible }">
                    <DownOutlined :class="['vort-select-arrow', isOpen && 'vort-select-arrow-open']" />
                </span>
            </span>
        </span>
    </div>

    <!-- 下拉内容 -->
    <Teleport v-if="shouldRenderPortal" :to="popupContainer">
        <div
            ref="contentRef"
            :class="contentClasses"
            :style="{
                position: 'fixed',
                top: `${dropdownPosition.top}px`,
                left: `${dropdownPosition.left}px`,
                minWidth: `${dropdownPosition.width}px`,
                zIndex: zIndex
            }"
            :data-state="isOpen ? 'open' : 'closed'"
            :data-side="actualSide"
            @animationend="handleAnimationEnd"
            @mousedown.prevent
        >
            <div v-if="$slots.dropdownSearch" class="vort-select-dropdown-search">
                <slot name="dropdownSearch" />
            </div>

            <div ref="viewportRef" class="vort-select-dropdown-viewport" :style="{ maxHeight: `${listHeight}px` }">
                <!-- 空状态 -->
                <div v-if="filteredOptions.length === 0" class="vort-select-empty">
                    {{ notFoundContent }}
                </div>

                <!-- 选项列表 -->
                <div
                    v-for="(option, index) in filteredOptions"
                    :key="String(option.value)"
                    class="vort-select-option"
                    :data-highlighted="index === highlightedIndex ? '' : undefined"
                    :data-state="isValueSelected(option.value) ? 'checked' : undefined"
                    :data-disabled="option.disabled ? '' : undefined"
                    @click="handleOptionClick(option)"
                    @mouseenter="highlightedIndex = index"
                >
                    <span class="vort-select-option-content">
                        <component v-if="option.render" :is="option.render" />
                        <template v-else>{{ option.label }}</template>
                    </span>

                    <span v-if="isMultiple && isValueSelected(option.value)" class="vort-select-option-check">
                        <CheckOutlined class="vort-select-check-icon" />
                    </span>
                </div>
            </div>

            <div v-if="$slots.dropdownRender" class="vort-select-dropdown-footer">
                <slot name="dropdownRender" />
            </div>
        </div>
    </Teleport>
    </div>
</template>

<style scoped>
/* ========================================
   根容器 - 替代原 ComboboxRoot 的包裹层
   ======================================== */
.vort-select {
    position: relative;
}

/* ========================================
   基础样式 - 选择器触发器
   ======================================== */
.vort-select-selector {
    --_border-color: var(--vort-border, #d9d9d9);
    --_focus-color: var(--vort-primary, #1456f0);
    --_focus-shadow: var(--vort-primary-shadow, rgba(20, 86, 240, 0.1));
    --_bg-color: #fff;

    position: relative;
    display: inline-flex;
    align-items: center;
    width: 100%;
    border: 1px solid var(--_border-color);
    border-radius: var(--vort-radius, 6px);
    background: var(--_bg-color);
    cursor: pointer;
    transition: var(--vort-transition-all, all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1));
}

.vort-select-selector:hover:not(.vort-select-disabled) {
    border-color: var(--_focus-color);
}

.vort-select-focused:not(.vort-select-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

.vort-select-error {
    --_border-color: var(--vort-error, #ff4d4f);
    --_focus-color: var(--vort-error, #ff4d4f);
    --_focus-shadow: rgba(255, 77, 79, 0.06);
}

.vort-select-warning {
    --_border-color: var(--vort-warning, #faad14);
    --_focus-color: var(--vort-warning, #faad14);
    --_focus-shadow: rgba(250, 173, 20, 0.1);
}

.vort-select-disabled {
    --_bg-color: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

.vort-select-borderless { border-color: transparent; background: transparent; }
.vort-select-borderless:hover:not(.vort-select-disabled) { border-color: transparent; background: rgba(0, 0, 0, 0.04); }
.vort-select-borderless.vort-select-focused { border-color: transparent; background: transparent; box-shadow: none; }

/* 尺寸 */
.vort-select-large { height: var(--vort-height-lg, 40px); padding: 0 11px; font-size: var(--vort-font-size-md, 16px); }
.vort-select-large.vort-select-multiple { min-height: var(--vort-height-lg, 40px); height: auto; }
.vort-select-middle { height: var(--vort-height-md, 32px); padding: 0 11px; font-size: var(--vort-font-size-sm, 14px); }
.vort-select-middle.vort-select-multiple { min-height: var(--vort-height-md, 32px); height: auto; }
.vort-select-small { height: var(--vort-height-sm, 24px); padding: 0 7px; font-size: var(--vort-font-size-sm, 14px); }
.vort-select-small.vort-select-multiple { min-height: var(--vort-height-sm, 24px); height: auto; }

/* 内部元素 */
.vort-select-prefix { display: flex; align-items: center; flex-shrink: 0; margin-right: 4px; color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25)); }
.vort-select-selection { display: flex; flex-wrap: wrap; align-items: center; flex: 1; min-width: 0; gap: 4px; padding: 3px 0; }
.vort-select-suffix { display: flex; align-items: center; flex-shrink: 0; margin-left: 4px; gap: 4px; }
.vort-select-indicator { position: relative; display: inline-flex; align-items: center; justify-content: center; width: 14px; height: 14px; flex-shrink: 0; }

/* 清除按钮 */
.vort-select-clear { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 14px; color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25)); cursor: pointer; opacity: 0; visibility: hidden; pointer-events: none; transition: color var(--vort-transition-colors, 0.1s), opacity var(--vort-transition-colors, 0.1s); }
.vort-select-clear-visible { opacity: 1; visibility: visible; pointer-events: auto; }
.vort-select-clear:hover { color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45)); }

/* 下拉箭头 */
.vort-select-arrow-wrapper { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; line-height: 1; transition: opacity var(--vort-transition-colors, 0.1s); }
.vort-select-arrow-wrapper-hidden { opacity: 0; visibility: hidden; pointer-events: none; }
.vort-select-arrow { font-size: 12px; color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25)); transition: transform var(--vort-transition-colors, 0.2s); }
.vort-select-arrow-open { transform: rotate(180deg); }

/* 占位符/值 */
.vort-select-placeholder { color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25)); }
.vort-select-value { display: flex; align-items: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--vort-text, rgba(0, 0, 0, 0.88)); transition: color var(--vort-transition-colors, 0.2s); }
.vort-select-value-focused { color: rgba(0, 0, 0, 0.25); }

/* 搜索输入 */
.vort-select-search-input { flex: 1; min-width: 60px; width: 100%; background: transparent; border: none; outline: none; color: var(--vort-text, rgba(0, 0, 0, 0.88)); font-size: inherit; padding: 0; }
.vort-select-search-input::placeholder { color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25)); }

/* 多选标签 */
.vort-select-tag { display: inline-flex; align-items: center; gap: 4px; max-width: 100%; padding: 0 4px; background: rgba(0, 0, 0, 0.06); border-radius: var(--vort-radius-sm, 4px); }
.vort-select-tag-placeholder { color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65)); }
.vort-select-tag-large { height: 24px; font-size: var(--vort-font-size-sm, 14px); }
.vort-select-tag-middle { height: 22px; font-size: var(--vort-font-size-sm, 14px); }
.vort-select-tag-small { height: 16px; font-size: var(--vort-font-size-xs, 12px); }
.vort-select-tag-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vort-select-tag-remove { display: flex; align-items: center; justify-content: center; width: 14px; height: 14px; border-radius: var(--vort-radius-sm, 4px); cursor: pointer; transition: background-color var(--vort-transition-colors, 0.1s); }
.vort-select-tag-remove:hover { background: rgba(0, 0, 0, 0.1); }
.vort-select-tag-remove-icon { font-size: 10px; color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45)); }

/* 下拉面板内元素（scoped 部分） */
.vort-select-dropdown-search { padding: 8px; border-bottom: 1px solid var(--vort-border, #d9d9d9); }
.vort-select-dropdown-viewport { padding: 4px; overflow-y: auto; }
.vort-select-dropdown-footer { border-top: 1px solid var(--vort-border, #d9d9d9); }
.vort-select-empty { padding: 24px 12px; text-align: center; font-size: var(--vort-font-size-sm, 14px); color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25)); }
.vort-select-option { position: relative; display: flex; align-items: center; width: 100%; padding: 5px 12px; font-size: var(--vort-font-size-sm, 14px); line-height: 22px; cursor: pointer; user-select: none; outline: none; border-radius: var(--vort-radius-sm, 4px); transition: background-color var(--vort-transition-colors, 0.15s); }
.vort-select-option:hover { background: rgba(0, 0, 0, 0.04); }
.vort-select-option[data-highlighted] { background: rgba(0, 0, 0, 0.04); }
.vort-select-option[data-state="checked"] { background: var(--vort-primary-bg, #e8f0fe); font-weight: 500; }
.vort-select-option[data-disabled] { opacity: 0.5; pointer-events: none; }
.vort-select-option-content { flex: 1; white-space: nowrap; }
.vort-select-option-check { margin-left: 8px; }
.vort-select-check-icon { width: 16px; height: 16px; color: var(--vort-primary, #1456f0); }
</style>
