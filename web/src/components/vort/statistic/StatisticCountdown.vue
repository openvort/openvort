<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, type CSSProperties } from "vue";

defineOptions({ name: "VortStatisticCountdown" });

/** Vort StatisticCountdown - 倒计时组件 */

interface Props {
    /** 数值标题 */
    title?: string;
    /** 目标时间戳（毫秒） */
    value?: number;
    /** 格式化字符串，参考 dayjs */
    format?: string;
    /** 数值的前缀 */
    prefix?: string;
    /** 数值的后缀 */
    suffix?: string;
    /** 设置数值区域的样式 */
    valueStyle?: CSSProperties;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    format: "HH:mm:ss"
});

const emit = defineEmits<{
    /** 倒计时完成时触发 */
    finish: [];
    /** 倒计时变化时触发 */
    change: [value: number];
}>();

// 定义插槽类型
defineSlots<{
    /** 自定义标题 */
    title?: () => unknown;
    /** 自定义前缀 */
    prefix?: () => unknown;
    /** 自定义后缀 */
    suffix?: () => unknown;
}>();

// 当前剩余时间（毫秒）
const remainingTime = ref(0);

// 定时器
let timer: ReturnType<typeof setInterval> | null = null;

// 计算剩余时间
const calculateRemaining = () => {
    if (!props.value) return 0;
    const now = Date.now();
    return Math.max(0, props.value - now);
};

// 格式化时间
const formattedValue = computed(() => {
    const totalMs = remainingTime.value;

    // 计算各时间单位
    const days = Math.floor(totalMs / (1000 * 60 * 60 * 24));
    const hours = Math.floor((totalMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((totalMs % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((totalMs % (1000 * 60)) / 1000);
    const milliseconds = Math.floor(totalMs % 1000);

    // 解析格式字符串
    let result = props.format;

    // 替换各时间单位
    // DD - 天数
    result = result.replace(/DD/g, String(days).padStart(2, "0"));
    result = result.replace(/D/g, String(days));

    // HH - 小时（包含天数的总小时）
    const totalHours = days * 24 + hours;
    result = result.replace(/HH/g, String(props.format.includes("D") ? hours : totalHours).padStart(2, "0"));
    result = result.replace(/H/g, String(props.format.includes("D") ? hours : totalHours));

    // mm - 分钟
    result = result.replace(/mm/g, String(minutes).padStart(2, "0"));
    result = result.replace(/m/g, String(minutes));

    // ss - 秒
    result = result.replace(/ss/g, String(seconds).padStart(2, "0"));
    result = result.replace(/s/g, String(seconds));

    // SSS - 毫秒
    result = result.replace(/SSS/g, String(milliseconds).padStart(3, "0"));
    result = result.replace(/SS/g, String(Math.floor(milliseconds / 10)).padStart(2, "0"));
    result = result.replace(/S/g, String(Math.floor(milliseconds / 100)));

    return result;
});

// 启动倒计时
const startCountdown = () => {
    stopCountdown();

    remainingTime.value = calculateRemaining();

    if (remainingTime.value <= 0) {
        emit("finish");
        return;
    }

    // 根据格式决定刷新间隔
    const interval = props.format.includes("S") ? 10 : 1000;

    timer = setInterval(() => {
        const remaining = calculateRemaining();
        const prevRemaining = remainingTime.value;

        remainingTime.value = remaining;

        if (remaining !== prevRemaining) {
            emit("change", remaining);
        }

        if (remaining <= 0) {
            stopCountdown();
            emit("finish");
        }
    }, interval);
};

// 停止倒计时
const stopCountdown = () => {
    if (timer) {
        clearInterval(timer);
        timer = null;
    }
};

// 监听 value 变化
watch(
    () => props.value,
    () => {
        startCountdown();
    }
);

onMounted(() => {
    startCountdown();
});

onUnmounted(() => {
    stopCountdown();
});
</script>

<template>
    <div :class="['vort-statistic', props.class]">
        <!-- 标题 -->
        <div v-if="$slots.title || title" class="vort-statistic-title">
            <slot name="title">{{ title }}</slot>
        </div>

        <!-- 数值内容 -->
        <div class="vort-statistic-content" :style="valueStyle">
            <!-- 前缀 -->
            <span v-if="$slots.prefix || prefix" class="vort-statistic-content-prefix">
                <slot name="prefix">{{ prefix }}</slot>
            </span>

            <!-- 数值 -->
            <span class="vort-statistic-content-value">
                {{ formattedValue }}
            </span>

            <!-- 后缀 -->
            <span v-if="$slots.suffix || suffix" class="vort-statistic-content-suffix">
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
