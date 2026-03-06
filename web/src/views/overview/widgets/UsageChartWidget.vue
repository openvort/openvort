<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from "vue";
import * as echarts from "echarts";
import { BarChart3 } from "lucide-vue-next";

const props = defineProps<{
    sessionUsage: { key: string; user_id: string; channel: string; input_tokens: number; output_tokens: number; messages: number }[];
}>();

const chartRef = ref<HTMLElement>();
let chart: echarts.ECharts | null = null;

function render() {
    if (!chartRef.value || !props.sessionUsage.length) return;
    if (!chart) chart = echarts.init(chartRef.value);
    const top = props.sessionUsage.slice(0, 10);
    const names = top.map(s => s.user_id || s.key).reverse();
    const input = top.map(s => s.input_tokens).reverse();
    const output = top.map(s => s.output_tokens).reverse();
    chart.setOption({
        tooltip: { trigger: "axis" },
        legend: { bottom: 0, textStyle: { fontSize: 12, color: "#6b7280" } },
        grid: { left: 80, right: 20, top: 10, bottom: 40 },
        xAxis: { type: "value", axisLabel: { color: "#9ca3af" }, splitLine: { lineStyle: { color: "#f3f4f6" } } },
        yAxis: { type: "category", data: names, axisLabel: { fontSize: 11, color: "#6b7280" } },
        color: ["#3b82f6", "#f59e0b"],
        series: [
            { name: "Input", type: "bar", stack: "total", data: input, barWidth: 16, itemStyle: { borderRadius: [0, 0, 0, 0] } },
            { name: "Output", type: "bar", stack: "total", data: output, barWidth: 16, itemStyle: { borderRadius: [0, 4, 4, 0] } },
        ],
    });
}

function handleResize() { chart?.resize(); }

watch(() => props.sessionUsage, () => { nextTick(render); }, { deep: true });

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
    <vort-card :shadow="false" title="会话用量 Top 10">
        <div class="relative">
            <div ref="chartRef" class="w-full h-[280px]" />
            <div v-if="!sessionUsage.length"
                class="absolute inset-0 flex flex-col items-center justify-center">
                <div class="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center mb-3">
                    <BarChart3 :size="22" class="text-blue-400" />
                </div>
                <p class="text-sm text-gray-500">暂无会话数据</p>
                <p class="text-xs text-gray-400 mt-1">有 Token 用量后将展示 Top 10 排行</p>
            </div>
        </div>
    </vort-card>
</template>
