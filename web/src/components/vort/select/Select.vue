<script lang="ts">
// ============ 空值哨兵 ============
// reka-ui ComboboxItem 禁止 value 为空字符串，
// 用内部哨兵替代，对外 API 仍支持 value=""
const EMPTY_SENTINEL = "__vort_select_empty__";
const toInternal = (v: string) => (v === "" ? EMPTY_SENTINEL : v);
const fromInternal = (v: string) => (v === EMPTY_SENTINEL ? "" : v);

// ============ 全局 Select 实例管理器（模块级别，所有实例共享） ============
// 用于协调多个 Select 实例，确保同时只有一个打开
const selectInstances = new Set<() => void>();
let lastClosedSelectSelector: HTMLElement | null = null;
let lastClosedSelectAnimationAt = 0;
let lastGlobalPointerDownTarget: EventTarget | null = null;
let lastGlobalPointerDownAt = 0;

// 关闭所有其他 Select
const closeAllOtherSelects = (currentClose: () => void) => {
    selectInstances.forEach((closeFunc) => {
        if (closeFunc !== currentClose) {
            closeFunc();
        }
    });
};

// ============ 导出类型 ============
export type { SelectProps, SelectOption, SelectOptionContext, SelectSize, SelectStatus, SelectMode } from "./types";
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, useAttrs } from "vue";
import type { ComponentPublicInstance, StyleValue } from "vue";
import type { SelectProps, SelectOption, SelectOptionContext } from "./types";
import "./select.css";
import {
    ComboboxAnchor,
    ComboboxContent,
    ComboboxEmpty,
    ComboboxInput,
    ComboboxItem,
    ComboboxItemIndicator,
    ComboboxPortal,
    ComboboxRoot,
    ComboboxTrigger,
    ComboboxViewport,
    TagsInputInput,
    TagsInputItem,
    TagsInputItemDelete,
    TagsInputItemText,
    TagsInputRoot
} from "reka-ui";
import { CloseCircleFilled, CloseOutlined, DownOutlined } from "@/components/vort/icons";
import { Check } from "lucide-vue-next";
import { getVortPopupContainer } from "@/components/vort/composables";
import { useLocale } from "@/components/vort/locale/useLocale";

defineOptions({ name: "VortSelect", inheritAttrs: false });

const { t: selT } = useLocale("Select");

const attrs = useAttrs();
const attrsStyle = computed<StyleValue | undefined>(() => attrs.style as StyleValue | undefined);

/** Vort Select - 选择器组件 */

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
const searchPlaceholder = computed(() => props.searchPlaceholder ?? selT("search_placeholder"));
const notFoundContent = computed(() => props.notFoundContent ?? selT("no_match"));

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
const shouldRenderPortal = ref(false); // 控制 Portal 是否渲染，避免产生 <!--v-if--> 注释
const searchValue = ref("");
const isHovered = ref(false);
const isFocused = ref(false);
const inputRef = ref<any>(null);
const selectorRef = ref<any>(null);
const lastOpenedAt = ref(0);
const OPEN_FOCUS_OUTSIDE_GUARD_MS = 80;
const CLOSED_SELECT_REF0CUS_GUARD_MS = 120;

/** 获取 inputRef 底层的 DOM 元素 */
const getInputEl = (): HTMLInputElement | null => {
    if (!inputRef.value) return null;
    // 如果是组件实例，通过 $el 获取 DOM 元素
    return inputRef.value.$el ?? inputRef.value;
};

const getSelectorEl = (): HTMLElement | null => {
    if (!selectorRef.value) return null;
    return selectorRef.value.$el ?? selectorRef.value;
};

const triggerRef = ref<HTMLElement | null>(null);
const setSingleSelectorRef = (el: Element | ComponentPublicInstance | null) => {
    const resolvedEl = ((el as ComponentPublicInstance | null)?.$el ?? el) as HTMLElement | null;
    selectorRef.value = resolvedEl;
    triggerRef.value = resolvedEl;
};

const getOriginalEvent = (event: Event) => {
    return ((event as CustomEvent<{ originalEvent?: Event }>).detail?.originalEvent ?? event) as Event;
};

const getEventTarget = (event: Event) => {
    return getOriginalEvent(event).target as HTMLElement | null;
};

const isRecentlyClosedSelectRefocusTarget = (target: HTMLElement | null) => {
    if (!target || !lastClosedSelectSelector) return false;
    return lastClosedSelectSelector.contains(target) && Date.now() - lastClosedSelectAnimationAt < CLOSED_SELECT_REF0CUS_GUARD_MS;
};

const hasRecentUserPointerOnTarget = (target: HTMLElement | null) => {
    if (!target || !(lastGlobalPointerDownTarget instanceof Node)) return false;
    return Date.now() - lastGlobalPointerDownAt < CLOSED_SELECT_REF0CUS_GUARD_MS && target.contains(lastGlobalPointerDownTarget);
};

// 从子组件收集的选项
const slotOptions = ref<SelectOption[]>([]);

const resetFocusState = () => {
    isFocused.value = false;

    const inputEl = getInputEl();
    if (inputEl && document.activeElement === inputEl) {
        inputEl.blur();
    }

    if (triggerRef.value && document.activeElement === triggerRef.value) {
        triggerRef.value.blur();
    }

    const blurActiveElementWithinSelect = () => {
        const selectorEl = getSelectorEl();
        const activeElement = document.activeElement;
        if (selectorEl && activeElement instanceof HTMLElement && selectorEl.contains(activeElement)) {
            activeElement.blur();
        }
    };

    blurActiveElementWithinSelect();
    setTimeout(() => {
        blurActiveElementWithinSelect();
    }, 0);
};

// 关闭当前 Select 的函数
const closeThis = () => {
    isOpen.value = false;
    if (props.autoClearSearchValue) {
        searchValue.value = "";
    }
    resetFocusState();
};

// 注册到全局管理器
selectInstances.add(closeThis);

// 组件销毁时注销
onBeforeUnmount(() => {
    selectInstances.delete(closeThis);
});

// ============ 子组件选项注册机制 ============
// 提供给子组件 VortSelectOption 的上下文
provide<SelectOptionContext>("vortSelectContext", {
    registerOption: (option: SelectOption) => {
        // 避免重复添加
        const existIndex = slotOptions.value.findIndex((o) => o.value === option.value);
        if (existIndex === -1) {
            slotOptions.value.push(option);
        } else {
            // 更新已存在的选项
            slotOptions.value[existIndex] = option;
        }
    },
    unregisterOption: (value: string | number) => {
        const index = slotOptions.value.findIndex((o) => o.value === value);
        if (index !== -1) {
            slotOptions.value.splice(index, 1);
        }
    }
});

// 合并 props.options 和 slot 收集的选项
const mergedOptions = computed(() => {
    // props.options 优先，然后是 slot 定义的选项
    if (props.options && props.options.length > 0) {
        return props.options;
    }
    return slotOptions.value;
});

// ============ 计算属性 ============

// 是否为多选模式
const isMultiple = computed(() => props.mode === "multiple" || props.mode === "tags");

// 内部值 - 统一转换为字符串，空字符串映射为哨兵
const internalValue = computed({
    get: () => {
        if (props.modelValue === undefined || props.modelValue === null) {
            return isMultiple.value ? [] : "";
        }
        if (isMultiple.value) {
            const arr = Array.isArray(props.modelValue) ? props.modelValue : [props.modelValue];
            return arr.map((v) => toInternal(String(v)));
        }
        return toInternal(String(props.modelValue));
    },
    set: (val) => {
        if (isMultiple.value) {
            const arr = Array.isArray(val) ? val : [val];
            const result = arr.map((v) => {
                const ext = fromInternal(v);
                const opt = mergedOptions.value.find((o) => String(o.value) === ext);
                return opt ? opt.value : ext;
            });
            emit("update:modelValue", result);
            const options = result.map((v) => mergedOptions.value.find((o) => o.value === v)!).filter(Boolean);
            emit("change", result, options);
        } else {
            const ext = fromInternal(String(val));
            const opt = mergedOptions.value.find((o) => String(o.value) === ext);
            const emitValue = opt?.value;
            emit("update:modelValue", emitValue);
            emit("change", emitValue, opt);
        }
    }
});

// 当前选中的选项（用于显示）
const selectedOptions = computed(() => {
    if (isMultiple.value) {
        const vals = Array.isArray(internalValue.value) ? internalValue.value : [];
        return vals.map((v) => mergedOptions.value.find((o) => toInternal(String(o.value)) === v)).filter(Boolean) as SelectOption[];
    }
    return mergedOptions.value.find((o) => toInternal(String(o.value)) === internalValue.value);
});

// 显示的标签（考虑 maxTagCount）
const displayedTags = computed(() => {
    if (!isMultiple.value) return [];
    const all = selectedOptions.value as SelectOption[];
    if (props.maxTagCount === undefined || props.maxTagCount === "responsive") {
        return all;
    }
    return all.slice(0, props.maxTagCount);
});

// 隐藏的标签数量
const hiddenTagCount = computed(() => {
    if (!isMultiple.value) return 0;
    const all = selectedOptions.value as SelectOption[];
    if (props.maxTagCount === undefined || props.maxTagCount === "responsive") {
        return 0;
    }
    return Math.max(0, all.length - props.maxTagCount);
});

// 隐藏标签的占位文本
const hiddenTagPlaceholder = computed(() => {
    if (hiddenTagCount.value <= 0) return "";
    if (typeof props.maxTagPlaceholder === "function") {
        const all = selectedOptions.value as SelectOption[];
        return props.maxTagPlaceholder(all.slice(props.maxTagCount as number));
    }
    if (props.maxTagPlaceholder) {
        return props.maxTagPlaceholder;
    }
    return `+ ${hiddenTagCount.value} ...`;
});

// 过滤后的选项
const filteredOptions = computed(() => {
    if (!searchValue.value || !props.filterOption) {
        return mergedOptions.value;
    }
    const search = searchValue.value.toLowerCase();
    const filterFn = props.filterOption;
    if (typeof filterFn === "function") {
        return mergedOptions.value.filter((opt) => filterFn(searchValue.value, opt));
    }
    return mergedOptions.value.filter((opt) => opt.label.toLowerCase().includes(search) || String(opt.value).toLowerCase().includes(search));
});

// 是否显示清除按钮
const showClearButton = computed(() => {
    if (!props.allowClear || props.disabled) return false;
    if (isMultiple.value) {
        return (internalValue.value as string[]).length > 0;
    }
    return !!internalValue.value;
});

// 悬浮时才显示清除按钮，但始终保留后缀图标占位，避免布局抖动
const isClearButtonVisible = computed(() => showClearButton.value && isHovered.value);

// 是否显示占位符
const showPlaceholder = computed(() => {
    if (isMultiple.value) {
        return (internalValue.value as string[]).length === 0 && !searchValue.value;
    }
    return !internalValue.value && !searchValue.value;
});

// 单选时显示的文本
const displayText = computed(() => {
    if (isMultiple.value) return "";
    const opt = selectedOptions.value as SelectOption | undefined;
    return opt?.label ?? "";
});

// ============ 样式类（简洁的类名切换） ============

/** 触发器类名 */
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

/** 下拉面板类名 */
const contentClasses = computed(() => {
    const classes = ["vort-select-dropdown"];
    if (props.popupClass) classes.push(props.popupClass);
    return classes;
});

/** 标签类名 */
const tagClasses = computed(() => {
    return ["vort-select-tag", `vort-select-tag-${props.size}`];
});

// ============ 事件处理 ============
const handleOpenChange = (open: boolean) => {
    if (open) {
        closeAllOtherSelects(closeThis);
        shouldRenderPortal.value = true; // 打开时先渲染 Portal
        isOpen.value = true;
        lastOpenedAt.value = Date.now();
        nextTick(() => {
            document.body.style.pointerEvents = "";
            // 自动聚焦搜索框
            if (props.showSearch) {
                getInputEl()?.focus();
            }
        });
    } else {
        isOpen.value = false;
        if (props.autoClearSearchValue) {
            searchValue.value = "";
        }
        resetFocusState();
    }
};

// 处理关闭动画完成后移除 Portal
const handleAnimationEnd = (event: AnimationEvent) => {
    if (!isOpen.value) {
        lastClosedSelectSelector = getSelectorEl();
        lastClosedSelectAnimationAt = Date.now();
        shouldRenderPortal.value = false;
    }
};

const handleSelect = (val: string) => {
    const opt = mergedOptions.value.find((o) => String(o.value) === val);
    if (opt) {
        emit("select", opt.value, opt);
    }
    // 单选模式下选中后关闭
    if (!isMultiple.value) {
        setTimeout(() => {
            isOpen.value = false;
        }, 100);
    }
    // 清空搜索
    if (props.autoClearSearchValue) {
        searchValue.value = "";
    }
};

const handleDeselect = (val: string) => {
    const opt = mergedOptions.value.find((o) => String(o.value) === val);
    if (opt) {
        emit("deselect", opt.value, opt);
    }
};

const handleClear = (e: Event) => {
    e.stopPropagation();
    if (isMultiple.value) {
        internalValue.value = [];
    } else {
        internalValue.value = "";
    }
    searchValue.value = "";
    emit("clear");
};

const handleRemoveTag = (val: string) => {
    if (props.disabled) return;
    const current = internalValue.value as string[];
    internalValue.value = current.filter((v) => v !== val);
    handleDeselect(val);
};

const handleSearchInput = (val: string) => {
    searchValue.value = val;
    emit("search", val);
};

const handleFocus = (e: FocusEvent) => {
    const target = e.target as HTMLElement | null;
    isFocused.value = !!target?.matches?.(":focus-visible");
    emit("focus", e);
};

const handleBlur = (e: FocusEvent) => {
    isFocused.value = false;
    emit("blur", e);
};

const handleTriggerClick = () => {
    if (props.disabled) return;
    // 切换打开/关闭状态
    handleOpenChange(!isOpen.value);
};

const handleFocusOutside = (event: Event) => {
    const target = getEventTarget(event);
    // 当一个 Select 关闭动画尚未结束时，点击另一个 Select 会让新的弹层
    // 在同一轮交互中收到一条误判的 focus-outside。这里只屏蔽打开后的首个短暂窗口。
    if (isOpen.value && Date.now() - lastOpenedAt.value < OPEN_FOCUS_OUTSIDE_GUARD_MS) {
        event.preventDefault();
    }

    // 上一个 Select 在关闭动画结束后会被内部逻辑重新聚焦，导致当前打开的 Select
    // 收到一条伪造的 focus-outside。这里仅拦截这种“刚完成关闭动画且没有新的用户指针操作”的回焦。
    if (isOpen.value && isRecentlyClosedSelectRefocusTarget(target) && !hasRecentUserPointerOnTarget(target)) {
        event.preventDefault();

        setTimeout(() => {
            const activeElement = document.activeElement;
            if (target && activeElement instanceof HTMLElement && target.contains(activeElement)) {
                activeElement.blur();
            }
        }, 0);
    }
};

onMounted(() => {
    const handleDocumentPointerDown = (event: PointerEvent) => {
        lastGlobalPointerDownTarget = event.target;
        lastGlobalPointerDownAt = Date.now();
    };

    document.addEventListener("pointerdown", handleDocumentPointerDown, true);
    onBeforeUnmount(() => {
        document.removeEventListener("pointerdown", handleDocumentPointerDown, true);
    });
});

// ============ 暴露方法 ============
defineExpose({
    focus: () => {
        const el = getInputEl();
        if (el) {
            el.focus();
        } else {
            triggerRef.value?.focus();
        }
    },
    blur: () => {
        getInputEl()?.blur();
        triggerRef.value?.blur();
    }
});
</script>

<template>
    <!-- 隐藏的插槽容器，用于收集 VortSelectOption 子组件 -->
    <div v-show="false">
        <slot />
    </div>

    <ComboboxRoot
        v-model="internalValue"
        v-model:open="isOpen"
        v-model:search-term="searchValue"
        :multiple="isMultiple"
        :disabled="disabled"
        :filter-function="() => filteredOptions"
        @update:open="handleOpenChange"
    >
        <ComboboxAnchor as-child>
            <!-- 多选模式 -->
            <template v-if="isMultiple">
                <TagsInputRoot
                    ref="selectorRef"
                    v-model="internalValue as string[]"
                    :disabled="disabled"
                    :class="triggerClasses"
                    :style="attrsStyle"
                    @mouseenter="isHovered = true"
                    @mouseleave="isHovered = false"
                    @click="handleTriggerClick"
                >
                    <!-- 前缀 -->
                    <span v-if="$slots.prefix" class="vort-select-prefix">
                        <slot name="prefix" />
                    </span>

                    <!-- 标签区域 -->
                    <div class="vort-select-selection">
                        <!-- 已选标签 -->
                        <TagsInputItem v-for="option in displayedTags" :key="toInternal(String(option.value))" :value="toInternal(String(option.value))" :class="tagClasses">
                            <TagsInputItemText class="vort-select-tag-text">{{ option.label }}</TagsInputItemText>
                            <TagsInputItemDelete v-if="!disabled" class="vort-select-tag-remove" @click.stop="handleRemoveTag(toInternal(String(option.value)))">
                                <CloseOutlined class="vort-select-tag-remove-icon" />
                            </TagsInputItemDelete>
                        </TagsInputItem>

                        <!-- 隐藏标签数量提示 -->
                        <span v-if="hiddenTagCount > 0" class="vort-select-tag vort-select-tag-placeholder">
                            {{ hiddenTagPlaceholder }}
                        </span>

                        <!-- 搜索输入框 -->
                        <ComboboxInput v-if="showSearch" as-child>
                            <TagsInputInput
                                ref="inputRef"
                                :placeholder="showPlaceholder ? placeholder : ''"
                                :disabled="disabled"
                                class="vort-select-search-input"
                                @focus="handleFocus"
                                @blur="handleBlur"
                                @input="(e: Event) => handleSearchInput((e.target as HTMLInputElement).value)"
                            />
                        </ComboboxInput>

                        <!-- 非搜索模式的占位符 -->
                        <span v-else-if="showPlaceholder" class="vort-select-placeholder">
                            {{ placeholder }}
                        </span>
                    </div>

                    <!-- 后缀区域 -->
                    <span class="vort-select-suffix">
                        <!-- 自定义后缀 -->
                        <slot name="suffix" />

                        <span class="vort-select-indicator">
                            <!-- 清除按钮 -->
                            <span
                                class="vort-select-clear"
                                :class="{ 'vort-select-clear-visible': isClearButtonVisible }"
                                @click="handleClear"
                                @mousedown.prevent
                            >
                                <CloseCircleFilled />
                            </span>

                            <!-- 下拉箭头 -->
                            <ComboboxTrigger
                                class="vort-select-arrow-wrapper"
                                :class="{ 'vort-select-arrow-wrapper-hidden': isClearButtonVisible }"
                                @click.stop
                            >
                                <DownOutlined :class="['vort-select-arrow', isOpen && 'vort-select-arrow-open']" />
                            </ComboboxTrigger>
                        </span>
                    </span>
                </TagsInputRoot>
            </template>

            <!-- 单选模式 -->
            <template v-else>
                <div
                    :ref="setSingleSelectorRef"
                    :class="triggerClasses"
                    :style="attrsStyle"
                    tabindex="0"
                    @mouseenter="isHovered = true"
                    @mouseleave="isHovered = false"
                    @click="handleTriggerClick"
                    @focus="handleFocus"
                    @blur="handleBlur"
                >
                    <!-- 前缀 -->
                    <span v-if="$slots.prefix" class="vort-select-prefix">
                        <slot name="prefix" />
                    </span>

                    <!-- 内容区域 -->
                    <div class="vort-select-selection">
                        <!-- 搜索输入框（仅在打开时显示） -->
                        <ComboboxInput
                            v-if="showSearch"
                            ref="inputRef"
                            :placeholder="displayText || placeholder"
                            :display-value="() => (isOpen ? searchValue : displayText)"
                            class="vort-select-search-input"
                            @input="(e: Event) => handleSearchInput((e.target as HTMLInputElement).value)"
                        />

                        <!-- 非搜索模式显示文本 -->
                        <template v-else>
                            <span v-if="selectedOptions && !isMultiple" :class="['vort-select-value', isOpen && 'vort-select-value-focused']">
                                <!-- 支持自定义渲染内容 -->
                                <component v-if="(selectedOptions as SelectOption).render" :is="(selectedOptions as SelectOption).render" />
                                <template v-else>
                                    {{ displayText }}
                                </template>
                            </span>
                            <span v-else-if="!displayText" class="vort-select-placeholder">
                                {{ placeholder }}
                            </span>
                        </template>
                    </div>

                    <!-- 后缀区域 -->
                    <span class="vort-select-suffix">
                        <!-- 自定义后缀 -->
                        <slot name="suffix" />

                        <span class="vort-select-indicator">
                            <!-- 清除按钮 -->
                            <span
                                class="vort-select-clear"
                                :class="{ 'vort-select-clear-visible': isClearButtonVisible }"
                                @click="handleClear"
                                @mousedown.prevent
                            >
                                <CloseCircleFilled />
                            </span>

                            <!-- 下拉箭头 -->
                            <ComboboxTrigger
                                class="vort-select-arrow-wrapper"
                                :class="{ 'vort-select-arrow-wrapper-hidden': isClearButtonVisible }"
                                @click.stop
                            >
                                <DownOutlined :class="['vort-select-arrow', isOpen && 'vort-select-arrow-open']" />
                            </ComboboxTrigger>
                        </span>
                    </span>
                </div>
            </template>
        </ComboboxAnchor>

        <!-- 下拉内容 -->
        <ComboboxPortal v-if="shouldRenderPortal" :to="popupContainer">
            <ComboboxContent
                :class="contentClasses"
                position="popper"
                :side-offset="4"
                :body-lock="false"
                @focus-outside="handleFocusOutside"
                @animationend="handleAnimationEnd"
            >
                <!-- 搜索框（下拉内嵌搜索，用于非 showSearch 模式下提供下拉内搜索） -->
                <div v-if="$slots.dropdownSearch" class="vort-select-dropdown-search">
                    <slot name="dropdownSearch" />
                </div>

                <ComboboxViewport class="vort-select-dropdown-viewport" :style="{ maxHeight: `${listHeight}px` }">
                    <!-- 空状态 -->
                    <ComboboxEmpty class="vort-select-empty">
                        {{ notFoundContent }}
                    </ComboboxEmpty>

                    <!-- 选项列表 -->
                    <ComboboxItem
                        v-for="option in filteredOptions"
                        :key="toInternal(String(option.value))"
                        :value="toInternal(String(option.value))"
                        :disabled="option.disabled"
                        class="vort-select-option"
                        @select="handleSelect(String(option.value))"
                    >
                        <!-- 选项内容：支持自定义渲染 -->
                        <span class="vort-select-option-content">
                            <component v-if="option.render" :is="option.render" />
                            <template v-else>
                                {{ option.label }}
                            </template>
                        </span>

                        <!-- 勾选图标（仅多选/标签模式显示） -->
                        <ComboboxItemIndicator v-if="isMultiple" class="vort-select-option-check">
                            <Check class="vort-select-check-icon" />
                        </ComboboxItemIndicator>
                    </ComboboxItem>
                </ComboboxViewport>

                <!-- 底部插槽（用于添加按钮等） -->
                <div v-if="$slots.dropdownRender" class="vort-select-dropdown-footer">
                    <slot name="dropdownRender" />
                </div>
            </ComboboxContent>
        </ComboboxPortal>
    </ComboboxRoot>
</template>

<style scoped>
/* ========================================
   CSS Variables（局部变量，可被状态类覆盖）
   使用 --_ 前缀表示私有变量
   ======================================== */

/* ========================================
   基础样式 - 选择器触发器
   ======================================== */
.vort-select-selector {
    /* 局部变量 - 可被状态类覆盖 */
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

/* ========================================
   交互状态 - Hover
   ======================================== */
.vort-select-selector:hover:not(.vort-select-disabled) {
    border-color: var(--_focus-color);
}

/* ========================================
   交互状态 - Focus / Open
   ======================================== */
.vort-select-focused:not(.vort-select-disabled) {
    border-color: var(--_focus-color);
    box-shadow: 0 0 0 2px var(--_focus-shadow);
}

/* ========================================
   状态覆盖 - Error
   ======================================== */
.vort-select-error {
    --_border-color: var(--vort-error, #ff4d4f);
    --_focus-color: var(--vort-error, #ff4d4f);
    --_focus-shadow: rgba(255, 77, 79, 0.06);
}

/* ========================================
   状态覆盖 - Warning
   ======================================== */
.vort-select-warning {
    --_border-color: var(--vort-warning, #faad14);
    --_focus-color: var(--vort-warning, #faad14);
    --_focus-shadow: rgba(250, 173, 20, 0.1);
}

/* ========================================
   状态覆盖 - Disabled
   ======================================== */
.vort-select-disabled {
    --_bg-color: rgba(0, 0, 0, 0.04);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: not-allowed;
}

/* ========================================
   状态覆盖 - Borderless
   ======================================== */
.vort-select-borderless {
    border-color: transparent;
    background: transparent;
}

.vort-select-borderless:hover:not(.vort-select-disabled) {
    border-color: transparent;
    background: rgba(0, 0, 0, 0.04);
}

.vort-select-borderless.vort-select-focused {
    border-color: transparent;
    background: transparent;
    box-shadow: none;
}

/* ========================================
   尺寸 - Large
   ======================================== */
.vort-select-large {
    height: var(--vort-height-lg, 40px);
    padding: 0 11px;
    font-size: var(--vort-font-size-md, 16px);
}

.vort-select-large.vort-select-multiple {
    min-height: var(--vort-height-lg, 40px);
    height: auto;
}

/* ========================================
   尺寸 - Middle（默认）
   ======================================== */
.vort-select-middle {
    height: var(--vort-height-md, 32px);
    padding: 0 11px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-select-middle.vort-select-multiple {
    min-height: var(--vort-height-md, 32px);
    height: auto;
}

/* ========================================
   尺寸 - Small
   ======================================== */
.vort-select-small {
    height: var(--vort-height-sm, 24px);
    padding: 0 7px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-select-small.vort-select-multiple {
    min-height: var(--vort-height-sm, 24px);
    height: auto;
}

/* ========================================
   内部元素 - 前缀
   ======================================== */
.vort-select-prefix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-right: 4px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   内部元素 - 选择区域
   ======================================== */
.vort-select-selection {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    flex: 1;
    min-width: 0;
    gap: 4px;
    padding: 3px 0;
}

/* ========================================
   内部元素 - 后缀
   ======================================== */
.vort-select-suffix {
    display: flex;
    align-items: center;
    flex-shrink: 0;
    margin-left: 4px;
    gap: 4px;
}

.vort-select-indicator {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    flex-shrink: 0;
}

/* ========================================
   内部元素 - 清除按钮
   ======================================== */
.vort-select-clear {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    cursor: pointer;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition:
        color var(--vort-transition-colors, 0.1s),
        opacity var(--vort-transition-colors, 0.1s);
}

.vort-select-clear-visible {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
}

.vort-select-clear:hover {
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

/* ========================================
   内部元素 - 下拉箭头
   ======================================== */
.vort-select-arrow-wrapper {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    margin: 0;
    border: none;
    outline: none;
    box-shadow: none;
    background: transparent !important;
    background-color: transparent !important;
    appearance: none;
    -webkit-appearance: none;
    line-height: 1;
    transition: opacity var(--vort-transition-colors, 0.1s);
}

.vort-select-arrow-wrapper-hidden {
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
}

.vort-select-arrow-wrapper:hover,
.vort-select-arrow-wrapper:active,
.vort-select-arrow-wrapper:focus,
.vort-select-arrow-wrapper:focus-visible {
    background: transparent !important;
    background-color: transparent !important;
    border: none;
    outline: none;
    box-shadow: none;
}

.vort-select-arrow {
    font-size: 12px;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: transform var(--vort-transition-colors, 0.2s);
}

.vort-select-arrow-open {
    transform: rotate(180deg);
}

/* ========================================
   内部元素 - 占位符
   ======================================== */
.vort-select-placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   内部元素 - 选中值
   ======================================== */
.vort-select-value {
    display: flex;
    align-items: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    transition: color var(--vort-transition-colors, 0.2s);
}

.vort-select-value-focused {
    color: rgba(0, 0, 0, 0.25);
}

/* ========================================
   内部元素 - 搜索输入框
   ======================================== */
.vort-select-search-input {
    flex: 1;
    min-width: 60px;
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-select-search-input::placeholder {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   多选标签 - 基础样式
   ======================================== */
.vort-select-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    max-width: 100%;
    padding: 0 4px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: var(--vort-radius-sm, 4px);
}

.vort-select-tag-placeholder {
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
}

/* ========================================
   多选标签 - 尺寸
   ======================================== */
.vort-select-tag-large {
    height: 24px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-select-tag-middle {
    height: 22px;
    font-size: var(--vort-font-size-sm, 14px);
}

.vort-select-tag-small {
    height: 16px;
    font-size: var(--vort-font-size-xs, 12px);
}

/* ========================================
   多选标签 - 内部元素
   ======================================== */
.vort-select-tag-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.vort-select-tag-remove {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    border-radius: var(--vort-radius-sm, 4px);
    cursor: pointer;
    transition: background-color var(--vort-transition-colors, 0.1s);
}

.vort-select-tag-remove:hover {
    background: rgba(0, 0, 0, 0.1);
}

.vort-select-tag-remove-icon {
    font-size: 10px;
    color: var(--vort-text-tertiary, rgba(0, 0, 0, 0.45));
}

/* ========================================
   下拉面板 - 基础样式
   ======================================== */
.vort-select-dropdown-search {
    padding: 8px;
    border-bottom: 1px solid var(--vort-border, #d9d9d9);
}

.vort-select-dropdown-viewport {
    padding: 4px;
    overflow-y: auto;
}

.vort-select-dropdown-footer {
    border-top: 1px solid var(--vort-border, #d9d9d9);
}

/* ========================================
   下拉面板 - 空状态
   ======================================== */
.vort-select-empty {
    padding: 24px 12px;
    text-align: center;
    font-size: var(--vort-font-size-sm, 14px);
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

/* ========================================
   下拉面板 - 选项
   ======================================== */
.vort-select-option {
    position: relative;
    display: flex;
    align-items: center;
    width: 100%;
    padding: 5px 12px;
    font-size: var(--vort-font-size-sm, 14px);
    line-height: 22px;
    cursor: pointer;
    user-select: none;
    outline: none;
    border-radius: var(--vort-radius-sm, 4px);
    transition: background-color var(--vort-transition-colors, 0.15s);
}

.vort-select-option:hover {
    background: rgba(0, 0, 0, 0.04);
}

.vort-select-option[data-highlighted] {
    background: rgba(0, 0, 0, 0.04);
}

.vort-select-option[data-state="checked"] {
    background: var(--vort-primary-bg, #e8f0fe);
    font-weight: 500;
}

.vort-select-option[data-disabled] {
    opacity: 0.5;
    pointer-events: none;
}

.vort-select-option-content {
    flex: 1;
    /* 移除文本省略，让内容完整显示 */
    white-space: nowrap;
}

.vort-select-option-check {
    margin-left: 8px;
}

.vort-select-check-icon {
    width: 16px;
    height: 16px;
    color: var(--vort-primary, #1456f0);
}
</style>
