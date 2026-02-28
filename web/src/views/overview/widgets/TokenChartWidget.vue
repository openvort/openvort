<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from "vue";
import * as echarts from "echarts";

const props = defineProps<{
    inputTokens: number;
    outputTokens: number;
}>();

const chartRef = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;

function render() {
    if (!chartRef.value) return;
    if (!chart) chart = echarts.init(chartRef.value);
    chart.setOption({
        tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
        legend: { bottom: 0, textStyle: { fontSize: 12 } },
        color: ["#3b82f6", "#f59e0b"],
        series: [{
            type: "pie",
            radius: ["45%", "70%"],
            center: ["50%", "45%"],
            avoidLabelOverlap: false,
            label: { show: false },
            data: [
                { value: props.inputTokens, name: "Input Tokens" },
                { value: props.outputTokens, name: "Output Tokens" },
            ],
        }],
    });
}

function handleResize() { chart?.resize(); }

watch(() => [props.inputTokens, props.outputTokens], () => { nextTick(render); });

onMounted(() => {
    nextTick(render);
    window.addEventListener("resize", handleResize);
});

onUnmounted(() => {
    window.removeEventListener("resize", handleResize);
    chart?.dispose();
});
</script>

<template>
    <vort-card :shadow="false" title="Token 用量分布">
        <div class="relative">
            <div ref="chartRef" class="w-full h-[280px]" />
            <div v-if="!inputTokens && !outputTokens"
                class="absolute inset-0 flex items-center justify-center text-gray-400 text-sm">
                暂无用量数据
            </div>
        </div>
    </vort-card>
</template>
