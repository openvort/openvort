<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch, onUnmounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
    Copy, Download, Edit3, CheckCircle, XCircle, AlertCircle,
    SkipForward, GitPullRequest, ExternalLink, ChevronUp,
    FileText, Table2, ClipboardList,
} from "lucide-vue-next";
import * as echarts from "echarts";
import * as XLSX from "xlsx";
import { message, Dropdown, DropdownMenuItem } from "@openvort/vort-ui";
import VortEditor from "@/components/vort-biz/editor/VortEditor.vue";
import { getVortflowTestReport, updateVortflowTestReport } from "@/api";

const route = useRoute();
const router = useRouter();
const reportId = computed(() => route.params.id as string);
const report = ref<any>({});
const loading = ref(true);
const editingTitle = ref(false);
const editTitleValue = ref("");
const editingSummary = ref(false);
const summaryText = ref("");
const summarySaving = ref(false);

const snapshot = computed(() => report.value?.snapshot || {});
const planInfo = computed(() => snapshot.value?.plan || {});
const overview = computed(() => snapshot.value?.overview || {});
const caseResult = computed(() => snapshot.value?.case_result || {});
const bugOverview = computed(() => snapshot.value?.bug_overview || {});
const bugsList = computed(() => snapshot.value?.bugs || []);
const reviewsList = computed(() => snapshot.value?.reviews || []);
const reviewStats = computed(() => snapshot.value?.review_stats || {});
const execProcess = computed(() => snapshot.value?.execution_process || {});
const caseDetails = computed(() => snapshot.value?.case_details || []);
const developerQuality = computed(() => snapshot.value?.developer_quality || []);

const durationDays = computed(() => {
    if (!planInfo.value.start_date || !planInfo.value.end_date) return null;
    const start = new Date(planInfo.value.start_date);
    const end = new Date(planInfo.value.end_date);
    const diff = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
    return diff > 0 ? diff : null;
});

const loadReport = async () => {
    loading.value = true;
    try {
        const res = await getVortflowTestReport(reportId.value) as any;
        if (res?.error) {
            message.error(res.error);
            return;
        }
        report.value = res;
        summaryText.value = res.summary || "";
    } finally {
        loading.value = false;
    }
};

const handleTitleEdit = () => {
    editTitleValue.value = report.value.title || "";
    editingTitle.value = true;
};

const handleTitleSave = async () => {
    const title = editTitleValue.value.trim();
    if (!title) return;
    await updateVortflowTestReport(reportId.value, { title });
    report.value.title = title;
    editingTitle.value = false;
};

const handleSummaryEdit = () => {
    summaryText.value = report.value.summary || "";
    editingSummary.value = true;
};

const handleSummarySave = async () => {
    summarySaving.value = true;
    try {
        await updateVortflowTestReport(reportId.value, { summary: summaryText.value });
        report.value.summary = summaryText.value;
        editingSummary.value = false;
    } finally {
        summarySaving.value = false;
    }
};

const handleCopyLink = () => {
    const url = `${window.location.origin}/vortflow/test-reports/${reportId.value}`;
    navigator.clipboard.writeText(url).then(() => message.success("链接已复制")).catch(() => message.warning("复制失败"));
};

const handleExportPdf = () => {
    window.print();
};

const _severityLabel = (s: number) => ({ 1: "致命", 2: "严重", 3: "一般", 4: "轻微" }[s] || `等级${s}`);
const _stateLabel = (s: string) => stateLabels[s] || s;
const _resultLabel = (r: string) => resultLabels[r] || r;

const handleExportExcel = () => {
    const wb = XLSX.utils.book_new();

    // Sheet 1: Overview
    const overviewData = [
        ["测试报告", report.value.title || ""],
        ["生成时间", report.value.created_at?.replace("T", " ")?.slice(0, 19) || ""],
        ["测试人员", report.value.creator_name || ""],
        ["测试开始时间", planInfo.value.start_date || ""],
        ["测试结束时间", planInfo.value.end_date || ""],
        ["关联测试计划", planInfo.value.title || ""],
        ["关联迭代", planInfo.value.iteration_name || "无"],
        ["关联版本", planInfo.value.version_name || "无"],
        [],
        ["测试结果", overview.value.verdict === "passed" ? "通过" : "不通过"],
        ["用例总数", overview.value.total_cases || 0],
        ["已执行", overview.value.executed_cases || 0],
        ["执行率", `${overview.value.exec_rate || 0}%`],
        ["通过率", `${overview.value.pass_rate || 0}%`],
        ["缺陷总数", overview.value.total_bugs || 0],
        ["缺陷解决率", `${overview.value.bug_resolve_rate ?? 100}%`],
        [],
        ["用例结果分布"],
        ["通过", caseResult.value.passed || 0],
        ["失败", caseResult.value.failed || 0],
        ["受阻", caseResult.value.blocked || 0],
        ["跳过", caseResult.value.skipped || 0],
        ["未执行", caseResult.value.unexecuted || 0],
    ];
    const wsOverview = XLSX.utils.aoa_to_sheet(overviewData);
    XLSX.utils.book_append_sheet(wb, wsOverview, "概览");

    // Sheet 2: Case details
    const caseRows = caseDetails.value.map((c: any) => ({
        "编号": c.test_case_id?.slice(0, 5)?.toUpperCase() || "",
        "标题": c.title,
        "类型": c.case_type,
        "优先级": `P${c.priority}`,
        "负责人": c.maintainer_name || "",
        "最新结果": _resultLabel(c.latest_result),
        "执行次数": c.execution_count || 0,
        "通过": c.execution_distribution?.passed || 0,
        "失败": c.execution_distribution?.failed || 0,
        "受阻": c.execution_distribution?.blocked || 0,
        "跳过": c.execution_distribution?.skipped || 0,
        "缺陷数": c.bug_count || 0,
    }));
    if (caseRows.length) {
        const wsCases = XLSX.utils.json_to_sheet(caseRows);
        XLSX.utils.book_append_sheet(wb, wsCases, "用例执行详情");
    }

    // Sheet 3: Developer Quality
    const devQualityRows = developerQuality.value.map((d: any) => ({
        "负责人": d.developer_name,
        "缺陷数": d.bug_count,
        "严重/致命": d.critical_count,
    }));
    if (devQualityRows.length) {
        const wsDevQuality = XLSX.utils.json_to_sheet(devQualityRows);
        XLSX.utils.book_append_sheet(wb, wsDevQuality, "开发者质量分析");
    }

    // Sheet 4: Bugs
    const bugRows = bugsList.value.map((b: any) => ({
        "编号": `#${b.id?.slice(0, 6)?.toUpperCase() || ""}`,
        "标题": b.title,
        "状态": _stateLabel(b.state),
        "严重程度": _severityLabel(b.severity),
        "负责人": b.assignee_name || "-",
    }));
    if (bugRows.length) {
        const wsBugs = XLSX.utils.json_to_sheet(bugRows);
        XLSX.utils.book_append_sheet(wb, wsBugs, "缺陷列表");
    }

    // Sheet 4: PRs
    const prRows = reviewsList.value.map((r: any) => ({
        "PR 编号": `#${r.pr_number}`,
        "标题": r.pr_title,
        "仓库": r.repo_name || "",
        "分支": `${r.head_branch} → ${r.base_branch}`,
        "评审人": r.reviewer_name || "-",
        "状态": r.review_status,
    }));
    if (prRows.length) {
        const wsPrs = XLSX.utils.json_to_sheet(prRows);
        XLSX.utils.book_append_sheet(wb, wsPrs, "PR列表");
    }

    const filename = `${report.value.title || "测试报告"}.xlsx`;
    XLSX.writeFile(wb, filename);
    message.success("Excel 报告已导出");
};

const handleExportExecutionDetail = () => {
    const wb = XLSX.utils.book_new();

    // Execution process summary
    const summaryData = [
        ["执行过程明细报告"],
        ["测试计划", planInfo.value.title || ""],
        ["报告时间", report.value.created_at?.replace("T", " ")?.slice(0, 19) || ""],
        [],
        ["用例总数", execProcess.value.total_cases || 0],
        ["已测用例", execProcess.value.executed_cases || 0],
        ["总测试次数", execProcess.value.total_executions || 0],
        [],
        ["执行结果分布"],
        ["通过次数", execProcess.value.result_distribution?.passed || 0],
        ["失败次数", execProcess.value.result_distribution?.failed || 0],
        ["受阻次数", execProcess.value.result_distribution?.blocked || 0],
        ["跳过次数", execProcess.value.result_distribution?.skipped || 0],
    ];
    const wsSummary = XLSX.utils.aoa_to_sheet(summaryData);
    XLSX.utils.book_append_sheet(wb, wsSummary, "执行概览");

    // Full case execution detail
    const detailRows = caseDetails.value.map((c: any) => ({
        "编号": c.test_case_id?.slice(0, 5)?.toUpperCase() || "",
        "标题": c.title,
        "类型": c.case_type,
        "优先级": `P${c.priority}`,
        "负责人": c.maintainer_name || "",
        "最新结果": _resultLabel(c.latest_result),
        "执行次数": c.execution_count || 0,
        "通过次数": c.execution_distribution?.passed || 0,
        "失败次数": c.execution_distribution?.failed || 0,
        "受阻次数": c.execution_distribution?.blocked || 0,
        "跳过次数": c.execution_distribution?.skipped || 0,
        "关联缺陷数": c.bug_count || 0,
    }));
    if (detailRows.length) {
        const wsDetail = XLSX.utils.json_to_sheet(detailRows);
        XLSX.utils.book_append_sheet(wb, wsDetail, "用例执行明细");
    }

    const filename = `${report.value.title || "测试报告"}_执行明细.xlsx`;
    XLSX.writeFile(wb, filename);
    message.success("执行明细已导出");
};

// --- ECharts ---
const caseChartRef = ref<HTMLDivElement>();
const bugStateChartRef = ref<HTMLDivElement>();
const bugSeverityChartRef = ref<HTMLDivElement>();
const devBugChartRef = ref<HTMLDivElement>();
const execBarRef = ref<HTMLDivElement>();
const execFreqBarRef = ref<HTMLDivElement>();
let chartInstances: echarts.ECharts[] = [];

const severityLabels: Record<string, string> = { "1": "致命", "2": "严重", "3": "一般", "4": "轻微" };
const severityColors: Record<string, string> = { "1": "#dc2626", "2": "#f97316", "3": "#eab308", "4": "#22c55e" };

const stateLabels: Record<string, string> = {
    open: "待确认", confirmed: "已确认", fixing: "修复中",
    resolved: "已修复", verified: "已验证", closed: "已关闭",
    not_reproducible: "无法复现", reopened: "再次打开",
    by_design: "设计如此", deferred: "延期修复",
};

const resultLabels: Record<string, string> = { passed: "通过", failed: "失败", blocked: "受阻", skipped: "跳过" };
const resultColors: Record<string, string> = { passed: "#22c55e", failed: "#ef4444", blocked: "#f97316", skipped: "#3b82f6" };

const priorityLabels: Record<number, string> = { 0: "P0", 1: "P1", 2: "P2", 3: "P3" };
const priorityColors: Record<number, string> = { 0: "#ef4444", 1: "#ef4444", 2: "#f97316", 3: "#94a3b8" };

function makePieOption(data: { name: string; value: number; color?: string }[]): any {
    return {
        tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
        legend: { show: false },
        series: [{
            type: "pie",
            radius: ["45%", "70%"],
            avoidLabelOverlap: false,
            label: { show: false },
            data: data.map(d => ({ name: d.name, value: d.value, itemStyle: d.color ? { color: d.color } : {} })),
        }],
    };
}

function initCharts() {
    chartInstances.forEach(c => c.dispose());
    chartInstances = [];

    if (caseChartRef.value) {
        const chart = echarts.init(caseChartRef.value);
        const data = [
            { name: "通过", value: caseResult.value.passed || 0, color: "#22c55e" },
            { name: "失败", value: caseResult.value.failed || 0, color: "#ef4444" },
            { name: "受阻", value: caseResult.value.blocked || 0, color: "#f97316" },
            { name: "跳过", value: caseResult.value.skipped || 0, color: "#3b82f6" },
            { name: "未执行", value: caseResult.value.unexecuted || 0, color: "#d1d5db" },
        ].filter(d => d.value > 0);
        chart.setOption(makePieOption(data));
        chartInstances.push(chart);
    }

    if (bugStateChartRef.value && Object.keys(bugOverview.value.state_distribution || {}).length) {
        const chart = echarts.init(bugStateChartRef.value);
        const data = Object.entries(bugOverview.value.state_distribution).map(([k, v]) => ({
            name: stateLabels[k] || k, value: v as number,
        }));
        chart.setOption(makePieOption(data));
        chartInstances.push(chart);
    }

    if (bugSeverityChartRef.value && Object.keys(bugOverview.value.severity_distribution || {}).length) {
        const chart = echarts.init(bugSeverityChartRef.value);
        const data = Object.entries(bugOverview.value.severity_distribution).map(([k, v]) => ({
            name: severityLabels[k] || k, value: v as number, color: severityColors[k],
        }));
        chart.setOption(makePieOption(data));
        chartInstances.push(chart);
    }

    if (devBugChartRef.value && developerQuality.value.length) {
        const chart = echarts.init(devBugChartRef.value);
        const data = developerQuality.value.map((d: any) => ({
            name: d.developer_name, value: d.bug_count,
        }));
        chart.setOption(makePieOption(data));
        chartInstances.push(chart);
    }

    // Execution result distribution bar
    if (execBarRef.value) {
        const chart = echarts.init(execBarRef.value);
        const dist = execProcess.value.result_distribution || {};
        const total = Object.values(dist).reduce((s: number, v) => s + (v as number), 0);
        const categories = ["passed", "failed", "blocked", "skipped"];
        const seriesData = categories.filter(k => dist[k]).map(k => ({
            name: resultLabels[k], value: dist[k], itemStyle: { color: resultColors[k] },
        }));
        chart.setOption({
            tooltip: { trigger: "item", formatter: (p: any) => `${p.name}: ${p.value}次 (${total ? ((p.value / total) * 100).toFixed(1) : 0}%)` },
            grid: { left: 0, right: 0, top: 0, bottom: 0 },
            xAxis: { type: "value", max: total || 1, show: false },
            yAxis: { type: "category", data: [""], show: false },
            series: seriesData.map(d => ({
                type: "bar", stack: "total", barWidth: 16, data: [d.value],
                name: d.name, itemStyle: d.itemStyle,
            })),
        });
        chartInstances.push(chart);
    }

    // Execution frequency bar
    if (execFreqBarRef.value) {
        const chart = echarts.init(execFreqBarRef.value);
        const freq = execProcess.value.frequency_distribution || {};
        const totalCases = Object.values(freq).reduce((s: number, v) => s + (v as number), 0);
        const freqColors = ["#a78bfa", "#6366f1", "#3b82f6", "#14b8a6", "#22c55e", "#eab308"];
        const freqData = Object.entries(freq).map(([k, v], i) => ({
            name: `${k}次`, value: v as number, itemStyle: { color: freqColors[i % freqColors.length] },
        }));
        chart.setOption({
            tooltip: { trigger: "item", formatter: (p: any) => `${p.name}: ${p.value}个 (${totalCases ? ((p.value / totalCases) * 100).toFixed(1) : 0}%)` },
            grid: { left: 0, right: 0, top: 0, bottom: 0 },
            xAxis: { type: "value", max: totalCases || 1, show: false },
            yAxis: { type: "category", data: [""], show: false },
            series: freqData.map(d => ({
                type: "bar", stack: "total", barWidth: 16, data: [d.value],
                name: d.name, itemStyle: d.itemStyle,
            })),
        });
        chartInstances.push(chart);
    }
}

const handleResize = () => {
    chartInstances.forEach(c => c.resize());
};

onMounted(async () => {
    await loadReport();
    await nextTick();
    initCharts();
    window.addEventListener("resize", handleResize);
});

watch(() => snapshot.value, async () => {
    await nextTick();
    initCharts();
}, { deep: true });

onUnmounted(() => {
    chartInstances.forEach(c => c.dispose());
    window.removeEventListener("resize", handleResize);
});
</script>

<template>
    <div class="min-h-screen bg-gray-50">
        <vort-spin :spinning="loading">
            <!-- Top bar -->
            <div class="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between print:hidden">
                <div class="flex items-center gap-2">
                    <a class="text-sm text-gray-500 hover:text-blue-600 cursor-pointer" @click="router.back()">
                        &larr;
                    </a>
                    <template v-if="editingTitle">
                        <vort-input
                            v-model="editTitleValue"
                            size="small"
                            class="w-[300px]"
                            @keyup.enter="handleTitleSave"
                            @blur="handleTitleSave"
                        />
                    </template>
                    <template v-else>
                        <h2 class="text-base font-medium text-gray-800">{{ report.title }}</h2>
                        <Edit3 :size="14" class="text-gray-400 cursor-pointer hover:text-blue-500" @click="handleTitleEdit" />
                    </template>
                </div>
                <div class="flex items-center gap-2">
                    <vort-button size="small" @click="handleCopyLink">
                        <Copy :size="14" class="mr-1" /> 复制报告链接
                    </vort-button>
                    <Dropdown trigger="click" placement="bottomRight">
                        <vort-button variant="primary" size="small">
                            <Download :size="14" class="mr-1" /> 导出 <ChevronUp :size="12" class="ml-1" />
                        </vort-button>
                        <template #overlay>
                            <DropdownMenuItem @click="handleExportPdf">
                                <FileText :size="14" class="mr-2 text-gray-400" /> 导出 PDF 报告
                            </DropdownMenuItem>
                            <DropdownMenuItem @click="handleExportExcel">
                                <Table2 :size="14" class="mr-2 text-gray-400" /> 生成 Excel 报告
                            </DropdownMenuItem>
                            <DropdownMenuItem @click="handleExportExecutionDetail">
                                <ClipboardList :size="14" class="mr-2 text-gray-400" /> 生成执行明细 (Excel)
                            </DropdownMenuItem>
                        </template>
                    </Dropdown>
                </div>
            </div>

            <!-- Report body -->
            <div class="max-w-[800px] mx-auto py-8 px-4 space-y-6 print:max-w-none print:py-0">
                <!-- Report header -->
                <div class="bg-white rounded-xl p-8 text-center">
                    <h1 class="text-xl font-bold text-gray-800 mb-2">{{ report.title }}</h1>
                    <p class="text-sm text-gray-400">
                        报告生成时间: {{ report.created_at?.replace('T', ' ')?.slice(0, 19) }}
                    </p>
                </div>

                <!-- Basic info -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">基本信息</h3>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                        <div>
                            <span class="text-gray-400">测试人员</span>
                            <div class="mt-1 text-gray-800 font-medium">{{ report.creator_name || '-' }}</div>
                        </div>
                        <div>
                            <span class="text-gray-400">测试开始时间</span>
                            <div class="mt-1 text-gray-800 font-medium">{{ planInfo.start_date || '-' }}</div>
                        </div>
                        <div>
                            <span class="text-gray-400">测试结束时间</span>
                            <div class="mt-1 text-gray-800 font-medium">{{ planInfo.end_date || '-' }}</div>
                        </div>
                        <div>
                            <span class="text-gray-400">持续时长</span>
                            <div class="mt-1 text-gray-800 font-medium">{{ durationDays ? `${durationDays} 天` : '-' }}</div>
                        </div>
                    </div>
                </div>

                <!-- Related info -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">关联信息</h3>
                    <div class="grid grid-cols-3 gap-4 text-sm">
                        <div>
                            <span class="text-gray-400">关联测试计划</span>
                            <div class="mt-1 text-gray-800">{{ planInfo.title || '-' }} <span v-if="planInfo.start_date" class="text-gray-400">({{ planInfo.start_date }} ~ {{ planInfo.end_date }})</span></div>
                        </div>
                        <div>
                            <span class="text-gray-400">关联迭代</span>
                            <div class="mt-1 text-gray-800">{{ planInfo.iteration_name || '无' }}</div>
                        </div>
                        <div>
                            <span class="text-gray-400">关联版本</span>
                            <div class="mt-1 text-gray-800">{{ planInfo.version_name || '无' }}</div>
                        </div>
                    </div>
                </div>

                <!-- Summary (editable) -->
                <div class="bg-white rounded-xl p-6">
                    <div class="flex items-center justify-between mb-3">
                        <h3 class="text-sm font-semibold text-gray-700">报告总结</h3>
                        <template v-if="editingSummary">
                            <div class="flex items-center gap-2">
                                <vort-button size="small" @click="editingSummary = false">取消</vort-button>
                                <vort-button variant="primary" size="small" :loading="summarySaving" @click="handleSummarySave">保存</vort-button>
                            </div>
                        </template>
                        <a v-else class="text-xs text-blue-600 cursor-pointer" @click="handleSummaryEdit">编辑报告 &nearr;</a>
                    </div>
                    <VortEditor
                        v-model="summaryText"
                        :readonly="!editingSummary"
                        :placeholder="editingSummary ? '输入报告总结内容...' : ''"
                        min-height="200px"
                    />
                </div>

                <!-- Overview -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">整体概览</h3>
                    <div class="grid grid-cols-5 gap-4 text-center">
                        <div>
                            <div class="text-xs text-gray-400 mb-1">测试结果</div>
                            <div v-if="overview.verdict === 'passed'" class="inline-flex items-center gap-1 text-green-600 font-semibold">
                                <CheckCircle :size="16" /> 通过
                            </div>
                            <div v-else class="inline-flex items-center gap-1 text-red-500 font-semibold">
                                <XCircle :size="16" /> 不通过
                            </div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">用例总数</div>
                            <div class="text-xl font-bold text-gray-800">{{ overview.total_cases || 0 }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">缺陷总数</div>
                            <div class="text-xl font-bold text-gray-800">{{ overview.total_bugs || 0 }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">用例通过率</div>
                            <div class="text-xl font-bold" :class="(overview.pass_rate || 0) >= 90 ? 'text-green-600' : (overview.pass_rate || 0) >= 70 ? 'text-orange-500' : 'text-red-500'">{{ overview.pass_rate || 0 }}%</div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">缺陷解决率</div>
                            <div class="text-xl font-bold" :class="(overview.bug_resolve_rate || 0) >= 80 ? 'text-green-600' : 'text-orange-500'">{{ overview.bug_resolve_rate ?? 100 }}%</div>
                        </div>
                    </div>
                </div>

                <!-- Case result -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">用例结果</h3>
                    <div class="flex items-center gap-8">
                        <div class="flex gap-8 text-center">
                            <div>
                                <div class="text-xs text-gray-400 mb-1">用例总数</div>
                                <div class="text-2xl font-bold text-gray-800">{{ overview.total_cases || 0 }}</div>
                            </div>
                            <div>
                                <div class="text-xs text-gray-400 mb-1">执行率</div>
                                <div class="text-2xl font-bold text-gray-800">{{ overview.exec_rate || 0 }}%</div>
                            </div>
                            <div>
                                <div class="text-xs text-gray-400 mb-1">通过率</div>
                                <div class="text-2xl font-bold text-gray-800">{{ overview.pass_rate || 0 }}%</div>
                            </div>
                        </div>
                        <div ref="caseChartRef" class="w-[160px] h-[160px] shrink-0" />
                        <div class="flex-1 space-y-1.5 text-sm">
                            <div v-if="caseResult.passed" class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-green-500 shrink-0" />
                                <span class="text-gray-600">通过</span>
                                <span class="ml-auto text-gray-800 font-medium">{{ caseResult.passed }} 个</span>
                                <span class="text-gray-400 w-[50px] text-right">{{ overview.total_cases ? ((caseResult.passed / overview.total_cases) * 100).toFixed(1) : 0 }}%</span>
                            </div>
                            <div v-if="caseResult.failed" class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0" />
                                <span class="text-gray-600">失败</span>
                                <span class="ml-auto text-gray-800 font-medium">{{ caseResult.failed }} 个</span>
                                <span class="text-gray-400 w-[50px] text-right">{{ overview.total_cases ? ((caseResult.failed / overview.total_cases) * 100).toFixed(1) : 0 }}%</span>
                            </div>
                            <div v-if="caseResult.blocked" class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-orange-400 shrink-0" />
                                <span class="text-gray-600">受阻</span>
                                <span class="ml-auto text-gray-800 font-medium">{{ caseResult.blocked }} 个</span>
                                <span class="text-gray-400 w-[50px] text-right">{{ overview.total_cases ? ((caseResult.blocked / overview.total_cases) * 100).toFixed(1) : 0 }}%</span>
                            </div>
                            <div v-if="caseResult.skipped" class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-blue-400 shrink-0" />
                                <span class="text-gray-600">跳过</span>
                                <span class="ml-auto text-gray-800 font-medium">{{ caseResult.skipped }} 个</span>
                                <span class="text-gray-400 w-[50px] text-right">{{ overview.total_cases ? ((caseResult.skipped / overview.total_cases) * 100).toFixed(1) : 0 }}%</span>
                            </div>
                            <div v-if="caseResult.unexecuted" class="flex items-center gap-2">
                                <span class="w-2.5 h-2.5 rounded-full bg-gray-300 shrink-0" />
                                <span class="text-gray-600">未执行</span>
                                <span class="ml-auto text-gray-800 font-medium">{{ caseResult.unexecuted }} 个</span>
                                <span class="text-gray-400 w-[50px] text-right">{{ overview.total_cases ? ((caseResult.unexecuted / overview.total_cases) * 100).toFixed(1) : 0 }}%</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Bug overview -->
                <div v-if="bugOverview.total > 0" class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">缺陷概览</h3>
                    <div class="flex items-start gap-6">
                        <div class="text-center">
                            <div class="text-xs text-gray-400 mb-1">总数</div>
                            <div class="text-2xl font-bold text-gray-800">{{ bugOverview.total }}</div>
                            <div class="text-xs text-gray-400 mt-2 mb-1">解决率</div>
                            <div class="text-2xl font-bold" :class="bugOverview.resolve_rate >= 80 ? 'text-green-600' : 'text-orange-500'">{{ bugOverview.resolve_rate }}%</div>
                        </div>
                        <div v-if="Object.keys(bugOverview.state_distribution || {}).length" class="flex-1 flex items-center gap-3">
                            <div ref="bugStateChartRef" class="w-[120px] h-[120px] shrink-0" />
                            <div class="space-y-1 text-sm">
                                <div v-for="(count, state) in bugOverview.state_distribution" :key="state" class="flex items-center gap-2">
                                    <span class="w-2 h-2 rounded-full bg-gray-400 shrink-0" />
                                    <span class="text-gray-600">{{ stateLabels[state as string] || state }}</span>
                                    <span class="ml-2 text-gray-800 font-medium">{{ count }} 个</span>
                                    <span class="text-gray-400">{{ bugOverview.total ? (((count as number) / bugOverview.total) * 100).toFixed(1) : 0 }}%</span>
                                </div>
                            </div>
                        </div>
                        <div v-if="Object.keys(bugOverview.severity_distribution || {}).length" class="flex-1 flex items-center gap-3">
                            <div ref="bugSeverityChartRef" class="w-[120px] h-[120px] shrink-0" />
                            <div class="space-y-1 text-sm">
                                <div v-for="(count, sev) in bugOverview.severity_distribution" :key="sev" class="flex items-center gap-2">
                                    <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: severityColors[sev as string] || '#94a3b8' }" />
                                    <span class="text-gray-600">{{ severityLabels[sev as string] || `等级${sev}` }}</span>
                                    <span class="ml-2 text-gray-800 font-medium">{{ count }} 个</span>
                                    <span class="text-gray-400">{{ bugOverview.total ? (((count as number) / bugOverview.total) * 100).toFixed(1) : 0 }}%</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Developer quality analysis -->
                <div v-if="developerQuality.length" class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">开发者质量分析</h3>
                    <div class="flex items-start gap-6">
                        <div ref="devBugChartRef" class="w-[160px] h-[160px] shrink-0" />
                        <div class="flex-1 overflow-auto">
                            <vort-table :data-source="developerQuality" :pagination="false" row-key="developer_name" size="small">
                                <vort-table-column label="开发者" :min-width="100">
                                    <template #default="{ row }">
                                        <span class="text-sm text-gray-800 font-medium">{{ row.developer_name }}</span>
                                    </template>
                                </vort-table-column>
                                <vort-table-column label="缺陷数" :width="80" align="center">
                                    <template #default="{ row }">
                                        <span class="text-sm font-bold" :class="row.bug_count > 3 ? 'text-red-500' : 'text-gray-800'">{{ row.bug_count }}</span>
                                    </template>
                                </vort-table-column>
                                <vort-table-column label="严重/致命" :width="90" align="center">
                                    <template #default="{ row }">
                                        <span class="text-sm" :class="row.critical_count > 0 ? 'text-red-500 font-medium' : 'text-gray-500'">{{ row.critical_count }}</span>
                                    </template>
                                </vort-table-column>
                            </vort-table>
                        </div>
                    </div>
                </div>

                <!-- Bug list -->
                <div v-if="bugsList.length" class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">缺陷列表 ({{ bugsList.length }})</h3>
                    <vort-table :data-source="bugsList" :pagination="false" row-key="id" size="small">
                        <vort-table-column label="标题" :min-width="200">
                            <template #default="{ row }">
                                <div class="flex items-center gap-1.5">
                                    <span class="text-xs text-red-500 font-mono">#{{ row.id?.slice(0, 6)?.toUpperCase() }}</span>
                                    <span class="text-sm text-gray-800">{{ row.title }}</span>
                                </div>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="任务状态" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-500">{{ stateLabels[row.state] || row.state }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="优先级" :width="100">
                            <template #default="{ row }">
                                <vort-tag size="small" :color="row.severity <= 2 ? 'red' : 'default'">
                                    {{ severityLabels[String(row.severity)] || `等级${row.severity}` }}
                                </vort-tag>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="负责人" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-600">{{ row.assignee_name || '-' }}</span>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>

                <!-- PR list -->
                <div v-if="reviewsList.length" class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">PR 列表 ({{ reviewsList.length }})</h3>
                    <vort-table :data-source="reviewsList" :pagination="false" row-key="id" size="small">
                        <vort-table-column label="标题" :min-width="280">
                            <template #default="{ row }">
                                <div class="flex items-center gap-1.5">
                                    <GitPullRequest :size="14" class="text-gray-400 shrink-0" />
                                    <a v-if="row.pr_url" :href="row.pr_url" target="_blank" class="text-sm text-blue-600 hover:underline truncate">
                                        #{{ row.pr_number }} {{ row.pr_title }}
                                    </a>
                                    <span v-else class="text-sm text-gray-800 truncate">#{{ row.pr_number }} {{ row.pr_title }}</span>
                                </div>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="评审人" :width="120">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-600">{{ row.reviewer_name || '-' }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="测试者" :width="120">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-600">{{ row.added_by_name || '-' }}</span>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>

                <!-- Execution process overview -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">执行过程概览</h3>
                    <div class="grid grid-cols-3 gap-4 text-center mb-6">
                        <div>
                            <div class="text-xs text-gray-400 mb-1">用例总数</div>
                            <div class="text-2xl font-bold text-gray-800">{{ execProcess.total_cases || 0 }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">已测用例</div>
                            <div class="text-2xl font-bold text-gray-800">{{ execProcess.executed_cases || 0 }}</div>
                        </div>
                        <div>
                            <div class="text-xs text-gray-400 mb-1">总测试次数</div>
                            <div class="text-2xl font-bold text-gray-800">{{ execProcess.total_executions || 0 }}</div>
                        </div>
                    </div>

                    <div class="space-y-4">
                        <div>
                            <div class="text-xs text-gray-500 mb-2">
                                执行过程结果分布
                                <template v-for="(count, key) in (execProcess.result_distribution || {})" :key="key">
                                    <span v-if="count" class="ml-2">
                                        <span class="inline-block w-2 h-2 rounded-full mr-0.5" :style="{ backgroundColor: resultColors[key as string] }" />
                                        {{ resultLabels[key as string] || key }} {{ count }}次
                                        {{ execProcess.total_executions ? (((count as number) / execProcess.total_executions) * 100).toFixed(1) : 0 }}%
                                    </span>
                                </template>
                            </div>
                            <div ref="execBarRef" class="w-full h-[20px]" />
                        </div>

                        <div>
                            <div class="text-xs text-gray-500 mb-2">
                                用例测试次数分布
                                <template v-for="(count, times) in (execProcess.frequency_distribution || {})" :key="times">
                                    <span class="ml-2">
                                        <span class="inline-block w-2 h-2 rounded-full mr-0.5 bg-blue-400" />
                                        {{ times }}次 {{ count }}个
                                        {{ execProcess.total_cases ? (((count as number) / execProcess.total_cases) * 100).toFixed(1) : 0 }}%
                                    </span>
                                </template>
                            </div>
                            <div ref="execFreqBarRef" class="w-full h-[20px]" />
                        </div>
                    </div>
                </div>

                <!-- Case execution details -->
                <div class="bg-white rounded-xl p-6">
                    <h3 class="text-sm font-semibold text-gray-700 mb-4">用例执行详情 ({{ caseDetails.length }})</h3>
                    <vort-table :data-source="caseDetails" :pagination="false" row-key="test_case_id" size="small">
                        <vort-table-column label="标题" :min-width="200">
                            <template #default="{ row }">
                                <div class="flex items-center gap-1.5">
                                    <span class="text-xs text-gray-400 font-mono">{{ row.test_case_id?.slice(0, 5)?.toUpperCase() }}</span>
                                    <span class="text-sm text-gray-800">{{ row.title }}</span>
                                </div>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="执行结果分布" :width="140">
                            <template #default="{ row }">
                                <div v-if="row.execution_count" class="flex items-center gap-1">
                                    <span v-if="row.execution_distribution?.passed" class="exec-badge exec-badge-passed">{{ row.execution_distribution.passed }}</span>
                                    <span v-if="row.execution_distribution?.failed" class="exec-badge exec-badge-failed">{{ row.execution_distribution.failed }}</span>
                                    <span v-if="row.execution_distribution?.blocked" class="exec-badge exec-badge-blocked">{{ row.execution_distribution.blocked }}</span>
                                    <span v-if="row.execution_distribution?.skipped" class="exec-badge exec-badge-skipped">{{ row.execution_distribution.skipped }}</span>
                                </div>
                                <span v-else class="text-sm text-gray-400">0</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="已执行次数" :width="100" align="center">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-700">{{ row.execution_count || 0 }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="缺陷数" :width="80" align="center">
                            <template #default="{ row }">
                                <span class="text-sm" :class="row.bug_count > 0 ? 'text-red-500 font-medium' : 'text-gray-500'">{{ row.bug_count || 0 }}</span>
                            </template>
                        </vort-table-column>
                        <vort-table-column label="优先级" :width="70">
                            <template #default="{ row }">
                                <vort-tag :color="priorityColors[row.priority] || 'default'" size="small">
                                    {{ priorityLabels[row.priority] || `P${row.priority}` }}
                                </vort-tag>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>
            </div>
        </vort-spin>
    </div>
</template>

<style scoped>
.exec-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 22px;
    padding: 0 6px;
    font-size: 12px;
    font-weight: 600;
    border-radius: 4px;
    line-height: 1;
}
.exec-badge-passed { color: #16a34a; background: #f0fdf4; }
.exec-badge-blocked { color: #ea580c; background: #fff7ed; }
.exec-badge-failed { color: #dc2626; background: #fef2f2; }
.exec-badge-skipped { color: #2563eb; background: #eff6ff; }

@media print {
    .bg-gray-50 { background: white !important; }
    .rounded-xl { border-radius: 0 !important; border-bottom: 1px solid #e5e7eb; }
}
</style>
