<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from "vue";
import { Checkbox, Select, SelectOption, DatePicker, RangePicker, Button, Divider } from "@openvort/vort-ui";
import { Filter } from "lucide-vue-next";
import StatusIcon from "@/components/vort-biz/work-item/StatusIcon.vue";

export type FilterType = "enum" | "date" | "text";
export type FilterOperator = "contains" | "gt" | "lt" | "between" | "eq" | "gte" | "lte";

export interface ColumnFilterOption {
    label: string;
    value: string;
    icon?: string;
    iconClass?: string;
    dotColor?: string;
    avatarUrl?: string;
    avatarLabel?: string;
    avatarBg?: string;
}

export interface ColumnFilterConfig {
    type: FilterType;
    options?: ColumnFilterOption[];
    sortLabels?: [string, string];
}

export interface ColumnFilterValue {
    operator: FilterOperator;
    value: any;
}

interface Props {
    field: string;
    title: string;
    config: ColumnFilterConfig;
    sortOrder?: "ascend" | "descend" | null;
    filterValue?: ColumnFilterValue | null;
}

const props = defineProps<Props>();

const emit = defineEmits<{
    sort: [order: "ascend" | "descend" | null];
    filter: [value: ColumnFilterValue | null];
}>();

const open = ref(false);
const triggerRef = ref<HTMLElement>();
const panelRef = ref<HTMLElement>();
const panelStyle = ref<Record<string, string>>({});

const operator = ref<FilterOperator>(props.config.type === "enum" ? "contains" : "gt");
const selectedValues = ref<string[]>([]);
const dateValue = ref<string>("");
const dateRange = ref<[string, string]>(["", ""]);

const formatDateStr = (d: Date | null): string => {
    if (!d || isNaN(d.getTime())) return "";
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const dateRangeModel = computed({
    get(): [Date | null, Date | null] | null {
        const [s, e] = dateRange.value;
        const sd = s ? new Date(s) : null;
        const ed = e ? new Date(e) : null;
        return (sd || ed) ? [sd, ed] : null;
    },
    set(val: [Date | null, Date | null] | null) {
        if (!val) { dateRange.value = ["", ""]; return; }
        dateRange.value = [formatDateStr(val[0]), formatDateStr(val[1])];
    },
});

const operatorOptions = computed(() => {
    if (props.config.type === "enum") {
        return [{ label: "包含", value: "contains" }];
    }
    return [
        { label: "大于", value: "gt" },
        { label: "小于", value: "lt" },
        { label: "介于", value: "between" },
        { label: "等于", value: "eq" },
        { label: "大于等于", value: "gte" },
        { label: "小于等于", value: "lte" },
    ];
});

const sortLabels = computed(() => {
    if (props.config.sortLabels) return props.config.sortLabels;
    if (props.config.type === "date") return ["旧 → 新", "新 → 旧"];
    if (props.config.type === "enum" && props.config.options?.length) {
        const first = props.config.options[0]?.label || "";
        const last = props.config.options[props.config.options.length - 1]?.label || "";
        return [`${last} → ${first}`, `${first} → ${last}`];
    }
    return ["升序", "降序"];
});

const hasActiveFilter = computed(() => {
    if (!props.filterValue) return false;
    if (props.config.type === "enum") return props.filterValue.value?.length > 0;
    if (operator.value === "between") return dateRange.value[0] || dateRange.value[1];
    return !!dateValue.value;
});

const activeCount = computed(() => {
    let count = 0;
    if (props.sortOrder) count++;
    if (hasActiveFilter.value) count++;
    return count;
});

watch(() => props.filterValue, (val) => {
    if (val) {
        operator.value = val.operator;
        if (props.config.type === "enum") {
            selectedValues.value = Array.isArray(val.value) ? [...val.value] : [];
        } else if (val.operator === "between") {
            dateRange.value = Array.isArray(val.value) ? [...val.value] as [string, string] : ["", ""];
        } else {
            dateValue.value = val.value || "";
        }
    } else {
        selectedValues.value = [];
        dateValue.value = "";
        dateRange.value = ["", ""];
    }
}, { immediate: true });

const updatePosition = () => {
    if (!triggerRef.value) return;
    const th = triggerRef.value.closest("th");
    const rect = (th || triggerRef.value).getBoundingClientRect();
    const panelWidth = 280;
    let left = rect.left;
    if (left + panelWidth > window.innerWidth - 8) {
        left = window.innerWidth - panelWidth - 8;
    }
    panelStyle.value = {
        position: "fixed",
        top: `${rect.bottom - 3}px`,
        left: `${Math.max(8, left - 3)}px`,
        zIndex: "1050",
    };
};

const toggleOpen = () => {
    if (open.value) {
        open.value = false;
    } else {
        open.value = true;
        nextTick(updatePosition);
    }
};

const isInsideChildPopup = (target: Node): boolean => {
    const el = target as HTMLElement;
    if (!el.closest) return false;
    return !!el.closest(
        "[data-radix-popper-content-wrapper], [data-reka-popper-content-wrapper], .vort-datepicker-panel, .vort-range-picker-panel"
    );
};

const handleMouseDown = (e: MouseEvent) => {
    if (!open.value) return;
    const target = e.target as Node;
    if (triggerRef.value?.contains(target)) return;
    if (panelRef.value?.contains(target)) return;
    if (isInsideChildPopup(target)) return;
    open.value = false;
};

const handleScroll = () => {
    if (open.value) updatePosition();
};

onMounted(() => {
    document.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("scroll", handleScroll, true);
    window.addEventListener("resize", handleScroll);
});

onBeforeUnmount(() => {
    document.removeEventListener("mousedown", handleMouseDown);
    window.removeEventListener("scroll", handleScroll, true);
    window.removeEventListener("resize", handleScroll);
});

const handleSort = (order: "ascend" | "descend") => {
    emit("sort", props.sortOrder === order ? null : order);
};

const toggleEnumValue = (val: string) => {
    const idx = selectedValues.value.indexOf(val);
    if (idx >= 0) selectedValues.value.splice(idx, 1);
    else selectedValues.value.push(val);
};

const handleConfirm = () => {
    if (props.config.type === "enum") {
        emit("filter", selectedValues.value.length > 0 ? { operator: "contains", value: [...selectedValues.value] } : null);
    } else {
        if (operator.value === "between") {
            emit("filter", dateRange.value[0] || dateRange.value[1]
                ? { operator: "between", value: [...dateRange.value] }
                : null);
        } else {
            emit("filter", dateValue.value ? { operator: operator.value, value: dateValue.value } : null);
        }
    }
    open.value = false;
};

const handleClear = () => {
    selectedValues.value = [];
    dateValue.value = "";
    dateRange.value = ["", ""];
    if (props.sortOrder) emit("sort", null);
    emit("filter", null);
    open.value = false;
};
</script>

<template>
    <div
        ref="triggerRef"
        class="column-filter-cell"
        :class="{ 'has-active': activeCount > 0 }"
        @click.stop="toggleOpen"
    >
        <span class="column-filter-cell-label"><slot /></span>
        <Filter :size="12" class="column-filter-cell-icon" />
        <span v-if="activeCount > 0" class="filter-badge">{{ activeCount }}</span>
    </div>

    <Teleport to="body">
        <Transition name="filter-fade">
            <div v-if="open" ref="panelRef" class="column-filter-panel" :style="panelStyle" @click.stop>
                <div class="filter-section">
                    <div class="filter-section-title">排序</div>
                    <div
                        class="sort-option"
                        :class="{ active: sortOrder === 'ascend' }"
                        @click="handleSort('ascend')"
                    >{{ sortLabels[0] }}</div>
                    <div
                        class="sort-option"
                        :class="{ active: sortOrder === 'descend' }"
                        @click="handleSort('descend')"
                    >{{ sortLabels[1] }}</div>
                </div>

                <Divider style="margin: 8px 0" />

                <div class="filter-section">
                    <div class="filter-section-title">筛选</div>

                    <Select v-model="operator" size="small" class="w-full mb-2">
                        <SelectOption v-for="op in operatorOptions" :key="op.value" :value="op.value">
                            {{ op.label }}
                        </SelectOption>
                    </Select>

                    <template v-if="config.type === 'enum'">
                        <div class="enum-options">
                            <div
                                v-for="opt in config.options"
                                :key="opt.value"
                                class="enum-option"
                                @click="toggleEnumValue(opt.value)"
                            >
                                <Checkbox :checked="selectedValues.includes(opt.value)" class="enum-checkbox" />
                                <span v-if="opt.dotColor" class="enum-dot" :style="{ background: opt.dotColor }" />
                                <span
                                    v-else-if="opt.avatarUrl || opt.avatarLabel"
                                    class="enum-avatar"
                                    :style="{ background: opt.avatarBg || '#94a3b8' }"
                                >
                                    {{ opt.avatarLabel }}
                                    <img v-if="opt.avatarUrl" :src="opt.avatarUrl" class="enum-avatar-img absolute inset-0" @error="$event.target.style.display = 'none'" />
                                </span>
                                <span v-else-if="opt.icon" class="enum-icon" :class="opt.iconClass"><StatusIcon :name="opt.icon" :size="14" /></span>
                                <span class="enum-label">{{ opt.label }}</span>
                            </div>
                        </div>
                    </template>

                    <template v-else-if="config.type === 'date'">
                        <RangePicker
                            v-if="operator === 'between'"
                            v-model="dateRangeModel"
                            size="small"
                            class="w-full"
                            :placeholder="['开始日期', '结束日期']"
                        />
                        <DatePicker
                            v-else
                            v-model="dateValue"
                            size="small"
                            class="w-full"
                            placeholder="请选择日期"
                            value-format="YYYY-MM-DD"
                        />
                    </template>
                </div>

                <div class="filter-actions">
                    <Button size="small" @click="handleClear">清除筛选条件</Button>
                    <Button size="small" type="primary" @click="handleConfirm">确认</Button>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
.column-filter-cell {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    cursor: pointer;
    position: static;
    user-select: none;
}
/* Expand hover + click area to cover entire th */
.column-filter-cell::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 1;
}
.column-filter-cell::after {
    content: "";
    position: absolute;
    inset: 0;
    border: 1px solid transparent;
    pointer-events: none;
    transition: border-color 0.2s ease;
    z-index: 1;
}
.column-filter-cell:hover::after {
    border-color: #d9d9d9;
}
.column-filter-cell.has-active::after {
    border-color: var(--vort-primary, #1456f0);
}
.column-filter-cell-label {
    position: relative;
    z-index: 2;
}
.column-filter-cell-icon {
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    color: #bbb;
    opacity: 0;
    transition: opacity 0.15s, color 0.15s;
    z-index: 2;
}
.column-filter-cell:hover .column-filter-cell-icon,
.column-filter-cell.has-active .column-filter-cell-icon {
    opacity: 1;
}
.column-filter-cell.has-active .column-filter-cell-icon {
    color: var(--vort-primary, #1456f0);
}
.filter-badge {
    position: absolute;
    top: 4px;
    right: 4px;
    min-width: 14px;
    height: 14px;
    border-radius: 7px;
    background: var(--vort-primary, #1456f0);
    color: #fff;
    font-size: 10px;
    line-height: 14px;
    text-align: center;
    padding: 0 3px;
    z-index: 2;
}
.column-filter-panel {
    width: 280px;
    padding: 12px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 6px 16px 0 rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12), 0 9px 28px 8px rgba(0, 0, 0, 0.05);
    border: 1px solid #f0f0f0;
}
.filter-section-title {
    font-size: 12px;
    color: #999;
    margin-bottom: 8px;
}
.sort-option {
    padding: 6px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
    color: #333;
    transition: background 0.15s;
}
.sort-option:hover {
    background: rgba(0, 0, 0, 0.04);
}
.sort-option.active {
    color: var(--vort-primary, #1456f0);
    background: var(--vort-primary-bg, rgba(20, 86, 240, 0.06));
}
.enum-options {
    max-height: 240px;
    overflow-y: auto;
}
.enum-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 0px 4px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 13px;
}
.enum-option:hover {
    background: rgba(0, 0, 0, 0.04);
}
.enum-checkbox {
    pointer-events: none;
}
.enum-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.enum-avatar {
    width: 20px;
    height: 20px;
    border-radius: 9999px;
    flex-shrink: 0;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    color: #fff;
    font-size: 11px;
    font-weight: 500;
}
.enum-avatar-img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}
.enum-label {
    flex: 1;
    min-width: 0;
}
.filter-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid #f0f0f0;
}

.filter-fade-enter-active {
    transition: opacity 0.15s ease, transform 0.15s ease;
}
.filter-fade-leave-active {
    transition: opacity 0.1s ease, transform 0.1s ease;
}
.filter-fade-enter-from {
    opacity: 0;
    transform: translateY(-4px);
}
.filter-fade-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}
</style>
