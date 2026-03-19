<script setup lang="ts">
import { computed, type CSSProperties, useSlots } from "vue";
import Skeleton from "../skeleton/Skeleton.vue";

defineOptions({ name: "VortStatistic" });

/** Vort Statistic - 统计数值组件 */

interface Props {
    /** 数值标题 */
    title?: string;
    /** 数值内容 */
    value?: string | number;
    /** 数值精度 */
    precision?: number;
    /** 设置小数点 */
    decimalSeparator?: string;
    /** 设置千分位标识符 */
    groupSeparator?: string;
    /** 数值的前缀 */
    prefix?: string;
    /** 数值的后缀 */
    suffix?: string;
    /** 是否加载中 */
    loading?: boolean;
    /** 设置数值区域的样式 */
    valueStyle?: CSSProperties;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    decimalSeparator: ".",
    groupSeparator: ",",
    loading: false
});

// 定义插槽类型
defineSlots<{
    /** 自定义标题 */
    title?: () => unknown;
    /** 自定义前缀 */
    prefix?: () => unknown;
    /** 自定义后缀 */
    suffix?: () => unknown;
    /** 自定义格式化（会覆盖默认的数值展示） */
    formatter?: (props: { value: string | number | undefined }) => unknown;
}>();

const slots = useSlots();

/**
 * 格式化数值
 * - 处理精度
 * - 添加千分位分隔符
 */
const formattedValue = computed(() => {
    if (props.value === undefined || props.value === null) return "";

    let numValue: number;

    if (typeof props.value === "string") {
        numValue = parseFloat(props.value);
        if (isNaN(numValue)) {
            // 如果是非数字字符串，直接返回
            return props.value;
        }
    } else {
        numValue = props.value;
    }

    // 处理精度
    let strValue: string;
    if (props.precision !== undefined) {
        strValue = numValue.toFixed(props.precision);
    } else {
        strValue = String(numValue);
    }

    // 分离整数和小数部分
    const [integerPart = "", decimalPart] = strValue.split(".");

    // 添加千分位分隔符
    const formattedInteger = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, props.groupSeparator);

    // 组合结果
    if (decimalPart !== undefined) {
        return `${formattedInteger}${props.decimalSeparator}${decimalPart}`;
    }
    return formattedInteger;
});

// 是否有自定义格式化插槽
const hasFormatterSlot = computed(() => !!slots.formatter);

// 是否有自定义标题插槽
const hasTitleSlot = computed(() => !!slots.title);

// 是否有自定义前缀插槽
const hasPrefixSlot = computed(() => !!slots.prefix);

// 是否有自定义后缀插槽
const hasSuffixSlot = computed(() => !!slots.suffix);
</script>

<template>
    <div :class="['vort-statistic', props.class]">
        <!-- 标题 -->
        <div v-if="hasTitleSlot || title" class="vort-statistic-title">
            <slot name="title">{{ title }}</slot>
        </div>

        <!-- 骨架屏加载状态 -->
        <Skeleton v-if="loading" :paragraph="false" :title="{ width: '100px' }" class="vort-statistic-skeleton" />

        <!-- 数值内容 -->
        <div v-else class="vort-statistic-content" :style="valueStyle">
            <!-- 前缀 -->
            <span v-if="hasPrefixSlot || prefix" class="vort-statistic-content-prefix">
                <slot name="prefix">{{ prefix }}</slot>
            </span>

            <!-- 数值 -->
            <span class="vort-statistic-content-value">
                <slot name="formatter" :value="value">
                    {{ formattedValue }}
                </slot>
            </span>

            <!-- 后缀 -->
            <span v-if="hasSuffixSlot || suffix" class="vort-statistic-content-suffix">
                <slot name="suffix">{{ suffix }}</slot>
            </span>
        </div>
    </div>
</template>

<style scoped>
.vort-statistic {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    line-height: 1.5714285714285714;
}

.vort-statistic-title {
    margin-bottom: 4px;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.45));
    font-size: 14px;
}

.vort-statistic-skeleton {
    padding-top: 4px;
}

.vort-statistic-content {
    color: var(--vort-text, rgba(0, 0, 0, 0.88));
    font-size: 24px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.vort-statistic-content-prefix {
    display: inline-block;
    margin-right: 4px;
}

.vort-statistic-content-value {
    display: inline-block;
    direction: ltr;
}

.vort-statistic-content-suffix {
    display: inline-block;
    margin-left: 4px;
}
</style>
