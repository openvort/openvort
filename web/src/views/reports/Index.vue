<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import {
    getReports, getReportDetail, submitReport, reviewReport,
    getReportTemplates, createReportTemplate, deleteReportTemplate,
    getReportRules, createReportRule, deleteReportRule,
    getReportStats, getMembers, generateReportContentPrompt,
    getReportingRelations, createReportingRelation, deleteReportingRelation,
} from "@/api";
import {
    Plus, FileText, Send, CheckCircle, XCircle, Clock,
    BarChart3, Settings, ChevronLeft, ChevronRight, Eye, Bot,
    ArrowRight,
} from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import { useUserStore } from "@/stores";

// ---- Types ----

interface ReportItem {
    id: string;
    report_type: string;
    report_date: string;
    title: string;
    content: string;
    status: string;
    reporter_id: string;
    reviewer_id: string;
    auto_generated: boolean;
    submitted_at: string | null;
    reviewed_at: string | null;
    reviewer_comment: string;
    created_at: string;
}

interface TemplateItem {
    id: string;
    name: string;
    report_type: string;
    content_schema: object;
    auto_collect: object;
    created_at: string;
}

interface RuleItem {
    id: string;
    template_id: string;
    template_name: string;
    scope: string;
    target_id: string;
    reviewer_id: string;
    deadline_cron: string;
    reminder_minutes: number;
    escalation_minutes: number;
    enabled: boolean;
}

interface MemberItem {
    id: string;
    name: string;
    email: string;
}

// ---- State ----

const userStore = useUserStore();
const router = useRouter();
const activeTab = ref("my");
const isAdmin = computed(() => userStore.userInfo.roles.includes("admin") || userStore.userInfo.roles.includes("manager"));

// My reports
const myReports = ref<ReportItem[]>([]);
const loadingMy = ref(false);
const myFilterType = ref("");
const myFilterStatus = ref("");

// Subordinate reports
const subReports = ref<ReportItem[]>([]);
const loadingSub = ref(false);
const subFilterStatus = ref("");

// Report detail
const detailVisible = ref(false);
const detailReport = ref<ReportItem | null>(null);
const detailLoading = ref(false);

// Submit dialog
const submitDialogOpen = ref(false);
const submitForm = ref({ report_type: "daily", title: "", content: "", report_date: "" });
const submitting = ref(false);

// Review dialog
const reviewDialogOpen = ref(false);
const reviewForm = ref({ status: "reviewed", comment: "" });
const reviewing = ref(false);
const reviewReportId = ref("");

// Settings tab
const templates = ref<TemplateItem[]>([]);
const rules = ref<RuleItem[]>([]);
const loadingTemplates = ref(false);
const loadingRules = ref(false);

// Template dialog
const templateDialogOpen = ref(false);
const templateForm = ref({ name: "", report_type: "daily" });
const savingTemplate = ref(false);

// Rule dialog
const ruleDialogOpen = ref(false);
const ruleForm = ref({ template_id: "", scope: "member", target_id: "", reviewer_id: "", deadline_cron: "0 18 * * 1-5" });
const savingRule = ref(false);

// Member search for rules
const ruleMemberSearch = ref("");
const ruleMemberResults = ref<MemberItem[]>([]);

// Stats
const stats = ref({ total: 0, draft: 0, submitted: 0, reviewed: 0, rejected: 0 });

// ---- Helpers ----

const typeOptions = [
    { label: "全部", value: "" },
    { label: "日报", value: "daily" },
    { label: "周报", value: "weekly" },
    { label: "月报", value: "monthly" },
];
const statusOptions = [
    { label: "全部", value: "" },
    { label: "草稿", value: "draft" },
    { label: "已提交", value: "submitted" },
    { label: "已审阅", value: "reviewed" },
    { label: "已退回", value: "rejected" },
];
const typeLabel = (val: string) => ({ daily: "日报", weekly: "周报", monthly: "月报" }[val] || val);
const typeColor = (val: string) => ({ daily: "blue", weekly: "purple", monthly: "orange" }[val] || "default");
const statusLabel = (val: string) => ({ draft: "草稿", submitted: "已提交", reviewed: "已审阅", rejected: "已退回" }[val] || val);
const statusColor = (val: string) => ({ draft: "default", submitted: "processing", reviewed: "green", rejected: "red" }[val] || "default");

// ---- My Reports ----

async function loadMyReports() {
    loadingMy.value = true;
    try {
        const params: Record<string, any> = { page_size: 50 };
        if (myFilterType.value) params.report_type = myFilterType.value;
        if (myFilterStatus.value) params.status = myFilterStatus.value;
        const res: any = await getReports(params);
        myReports.value = res?.items || [];
    } catch { /* ignore */ }
    finally { loadingMy.value = false; }
}

// ---- Subordinate Reports ----

async function loadSubReports() {
    loadingSub.value = true;
    try {
        const params: Record<string, any> = { reviewer_id: userStore.userInfo.id, page_size: 50 };
        if (subFilterStatus.value) params.status = subFilterStatus.value;
        const res: any = await getReports(params);
        subReports.value = res?.items || [];
    } catch { /* ignore */ }
    finally { loadingSub.value = false; }
}

// ---- Detail ----

async function openDetail(reportId: string) {
    detailVisible.value = true;
    detailLoading.value = true;
    try {
        const res: any = await getReportDetail(reportId);
        detailReport.value = res;
    } catch { message.error("加载失败"); }
    finally { detailLoading.value = false; }
}

// ---- Submit ----

function openSubmitDialog() {
    submitForm.value = { report_type: "daily", title: "", content: "", report_date: "" };
    submitDialogOpen.value = true;
}

async function handleSubmit() {
    if (!submitForm.value.content.trim()) {
        message.error("请填写汇报内容");
        return;
    }
    submitting.value = true;
    try {
        const res: any = await submitReport({
            report_type: submitForm.value.report_type,
            title: submitForm.value.title || `${typeLabel(submitForm.value.report_type)} - ${submitForm.value.report_date || new Date().toISOString().slice(0, 10)}`,
            content: submitForm.value.content,
            report_date: submitForm.value.report_date || undefined,
        });
        if (res?.success) {
            message.success("汇报已提交");
            submitDialogOpen.value = false;
            await loadMyReports();
        } else { message.error("提交失败"); }
    } catch { message.error("提交失败"); }
    finally { submitting.value = false; }
}

// AI 生成汇报内容
async function handleAiGenerateContent(reportType?: string, reportDate?: string) {
    const type = reportType || submitForm.value.report_type;
    const date = reportDate || submitForm.value.report_date || new Date().toISOString().slice(0, 10);
    if (!type) {
        message.warning("请先选择汇报类型");
        return;
    }
    try {
        const res: any = await generateReportContentPrompt(type, date);
        if (res?.prompt) {
            submitDialogOpen.value = false;
            router.push({ name: "chat", query: { prompt: res.prompt } });
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "生成失败");
    }
}

// ---- Review ----

function openReviewDialog(reportId: string) {
    reviewReportId.value = reportId;
    reviewForm.value = { status: "reviewed", comment: "" };
    reviewDialogOpen.value = true;
}

async function handleReview() {
    reviewing.value = true;
    try {
        const res: any = await reviewReport(reviewReportId.value, reviewForm.value);
        if (res?.success) {
            message.success(reviewForm.value.status === "reviewed" ? "已通过" : "已退回");
            reviewDialogOpen.value = false;
            detailVisible.value = false;
            await loadSubReports();
        } else { message.error("操作失败"); }
    } catch { message.error("操作失败"); }
    finally { reviewing.value = false; }
}

// ---- Settings ----

async function loadTemplates() {
    loadingTemplates.value = true;
    try {
        const res: any = await getReportTemplates();
        templates.value = res?.templates || [];
    } catch { /* ignore */ }
    finally { loadingTemplates.value = false; }
}

async function loadRules() {
    loadingRules.value = true;
    try {
        const res: any = await getReportRules();
        rules.value = res?.rules || [];
    } catch { /* ignore */ }
    finally { loadingRules.value = false; }
}

async function loadStats() {
    try {
        const res: any = await getReportStats();
        stats.value = res || { total: 0, draft: 0, submitted: 0, reviewed: 0, rejected: 0 };
    } catch { /* ignore */ }
}

function openTemplateDialog() {
    templateForm.value = { name: "", report_type: "daily" };
    templateDialogOpen.value = true;
}

async function handleSaveTemplate() {
    if (!templateForm.value.name.trim()) {
        message.error("请输入模板名称");
        return;
    }
    savingTemplate.value = true;
    try {
        const res: any = await createReportTemplate(templateForm.value);
        if (res?.success) {
            message.success("模板已创建");
            templateDialogOpen.value = false;
            await loadTemplates();
        } else { message.error("创建失败"); }
    } catch { message.error("创建失败"); }
    finally { savingTemplate.value = false; }
}

async function handleDeleteTemplate(id: string) {
    try {
        const res: any = await deleteReportTemplate(id);
        if (res?.success) {
            message.success("已删除");
            await loadTemplates();
        }
    } catch { message.error("删除失败"); }
}

async function searchRuleMembers() {
    if (!ruleMemberSearch.value.trim()) return;
    try {
        const res: any = await getMembers({ search: ruleMemberSearch.value, size: 10 });
        ruleMemberResults.value = res?.members || [];
    } catch { ruleMemberResults.value = []; }
}

function openRuleDialog() {
    ruleForm.value = { template_id: "", scope: "member", target_id: "", reviewer_id: "", deadline_cron: "0 18 * * 1-5" };
    ruleMemberSearch.value = "";
    ruleMemberResults.value = [];
    ruleDialogOpen.value = true;
}

async function handleSaveRule() {
    if (!ruleForm.value.template_id || !ruleForm.value.target_id) {
        message.error("请选择模板和目标成员");
        return;
    }
    savingRule.value = true;
    try {
        const res: any = await createReportRule(ruleForm.value);
        if (res?.success) {
            message.success("规则已创建");
            ruleDialogOpen.value = false;
            await loadRules();
        } else { message.error("创建失败"); }
    } catch { message.error("创建失败"); }
    finally { savingRule.value = false; }
}

async function handleDeleteRule(id: string) {
    try {
        const res: any = await deleteReportRule(id);
        if (res?.success) {
            message.success("已删除");
            await loadRules();
        }
    } catch { message.error("删除失败"); }
}

// ---- 汇报关系 ----

interface RelationItem {
    id: number;
    reporter_id: string;
    reporter_name: string;
    supervisor_id: string;
    supervisor_name: string;
    relation_type: string;
    is_primary: boolean;
    created_at: string;
}

const relations = ref<RelationItem[]>([]);
const loadingRelations = ref(false);

const relationDialogOpen = ref(false);
const relationForm = ref({ reporter_id: "", supervisor_id: "", relation_type: "direct" });
const savingRelation = ref(false);
const relationMemberSearch = ref("");
const relationMemberResults = ref<MemberItem[]>([]);

const relationTypeOptions = [
    { label: "直属", value: "direct" },
    { label: "虚线", value: "dotted" },
    { label: "职能", value: "functional" },
];

const relationTypeLabel = (val: string) => relationTypeOptions.find(o => o.value === val)?.label || val;

async function loadRelations() {
    loadingRelations.value = true;
    try {
        const res: any = await getReportingRelations();
        relations.value = res?.relations || [];
    } catch { /* ignore */ }
    finally { loadingRelations.value = false; }
}

function openRelationDialog() {
    relationForm.value = { reporter_id: "", supervisor_id: "", relation_type: "direct" };
    relationMemberSearch.value = "";
    relationMemberResults.value = [];
    relationDialogOpen.value = true;
}

async function searchRelationMembers() {
    if (!relationMemberSearch.value.trim()) return;
    try {
        const res: any = await getMembers({ search: relationMemberSearch.value, size: 20 });
        relationMemberResults.value = res?.members || [];
    } catch { relationMemberResults.value = []; }
}

async function handleSaveRelation() {
    if (!relationForm.value.reporter_id || !relationForm.value.supervisor_id) {
        message.error("请选择汇报人和上级");
        return;
    }
    savingRelation.value = true;
    try {
        const res: any = await createReportingRelation(relationForm.value);
        if (res?.success) {
            message.success("汇报关系已创建");
            relationDialogOpen.value = false;
            await loadRelations();
        } else { message.error(res?.error || "创建失败"); }
    } catch { message.error("创建失败"); }
    finally { savingRelation.value = false; }
}

async function handleDeleteRelation(id: number) {
    try {
        const res: any = await deleteReportingRelation(id);
        if (res?.success) {
            message.success("已删除");
            await loadRelations();
        } else { message.error("删除失败"); }
    } catch { message.error("删除失败"); }
}

// ---- 头像工具 ----

const AVATAR_COLORS = [
    'bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500',
    'bg-pink-500', 'bg-teal-500', 'bg-indigo-500', 'bg-red-400',
    'bg-cyan-500', 'bg-amber-500',
];

function getInitial(name: string): string {
    if (!name) return '?';
    const trimmed = name.trim();
    const first = trimmed.charAt(0);
    return /[a-zA-Z]/.test(first) ? first.toUpperCase() : first;
}

function getAvatarColor(name: string): string {
    if (!name) return AVATAR_COLORS[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

// ---- Init ----

onMounted(() => {
    loadMyReports();
    loadSubReports();
    loadStats();
    loadTemplates();
    loadRules();
    loadRelations();
});
</script>

<template>
    <div class="space-y-4">
        <!-- 统计卡片 -->
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div class="bg-white rounded-xl p-4">
                <div class="text-sm text-gray-400">总汇报数</div>
                <div class="text-2xl font-semibold text-gray-800 mt-1">{{ stats.total }}</div>
            </div>
            <div class="bg-white rounded-xl p-4">
                <div class="text-sm text-gray-400">草稿</div>
                <div class="text-2xl font-semibold text-gray-500 mt-1">{{ stats.draft }}</div>
            </div>
            <div class="bg-white rounded-xl p-4">
                <div class="text-sm text-gray-400">已提交</div>
                <div class="text-2xl font-semibold text-blue-600 mt-1">{{ stats.submitted }}</div>
            </div>
            <div class="bg-white rounded-xl p-4">
                <div class="text-sm text-gray-400">已审阅</div>
                <div class="text-2xl font-semibold text-green-600 mt-1">{{ stats.reviewed }}</div>
            </div>
            <div class="bg-white rounded-xl p-4">
                <div class="text-sm text-gray-400">已退回</div>
                <div class="text-2xl font-semibold text-red-500 mt-1">{{ stats.rejected }}</div>
            </div>
        </div>

        <!-- 主内容区 -->
        <div class="bg-white rounded-xl p-6">
            <VortTabs v-model:activeKey="activeTab">
                <!-- 我的汇报 -->
                <VortTabPane tab-key="my" tab="我的汇报">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <VortSelect v-model="myFilterType" placeholder="全部类型" allow-clear style="width: 120px" @change="loadMyReports">
                                <VortSelectOption v-for="opt in typeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                            </VortSelect>
                            <VortSelect v-model="myFilterStatus" placeholder="全部状态" allow-clear style="width: 120px" @change="loadMyReports">
                                <VortSelectOption v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                            </VortSelect>
                        </div>
                        <div class="flex items-center gap-2">
                            <AiAssistButton prompt="我想写一份日报/周报/月报，请引导我完成。请先询问我要写哪种类型的汇报，然后帮我梳理和生成汇报内容。" />
                            <VortButton variant="primary" @click="openSubmitDialog">
                                <Plus :size="14" class="mr-1" /> 写汇报
                            </VortButton>
                        </div>
                    </div>

                    <VortSpin :spinning="loadingMy">
                        <div v-if="myReports.length" class="space-y-2">
                            <div
                                v-for="r in myReports" :key="r.id"
                                class="flex items-center justify-between px-5 py-3.5 rounded-lg border border-gray-100 hover:bg-gray-50 cursor-pointer"
                                @click="openDetail(r.id)"
                            >
                                <div class="flex items-center gap-3 min-w-0">
                                    <VortTag :color="typeColor(r.report_type)" size="small">{{ typeLabel(r.report_type) }}</VortTag>
                                    <span class="text-sm font-medium text-gray-800 truncate">{{ r.title || '无标题' }}</span>
                                    <span class="text-xs text-gray-400 flex-shrink-0">{{ r.report_date }}</span>
                                </div>
                                <div class="flex items-center gap-2 flex-shrink-0">
                                    <VortTag v-if="r.auto_generated" size="small" color="cyan">AI 生成</VortTag>
                                    <VortTag :color="statusColor(r.status)" size="small">{{ statusLabel(r.status) }}</VortTag>
                                </div>
                            </div>
                        </div>
                        <div v-else class="text-gray-400 text-sm text-center py-16">
                            暂无汇报记录，点击右上角「写汇报」开始
                        </div>
                    </VortSpin>
                </VortTabPane>

                <!-- 下属汇报 -->
                <VortTabPane tab-key="subordinate" tab="下属汇报">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-3">
                            <VortSelect v-model="subFilterStatus" placeholder="全部状态" allow-clear style="width: 120px" @change="loadSubReports">
                                <VortSelectOption v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                            </VortSelect>
                        </div>
                    </div>

                    <VortSpin :spinning="loadingSub">
                        <div v-if="subReports.length" class="space-y-2">
                            <div
                                v-for="r in subReports" :key="r.id"
                                class="flex items-center justify-between px-5 py-3.5 rounded-lg border border-gray-100 hover:bg-gray-50 cursor-pointer"
                                @click="openDetail(r.id)"
                            >
                                <div class="flex items-center gap-3 min-w-0">
                                    <VortTag :color="typeColor(r.report_type)" size="small">{{ typeLabel(r.report_type) }}</VortTag>
                                    <span class="text-sm font-medium text-gray-800 truncate">{{ r.title || '无标题' }}</span>
                                    <span class="text-xs text-gray-400 flex-shrink-0">{{ r.report_date }}</span>
                                </div>
                                <div class="flex items-center gap-2 flex-shrink-0">
                                    <VortTag :color="statusColor(r.status)" size="small">{{ statusLabel(r.status) }}</VortTag>
                                    <VortButton v-if="r.status === 'submitted'" size="small" variant="primary" @click.stop="openReviewDialog(r.id)">
                                        审阅
                                    </VortButton>
                                </div>
                            </div>
                        </div>
                        <div v-else class="text-gray-400 text-sm text-center py-16">
                            暂无下属汇报
                        </div>
                    </VortSpin>
                </VortTabPane>

                <!-- 汇报关系 -->
                <VortTabPane v-if="isAdmin" tab-key="reporting" tab="汇报关系">
                    <div class="flex items-center justify-between mb-4">
                        <h4 class="text-base font-medium text-gray-800">汇报关系</h4>
                        <div class="flex items-center gap-2">
                            <AiAssistButton prompt="我想添加一条汇报关系，请引导我完成。需要设置汇报人（下级）、上级、以及关系类型（直属/虚线/职能）。" />
                            <VortButton variant="primary" @click="openRelationDialog">
                                <Plus :size="14" class="mr-1" /> 新增
                            </VortButton>
                        </div>
                    </div>

                    <VortSpin :spinning="loadingRelations">
                        <div v-if="relations.length" class="space-y-2">
                            <div
                                v-for="r in relations" :key="r.id"
                                class="flex items-center justify-between px-5 py-3.5 rounded-lg border border-gray-100 hover:bg-gray-50"
                            >
                                <div class="flex items-center gap-3 text-sm">
                                    <span
                                        class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                                        :class="getAvatarColor(r.reporter_name)"
                                    >{{ getInitial(r.reporter_name) }}</span>
                                    <span class="font-medium text-gray-800">{{ r.reporter_name }}</span>
                                    <ArrowRight :size="14" class="text-gray-400" />
                                    <span
                                        class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                                        :class="getAvatarColor(r.supervisor_name)"
                                    >{{ getInitial(r.supervisor_name) }}</span>
                                    <span class="font-medium text-gray-800">{{ r.supervisor_name }}</span>
                                    <VortTag :color="r.relation_type === 'direct' ? 'blue' : r.relation_type === 'dotted' ? 'orange' : 'cyan'" size="small">
                                        {{ relationTypeLabel(r.relation_type) }}
                                    </VortTag>
                                    <VortTag v-if="r.is_primary" color="green" size="small">主要</VortTag>
                                </div>
                                <VortPopconfirm title="确认删除此汇报关系？" @confirm="handleDeleteRelation(r.id)">
                                    <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                </VortPopconfirm>
                            </div>
                        </div>
                        <div v-else class="text-gray-400 text-sm text-center py-16">
                            暂无汇报关系，点击右上角「新增」添加
                        </div>
                    </VortSpin>
                </VortTabPane>

                <!-- 汇报设置 -->
                <VortTabPane v-if="isAdmin" tab-key="settings" tab="汇报设置">
                    <div class="space-y-6">
                        <!-- 模板管理 -->
                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="text-sm font-medium text-gray-600">汇报模板</h4>
                                <VortButton size="small" @click="openTemplateDialog">
                                    <Plus :size="14" class="mr-1" /> 新增模板
                                </VortButton>
                            </div>
                            <VortSpin :spinning="loadingTemplates">
                                <div v-if="templates.length" class="space-y-2">
                                    <div
                                        v-for="t in templates" :key="t.id"
                                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100"
                                    >
                                        <div class="flex items-center gap-3">
                                            <FileText :size="16" class="text-gray-400" />
                                            <span class="text-sm font-medium text-gray-800">{{ t.name }}</span>
                                            <VortTag :color="typeColor(t.report_type)" size="small">{{ typeLabel(t.report_type) }}</VortTag>
                                        </div>
                                        <VortPopconfirm title="确认删除此模板？" @confirm="handleDeleteTemplate(t.id)">
                                            <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                        </VortPopconfirm>
                                    </div>
                                </div>
                                <div v-else class="text-gray-400 text-sm text-center py-8">暂无模板</div>
                            </VortSpin>
                        </div>

                        <VortDivider />

                        <!-- 规则管理 -->
                        <div>
                            <div class="flex items-center justify-between mb-3">
                                <h4 class="text-sm font-medium text-gray-600">汇报规则</h4>
                                <VortButton size="small" @click="openRuleDialog">
                                    <Plus :size="14" class="mr-1" /> 新增规则
                                </VortButton>
                            </div>
                            <VortSpin :spinning="loadingRules">
                                <div v-if="rules.length" class="space-y-2">
                                    <div
                                        v-for="r in rules" :key="r.id"
                                        class="flex items-center justify-between px-4 py-3 rounded-lg border border-gray-100"
                                    >
                                        <div class="flex items-center gap-3 text-sm">
                                            <VortTag size="small" :color="r.enabled ? 'green' : 'default'">
                                                {{ r.enabled ? '启用' : '禁用' }}
                                            </VortTag>
                                            <span class="text-gray-800">{{ r.template_name || '未知模板' }}</span>
                                            <span class="text-gray-400">{{ r.scope === 'member' ? '个人' : '部门' }}: {{ r.target_id.slice(0, 8) }}</span>
                                            <span class="text-gray-400">
                                                <Clock :size="12" class="inline mr-1" />{{ r.deadline_cron }}
                                            </span>
                                        </div>
                                        <VortPopconfirm title="确认删除此规则？" @confirm="handleDeleteRule(r.id)">
                                            <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                        </VortPopconfirm>
                                    </div>
                                </div>
                                <div v-else class="text-gray-400 text-sm text-center py-8">暂无规则</div>
                            </VortSpin>
                        </div>
                    </div>
                </VortTabPane>
            </VortTabs>
        </div>

        <!-- 汇报详情抽屉 -->
        <VortDrawer :open="detailVisible" title="汇报详情" :width="600" @update:open="detailVisible = $event">
            <template v-if="detailLoading">
                <div class="flex items-center justify-center py-16 text-gray-400">加载中...</div>
            </template>
            <template v-else-if="detailReport">
                <div class="space-y-4">
                    <div class="flex items-center gap-3">
                        <VortTag :color="typeColor(detailReport.report_type)">{{ typeLabel(detailReport.report_type) }}</VortTag>
                        <VortTag :color="statusColor(detailReport.status)">{{ statusLabel(detailReport.status) }}</VortTag>
                        <VortTag v-if="detailReport.auto_generated" color="cyan">AI 生成</VortTag>
                    </div>

                    <div>
                        <h3 class="text-lg font-medium text-gray-800">{{ detailReport.title || '无标题' }}</h3>
                        <div class="text-xs text-gray-400 mt-1">{{ detailReport.report_date }}</div>
                    </div>

                    <div class="prose prose-sm max-w-none bg-gray-50 rounded-lg p-4 whitespace-pre-wrap text-sm text-gray-700">{{ detailReport.content || '无内容' }}</div>

                    <div v-if="detailReport.reviewer_comment" class="bg-yellow-50 rounded-lg p-4">
                        <div class="text-xs text-yellow-600 font-medium mb-1">审阅批注</div>
                        <div class="text-sm text-gray-700">{{ detailReport.reviewer_comment }}</div>
                    </div>

                    <div class="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <span class="text-gray-400">提交时间</span>
                            <div class="text-gray-800 mt-0.5">{{ detailReport.submitted_at || '未提交' }}</div>
                        </div>
                        <div>
                            <span class="text-gray-400">审阅时间</span>
                            <div class="text-gray-800 mt-0.5">{{ detailReport.reviewed_at || '未审阅' }}</div>
                        </div>
                    </div>

                    <div v-if="detailReport.status === 'submitted'" class="flex justify-end gap-3 pt-4 border-t border-gray-100">
                        <VortButton @click="openReviewDialog(detailReport!.id)">
                            <XCircle :size="14" class="mr-1" /> 退回
                        </VortButton>
                        <VortButton variant="primary" @click="reviewReportId = detailReport!.id; reviewForm = { status: 'reviewed', comment: '' }; handleReview()">
                            <CheckCircle :size="14" class="mr-1" /> 通过
                        </VortButton>
                    </div>
                </div>
            </template>
        </VortDrawer>

        <!-- 写汇报弹窗 -->
        <VortDialog
            :open="submitDialogOpen"
            title="写汇报"
            :width="640"
            :ok-text="'提交'"
            :confirm-loading="submitting"
            @update:open="submitDialogOpen = $event"
            @ok="handleSubmit"
        >
            <div class="space-y-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">汇报类型</label>
                        <VortSelect v-model="submitForm.report_type" style="width: 100%">
                            <VortSelectOption value="daily">日报</VortSelectOption>
                            <VortSelectOption value="weekly">周报</VortSelectOption>
                            <VortSelectOption value="monthly">月报</VortSelectOption>
                        </VortSelect>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">汇报日期</label>
                        <VortDatePicker v-model="submitForm.report_date" value-format="YYYY-MM-DD" placeholder="默认今天" style="width: 100%" />
                    </div>
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">标题</label>
                    <VortInput v-model="submitForm.title" placeholder="留空则自动生成" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">内容（Markdown）</label>
                    <div class="space-y-2">
                        <VortTextarea v-model="submitForm.content" :rows="12" placeholder="## 今日工作&#10;&#10;## 遇到的问题&#10;&#10;## 明日计划" />
                        <div class="flex justify-end">
                            <vort-button size="small" @click="handleAiGenerateContent">
                                <Bot :size="12" class="mr-1" /> AI 助手创建
                            </vort-button>
                        </div>
                    </div>
                </div>
            </div>
        </VortDialog>

        <!-- 审阅弹窗 -->
        <VortDialog
            :open="reviewDialogOpen"
            title="审阅汇报"
            :ok-text="reviewForm.status === 'reviewed' ? '通过' : '退回'"
            :confirm-loading="reviewing"
            @update:open="reviewDialogOpen = $event"
            @ok="handleReview"
        >
            <div class="space-y-4">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">审阅结果</label>
                    <VortSelect v-model="reviewForm.status" style="width: 100%">
                        <VortSelectOption value="reviewed">通过</VortSelectOption>
                        <VortSelectOption value="rejected">退回</VortSelectOption>
                    </VortSelect>
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">批注（可选）</label>
                    <VortTextarea v-model="reviewForm.comment" :rows="4" placeholder="添加审阅批注..." />
                </div>
            </div>
        </VortDialog>

        <!-- 新增模板弹窗 -->
        <VortDialog
            :open="templateDialogOpen"
            title="新增汇报模板"
            :ok-text="'创建'"
            :confirm-loading="savingTemplate"
            @update:open="templateDialogOpen = $event"
            @ok="handleSaveTemplate"
        >
            <div class="space-y-4">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">模板名称</label>
                    <VortInput v-model="templateForm.name" placeholder="如：技术团队日报" />
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">汇报类型</label>
                    <VortSelect v-model="templateForm.report_type" style="width: 100%">
                        <VortSelectOption value="daily">日报</VortSelectOption>
                        <VortSelectOption value="weekly">周报</VortSelectOption>
                        <VortSelectOption value="monthly">月报</VortSelectOption>
                    </VortSelect>
                </div>
            </div>
        </VortDialog>

        <!-- 新增汇报关系弹窗 -->
        <VortDialog
            :open="relationDialogOpen"
            title="新增汇报关系"
            :ok-text="'创建'"
            :confirm-loading="savingRelation"
            @update:open="relationDialogOpen = $event"
            @ok="handleSaveRelation"
        >
            <div class="space-y-4">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">搜索成员</label>
                    <VortInputSearch
                        v-model="relationMemberSearch"
                        placeholder="输入姓名搜索"
                        @search="searchRelationMembers"
                        @press-enter="searchRelationMembers"
                    />
                </div>
                <div v-if="relationMemberResults.length" class="max-h-40 overflow-y-auto border border-gray-100 rounded-lg p-2 space-y-1">
                    <div
                        v-for="m in relationMemberResults" :key="m.id"
                        class="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 text-sm"
                    >
                        <span class="font-medium text-gray-800">{{ m.name }}</span>
                        <div class="flex items-center gap-1">
                            <VortButton size="small" @click="relationForm.reporter_id = m.id; message.info(`已选为汇报人: ${m.name}`)">
                                设为汇报人
                            </VortButton>
                            <VortButton size="small" @click="relationForm.supervisor_id = m.id; message.info(`已选为上级: ${m.name}`)">
                                设为上级
                            </VortButton>
                        </div>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">汇报人（下级）</label>
                        <div class="text-sm text-gray-800 px-3 py-2 bg-gray-50 rounded-lg min-h-[36px]">
                            {{ relationMemberResults.find(m => m.id === relationForm.reporter_id)?.name || '未选择' }}
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs text-gray-500 mb-1">上级</label>
                        <div class="text-sm text-gray-800 px-3 py-2 bg-gray-50 rounded-lg min-h-[36px]">
                            {{ relationMemberResults.find(m => m.id === relationForm.supervisor_id)?.name || '未选择' }}
                        </div>
                    </div>
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">关系类型</label>
                    <VortSelect v-model="relationForm.relation_type" style="width: 100%">
                        <VortSelectOption v-for="opt in relationTypeOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</VortSelectOption>
                    </VortSelect>
                </div>
            </div>
        </VortDialog>

        <!-- 新增规则弹窗 -->
        <VortDialog
            :open="ruleDialogOpen"
            title="新增汇报规则"
            :ok-text="'创建'"
            :confirm-loading="savingRule"
            @update:open="ruleDialogOpen = $event"
            @ok="handleSaveRule"
        >
            <div class="space-y-4">
                <div>
                    <label class="block text-xs text-gray-500 mb-1">汇报模板</label>
                    <VortSelect v-model="ruleForm.template_id" placeholder="请选择模板" style="width: 100%">
                        <VortSelectOption v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</VortSelectOption>
                    </VortSelect>
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">搜索成员</label>
                    <VortInputSearch
                        v-model="ruleMemberSearch"
                        placeholder="输入姓名搜索"
                        @search="searchRuleMembers"
                        @press-enter="searchRuleMembers"
                    />
                    <div v-if="ruleMemberResults.length" class="mt-2 max-h-32 overflow-y-auto border border-gray-100 rounded-lg p-2 space-y-1">
                        <div
                            v-for="m in ruleMemberResults" :key="m.id"
                            class="flex items-center justify-between px-3 py-1.5 rounded hover:bg-gray-50 text-sm cursor-pointer"
                        >
                            <span>{{ m.name }}</span>
                            <div class="flex gap-1">
                                <VortButton size="small" @click="ruleForm.target_id = m.id; message.info(`汇报人: ${m.name}`)">汇报人</VortButton>
                                <VortButton size="small" @click="ruleForm.reviewer_id = m.id; message.info(`审阅人: ${m.name}`)">审阅人</VortButton>
                            </div>
                        </div>
                    </div>
                </div>
                <div>
                    <label class="block text-xs text-gray-500 mb-1">截止时间 (cron)</label>
                    <VortInput v-model="ruleForm.deadline_cron" placeholder="0 18 * * 1-5 (工作日18点)" />
                </div>
            </div>
        </VortDialog>
    </div>
</template>
