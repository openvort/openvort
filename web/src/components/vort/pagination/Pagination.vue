<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { Select, type SelectOptionType } from "@/components/vort/select";
import { Input } from "@/components/vort/input";
import { LeftOutlined, RightOutlined, DoubleLeftOutlined, DoubleRightOutlined, MoreOutlined } from "./icons";
import { useLocale } from "../locale";

defineOptions({ name: "VortPagination" });

/** Vort Pagination - 分页组件 */

type PaginationSize = "default" | "small";

interface Props {
    /** 当前页数 (v-model:current) */
    current?: number;
    /** 每页条数 (v-model:pageSize) */
    pageSize?: number;
    /** 数据总数 */
    total?: number;
    /** 是否禁用 */
    disabled?: boolean;
    /** 只有一页时是否隐藏分页器 */
    hideOnSinglePage?: boolean;
    /** 用于显示数据总量和当前数据顺序（函数形式，自定义格式） */
    showTotal?: (total: number, range: [number, number]) => string;
    /** 是否显示总数信息，格式：第1-15 条 / 总共 3989 条 */
    showTotalInfo?: boolean;
    /** 是否显示 pageSize 切换器 */
    showSizeChanger?: boolean;
    /** 指定每页可以显示多少条 */
    pageSizeOptions?: number[];
    /** 是否显示快速跳转 */
    showQuickJumper?: boolean;
    /** 当前页面展示的最大页码按钮数 */
    showLessItems?: boolean;
    /** 简洁版本 */
    simple?: boolean;
    /** 尺寸 */
    size?: PaginationSize;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    current: 1,
    pageSize: 10,
    total: 0,
    disabled: false,
    hideOnSinglePage: false,
    showTotal: undefined,
    showTotalInfo: false,
    showSizeChanger: false,
    pageSizeOptions: () => [10, 20, 50, 100],
    showQuickJumper: false,
    showLessItems: false,
    simple: false,
    size: "default"
});

const emit = defineEmits<{
    "update:current": [page: number];
    "update:pageSize": [size: number];
    change: [page: number, pageSize: number];
    showSizeChange: [current: number, size: number];
}>();

// 国际化
const { t } = useLocale("Pagination");

// 内部状态
const internalCurrent = ref(props.current);
const internalPageSize = ref(props.pageSize);
const jumpValue = ref("");

// 同步外部值
watch(
    () => props.current,
    (val) => {
        internalCurrent.value = val;
    }
);

watch(
    () => props.pageSize,
    (val) => {
        internalPageSize.value = val;
    }
);

// 总页数
const totalPages = computed(() => {
    return Math.max(1, Math.ceil(props.total / internalPageSize.value));
});

// 是否隐藏分页
const shouldHide = computed(() => {
    return props.hideOnSinglePage && totalPages.value <= 1;
});

// 当前数据范围
const dataRange = computed((): [number, number] => {
    const start = (internalCurrent.value - 1) * internalPageSize.value + 1;
    const end = Math.min(internalCurrent.value * internalPageSize.value, props.total);
    return [start, end];
});

// 总数显示文本
const totalText = computed(() => {
    if (props.showTotal) {
        return props.showTotal(props.total, dataRange.value);
    }
    if (props.showTotalInfo) {
        const [start, end] = dataRange.value;
        return t("total", { start, end, total: props.total });
    }
    return "";
});

// 页码列表
const pageList = computed(() => {
    const total = totalPages.value;
    const current = internalCurrent.value;
    const maxShow = props.showLessItems ? 5 : 7;

    if (total <= maxShow) {
        return Array.from({ length: total }, (_, i) => i + 1);
    }

    const pages: (number | "prev" | "next")[] = [];
    const sideCount = props.showLessItems ? 1 : 2;

    // 始终显示第一页
    pages.push(1);

    // 计算中间页码的范围
    let start = Math.max(2, current - sideCount);
    let end = Math.min(total - 1, current + sideCount);

    // 调整范围确保显示足够的页码
    if (current - sideCount <= 2) {
        end = Math.min(total - 1, maxShow - 2);
    }
    if (current + sideCount >= total - 1) {
        start = Math.max(2, total - maxShow + 3);
    }

    // 前省略号
    if (start > 2) {
        pages.push("prev");
    }

    // 中间页码
    for (let i = start; i <= end; i++) {
        pages.push(i);
    }

    // 后省略号
    if (end < total - 1) {
        pages.push("next");
    }

    // 始终显示最后一页
    if (total > 1) {
        pages.push(total);
    }

    return pages;
});

// pageSize 选项
const sizeOptions = computed((): SelectOptionType[] => {
    return props.pageSizeOptions.map((size) => ({
        value: size,
        label: `${size} ${t("items_per_page")}`
    }));
});

// 方法
const changePage = (page: number) => {
    if (props.disabled) return;
    if (page < 1 || page > totalPages.value) return;
    if (page === internalCurrent.value) return;

    internalCurrent.value = page;
    emit("update:current", page);
    emit("change", page, internalPageSize.value);
};

const changePageSize = (size: string | number | (string | number)[] | undefined) => {
    if (typeof size !== "number") return;
    if (props.disabled) return;

    internalPageSize.value = size;
    // 调整当前页，确保不超出范围
    const maxPage = Math.max(1, Math.ceil(props.total / size));
    if (internalCurrent.value > maxPage) {
        internalCurrent.value = maxPage;
        emit("update:current", maxPage);
    }

    emit("update:pageSize", size);
    emit("showSizeChange", internalCurrent.value, size);
    emit("change", internalCurrent.value, size);
};

const handleJump = () => {
    const page = parseInt(jumpValue.value, 10);
    if (!isNaN(page)) {
        const targetPage = Math.max(1, Math.min(page, totalPages.value));
        changePage(targetPage);
    }
    jumpValue.value = "";
};

const handleJumpKeydown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
        handleJump();
    }
};

const jumpPrev = () => {
    const target = Math.max(1, internalCurrent.value - (props.showLessItems ? 3 : 5));
    changePage(target);
};

const jumpNext = () => {
    const target = Math.min(totalPages.value, internalCurrent.value + (props.showLessItems ? 3 : 5));
    changePage(target);
};

// ========== 类名计算 ==========

const containerClasses = computed(() => {
    const classes = ["vort-pagination"];
    if (props.size === "small") classes.push("vort-pagination-small");
    if (props.disabled) classes.push("vort-pagination-disabled");
    if (props.class) classes.push(props.class);
    return classes;
});

const getPageItemClasses = (page: number) => {
    const classes = ["vort-pagination-item"];
    if (page === internalCurrent.value) classes.push("vort-pagination-item-active");
    return classes;
};

const getNavItemClasses = (isDisabled: boolean) => {
    const classes = ["vort-pagination-item", "vort-pagination-nav"];
    if (isDisabled || props.disabled) classes.push("vort-pagination-item-disabled");
    return classes;
};
</script>

<template>
    <nav v-if="!shouldHide" :class="containerClasses" role="navigation" aria-label="分页">
        <!-- 总数显示 -->
        <span v-if="totalText" class="vort-pagination-total">
            {{ totalText }}
        </span>

        <!-- 简洁模式 -->
        <template v-if="simple">
            <!-- 上一页 -->
            <button
                :class="getNavItemClasses(internalCurrent <= 1)"
                :disabled="internalCurrent <= 1 || disabled"
                :aria-label="t('prev_page')"
                @click="changePage(internalCurrent - 1)"
            >
                <LeftOutlined />
            </button>

            <!-- 页码输入 -->
            <div class="vort-pagination-simple-pager">
                <input
                    :value="internalCurrent"
                    class="vort-pagination-simple-input"
                    type="text"
                    :disabled="disabled"
                    @change="(e) => changePage(parseInt((e.target as HTMLInputElement).value, 10))"
                    @keydown.enter="(e) => changePage(parseInt((e.target as HTMLInputElement).value, 10))"
                />
                <span class="vort-pagination-simple-separator">/</span>
                <span class="vort-pagination-simple-total">{{ totalPages }}</span>
            </div>

            <!-- 下一页 -->
            <button
                :class="getNavItemClasses(internalCurrent >= totalPages)"
                :disabled="internalCurrent >= totalPages || disabled"
                :aria-label="t('next_page')"
                @click="changePage(internalCurrent + 1)"
            >
                <RightOutlined />
            </button>
        </template>

        <!-- 标准模式 -->
        <template v-else>
            <!-- 上一页 -->
            <button
                :class="getNavItemClasses(internalCurrent <= 1)"
                :disabled="internalCurrent <= 1 || disabled"
                :aria-label="t('prev_page')"
                @click="changePage(internalCurrent - 1)"
            >
                <LeftOutlined />
            </button>

            <!-- 页码列表 -->
            <template v-for="page in pageList" :key="page">
                <!-- 前跳省略号 -->
                <button
                    v-if="page === 'prev'"
                    class="vort-pagination-jump vort-pagination-jump-prev"
                    :title="t('prev_n', { count: showLessItems ? 3 : 5 })"
                    :disabled="disabled"
                    @click="jumpPrev"
                >
                    <MoreOutlined class="vort-pagination-ellipsis" />
                    <DoubleLeftOutlined class="vort-pagination-jump-icon" />
                </button>

                <!-- 后跳省略号 -->
                <button
                    v-else-if="page === 'next'"
                    class="vort-pagination-jump vort-pagination-jump-next"
                    :title="t('next_n', { count: showLessItems ? 3 : 5 })"
                    :disabled="disabled"
                    @click="jumpNext"
                >
                    <MoreOutlined class="vort-pagination-ellipsis" />
                    <DoubleRightOutlined class="vort-pagination-jump-icon" />
                </button>

                <!-- 页码 -->
                <button
                    v-else
                    :class="getPageItemClasses(page as number)"
                    :aria-current="page === internalCurrent ? 'page' : undefined"
                    :disabled="disabled"
                    @click="changePage(page as number)"
                >
                    {{ page }}
                </button>
            </template>

            <!-- 下一页 -->
            <button
                :class="getNavItemClasses(internalCurrent >= totalPages)"
                :disabled="internalCurrent >= totalPages || disabled"
                :aria-label="t('next_page')"
                @click="changePage(internalCurrent + 1)"
            >
                <RightOutlined />
            </button>

            <!-- 每页条数选择器 -->
            <Select
                v-if="showSizeChanger"
                :model-value="internalPageSize"
                :options="sizeOptions"
                :size="size === 'small' ? 'small' : 'middle'"
                :disabled="disabled"
                class="vort-pagination-options-size-changer"
                @update:model-value="changePageSize"
            />

            <!-- 快速跳转 -->
            <div v-if="showQuickJumper" class="vort-pagination-options-quick-jumper">
                <span>{{ t("jump_to") }}</span>
                <Input
                    v-model="jumpValue"
                    :size="size === 'small' ? 'small' : 'middle'"
                    :disabled="disabled"
                    class="vort-pagination-options-quick-jumper-input"
                    @keydown="handleJumpKeydown"
                    @blur="handleJump"
                />
                <span>{{ t("page") }}</span>
            </div>
        </template>
    </nav>
</template>

<style scoped>
/* ========================================
   容器
   ======================================== */
.vort-pagination {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    font-size: var(--vort-font-size-sm, 14px);
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-pagination-small {
    font-size: var(--vort-font-size-xs, 12px);
    gap: 8px;
}

.vort-pagination-disabled {
    cursor: not-allowed;
}

/* ========================================
   总数显示
   ======================================== */
.vort-pagination-total {
    margin-right: 8px;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

/* ========================================
   页码按钮
   ======================================== */
.vort-pagination-item {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    padding: 0 10px;
    font-weight: 400;
    background: #fff;
    border: 1px solid var(--vort-border, #d9d9d9);
    border-radius: var(--vort-radius, 6px);
    cursor: pointer;
    user-select: none;
    outline: none;
    transition: all var(--vort-duration-normal, 200ms);
}

.vort-pagination-small .vort-pagination-item {
    min-width: 22px;
    height: 22px;
    padding: 0 6px;
    font-size: var(--vort-font-size-xs, 12px);
    line-height: 20px;
    border-radius: var(--vort-radius-sm, 4px);
}

.vort-pagination-item:hover:not(:disabled):not(.vort-pagination-item-disabled) {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
}

.vort-pagination-item-active {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
}

.vort-pagination-item-disabled,
.vort-pagination-item:disabled {
    cursor: not-allowed;
    opacity: 0.6;
}

/* ========================================
   导航按钮（上一页/下一页）
   ======================================== */
.vort-pagination-nav {
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
}

.vort-pagination-nav:hover:not(:disabled):not(.vort-pagination-item-disabled) {
    color: var(--vort-primary, #1456f0);
}

/* ========================================
   省略号 & 快速跳转
   ======================================== */
.vort-pagination-jump {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    padding: 0;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--vort-radius, 6px);
    cursor: pointer;
    user-select: none;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    transition: all var(--vort-duration-normal, 200ms);
}

.vort-pagination-small .vort-pagination-jump {
    min-width: 22px;
    height: 22px;
}

.vort-pagination-jump:hover:not(:disabled) {
    color: var(--vort-primary, #1456f0);
}

.vort-pagination-jump:disabled {
    cursor: not-allowed;
}

.vort-pagination-ellipsis {
    display: block;
}

.vort-pagination-jump-icon {
    display: none;
    color: var(--vort-primary, #1456f0);
}

.vort-pagination-jump:hover:not(:disabled) .vort-pagination-ellipsis {
    display: none;
}

.vort-pagination-jump:hover:not(:disabled) .vort-pagination-jump-icon {
    display: block;
}

/* ========================================
   简洁模式
   ======================================== */
.vort-pagination-simple-pager {
    display: flex;
    align-items: center;
    gap: 6px;
}

.vort-pagination-simple-input {
    width: 48px;
    height: 32px;
    padding: 0;
    text-align: center;
    background: #fff;
    border: 1px solid var(--vort-border, #d9d9d9);
    border-radius: var(--vort-radius, 6px);
    outline: none;
    transition: border-color var(--vort-duration-fast, 100ms);
}

.vort-pagination-small .vort-pagination-simple-input {
    width: 40px;
    height: 22px;
    font-size: var(--vort-font-size-xs, 12px);
    border-radius: var(--vort-radius-sm, 4px);
}

.vort-pagination-simple-input:focus {
    border-color: var(--vort-primary, #1456f0);
}

.vort-pagination-simple-input:disabled {
    cursor: not-allowed;
    opacity: 0.6;
}

.vort-pagination-simple-separator {
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
}

.vort-pagination-simple-total {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

/* ========================================
   每页条数选择器
   ======================================== */
.vort-pagination-options-size-changer {
    margin-left: 8px;
    width: 100px;
}

.vort-pagination-small .vort-pagination-options-size-changer {
    width: 90px;
}

/* ========================================
   快速跳转
   ======================================== */
.vort-pagination-options-quick-jumper {
    display: flex;
    align-items: center;
    flex-wrap: nowrap;
    flex-shrink: 0;
    gap: 8px;
    margin-left: 8px;
    white-space: nowrap;
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
}

.vort-pagination-small .vort-pagination-options-quick-jumper {
    gap: 6px;
}

:deep(.vort-pagination-options-quick-jumper-input.vort-input-wrapper),
:deep(.vort-pagination-options-quick-jumper-input.vort-input) {
    width: 48px;
    flex-shrink: 0;
}

.vort-pagination-small :deep(.vort-pagination-options-quick-jumper-input.vort-input-wrapper),
.vort-pagination-small :deep(.vort-pagination-options-quick-jumper-input.vort-input) {
    width: 40px;
}
</style>
