<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
    Plus, Search, ChevronRight, ChevronDown, FolderOpen, Folder,
    Ellipsis, CheckCircle, XCircle, AlertCircle, SkipForward, Bug, ChevronsUpDown,
    ExternalLink, GitPullRequest, Trash2, Bot, MessageSquare, History, Loader2,
    FileText, Copy, MoreHorizontal, ArrowUpDown, Check, Filter,
} from "lucide-vue-next";
import { message, Dropdown, DropdownMenuItem, Dialog } from "@openvort/vort-ui";
import MarkdownView from "@/components/vort-biz/editor/MarkdownView.vue";
import { useVortFlowStore } from "@/stores";
import { useWorkItemCommon } from "./work-item/useWorkItemCommon";
import WorkItemCreate from "./work-item/WorkItemCreate.vue";
import TestPlanEditDialog from "./components/TestPlanEditDialog.vue";
import TestPlanAddCasesDialog from "./components/TestPlanAddCasesDialog.vue";
import TestPlanAddPRDialog from "./components/TestPlanAddPRDialog.vue";
import TestCaseDetailDrawer from "./components/TestCaseDetailDrawer.vue";
import WorkItemMemberPicker from "@/components/vort-biz/work-item/WorkItemMemberPicker.vue";
import {
    getVortflowTestPlan,
    getVortflowTestPlanCases,
    removeVortflowTestPlanCase,
    addVortflowTestPlanExecution,
    updateVortflowTestPlan,
    getVortflowTestModules,
    getVortflowIterations,
    getVortflowVersions,
    createVortflowBug,
    createVortflowTestCaseLink,
    getVortflowTestPlans,
    getVortflowTestPlanReviews,
    updateVortflowTestPlanReview,
    removeVortflowTestPlanReview,
    getVortflowReviewHistory,
    triggerVortflowAiReview,
    getVortflowTestReports,
    createVortflowTestReport,
    deleteVortflowTestReport,
} from "@/api";
import type { NewBugForm } from "@/components/vort-biz/work-item/WorkItemTable.types";

const route = useRoute();
const router = useRouter();
const vortFlowStore = useVortFlowStore();
const {
    getAvatarBg, getAvatarLabel, getMemberAvatarUrl,
    loadMemberOptions, getMemberIdByName, getMemberNameById,
    ownerGroups,
} = useWorkItemCommon();

const planId = computed(() => route.params.id as string);
const plan = ref<any>({});
const planLoading = ref(true);
const validTabs = ["cases", "reviews", "report"];
const activeTab = ref(validTabs.includes(route.query.tab as string) ? (route.query.tab as string) : "cases");

watch(activeTab, (tab) => {
    router.replace({ query: { ...route.query, tab } });
});

const statusLabels: Record<string, string> = {
    planning: "待开始",
    in_progress: "进行中",
    completed: "已完成",
    suspended: "已挂起",
};
const statusColorMap: Record<string, string> = {
    in_progress: "processing",
    completed: "green",
    suspended: "default",
    planning: "default",
};

const caseTypeLabels: Record<string, string> = {
    functional: "功能测试",
    performance: "性能测试",
    api: "接口测试",
    ui: "UI 测试",
    security: "安全测试",
};
const priorityLabels: Record<number, string> = { 0: "P0", 1: "P1", 2: "P2", 3: "P3" };
const priorityColors: Record<number, string> = { 0: "red", 1: "red", 2: "orange", 3: "default" };

const resultIcons: Record<string, { icon: any; color: string; label: string }> = {
    passed: { icon: CheckCircle, color: "text-green-500", label: "通过" },
    blocked: { icon: AlertCircle, color: "text-orange-400", label: "受阻" },
    failed: { icon: XCircle, color: "text-red-500", label: "失败" },
    skipped: { icon: SkipForward, color: "text-blue-400", label: "跳过" },
};
const resultOptions = [
    { value: "passed", label: "通过", color: "text-green-500", icon: CheckCircle },
    { value: "blocked", label: "受阻", color: "text-orange-400", icon: AlertCircle },
    { value: "failed", label: "失败", color: "text-red-500", icon: XCircle },
    { value: "skipped", label: "跳过", color: "text-blue-400", icon: SkipForward },
];

// ============ Load Plan ============

const loadPlan = async () => {
    planLoading.value = true;
    try {
        const res = await getVortflowTestPlan(planId.value);
        if ((res as any).error) {
            message.error((res as any).error);
            return;
        }
        plan.value = res;
    } finally {
        planLoading.value = false;
    }
};

// ============ Plan Switcher ============

const planSwitcherOpen = ref(false);
const planSwitcherSearch = ref("");
const planSwitcherList = ref<{ id: string; title: string; status: string }[]>([]);

const filteredPlanList = computed(() => {
    const kw = planSwitcherSearch.value.trim().toLowerCase();
    if (!kw) return planSwitcherList.value;
    return planSwitcherList.value.filter(p => p.title.toLowerCase().includes(kw));
});

const loadPlanSwitcherList = async () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    const res = await getVortflowTestPlans({ project_id: projectId, page_size: 100 });
    planSwitcherList.value = ((res as any).items || []).map((p: any) => ({
        id: p.id, title: p.title, status: p.status,
    }));
};

const handleSwitchPlan = (id: string) => {
    planSwitcherOpen.value = false;
    planSwitcherSearch.value = "";
    if (id !== planId.value) {
        router.push(`/vortflow/test-plans/${id}`);
    }
};

// ============ Module Tree ============

interface RawModule {
    id: string;
    name: string;
    parent_id: string | null;
}

interface FlatNode {
    id: string;
    name: string;
    parent_id: string | null;
    depth: number;
    hasChildren: boolean;
    expanded: boolean;
}

const rawModules = ref<RawModule[]>([]);
const expandedModuleIds = ref<Set<string>>(new Set());
const selectedModuleId = ref("");
const moduleSearch = ref("");
const showModuleSearch = ref(false);

const EXPAND_STORAGE_KEY = "vortflow_test_module_expanded";

const saveExpandedState = () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    try {
        const all = JSON.parse(localStorage.getItem(EXPAND_STORAGE_KEY) || "{}");
        all[projectId] = [...expandedModuleIds.value];
        localStorage.setItem(EXPAND_STORAGE_KEY, JSON.stringify(all));
    } catch { /* ignore */ }
};

const loadExpandedState = (): Set<string> | null => {
    const projectId = plan.value?.project_id;
    if (!projectId) return null;
    try {
        const all = JSON.parse(localStorage.getItem(EXPAND_STORAGE_KEY) || "{}");
        const ids = all[projectId];
        if (Array.isArray(ids)) return new Set(ids);
    } catch { /* ignore */ }
    return null;
};

const flatNodes = computed<FlatNode[]>(() => {
    const map = new Map<string, RawModule>();
    const childMap = new Map<string, string[]>();
    for (const m of rawModules.value) {
        map.set(m.id, m);
        const pid = m.parent_id || "__root__";
        if (!childMap.has(pid)) childMap.set(pid, []);
        childMap.get(pid)!.push(m.id);
    }
    const kw = moduleSearch.value.trim().toLowerCase();
    const matchesSearch = (id: string): boolean => {
        if (!kw) return true;
        const mod = map.get(id);
        if (!mod) return false;
        if (mod.name.toLowerCase().includes(kw)) return true;
        return (childMap.get(id) || []).some((cid) => matchesSearch(cid));
    };
    const result: FlatNode[] = [];
    const walk = (parentId: string, depth: number) => {
        const children = childMap.get(parentId) || [];
        for (const id of children) {
            if (!matchesSearch(id)) continue;
            const mod = map.get(id)!;
            const hasChildren = (childMap.get(id) || []).length > 0;
            const expanded = kw ? true : expandedModuleIds.value.has(id);
            result.push({ id: mod.id, name: mod.name, parent_id: mod.parent_id, depth, hasChildren, expanded });
            if (expanded && hasChildren) walk(id, depth + 1);
        }
    };
    walk("__root__", 0);
    return result;
});

const loadModules = async () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    try {
        const res = await getVortflowTestModules({ project_id: projectId });
        rawModules.value = (res as any)?.items || [];
        const saved = loadExpandedState();
        if (saved) {
            const validIds = new Set(rawModules.value.map((m) => m.id));
            expandedModuleIds.value = new Set([...saved].filter((id) => validIds.has(id)));
        } else {
            expandedModuleIds.value = new Set();
        }
    } catch {
        rawModules.value = [];
    }
};

const toggleModuleExpand = (id: string) => {
    const next = new Set(expandedModuleIds.value);
    if (next.has(id)) next.delete(id); else next.add(id);
    expandedModuleIds.value = next;
    saveExpandedState();
};

const selectModule = (id: string) => {
    selectedModuleId.value = selectedModuleId.value === id ? "" : id;
    loadCases();
};

// ============ Module Case Counts ============

const moduleCaseCounts = ref<Map<string, number>>(new Map());

const loadModuleCaseCounts = async () => {
    try {
        const res = await getVortflowTestPlanCases(planId.value, {});
        const items: any[] = (res as any).items || [];
        const counts = new Map<string, number>();
        for (const c of items) {
            if (c.module_id) counts.set(c.module_id, (counts.get(c.module_id) || 0) + 1);
        }
        moduleCaseCounts.value = counts;
    } catch { /* ignore */ }
};

const moduleAggCounts = computed(() => {
    const direct = moduleCaseCounts.value;
    const childMap = new Map<string, string[]>();
    for (const m of rawModules.value) {
        const pid = m.parent_id || "__root__";
        if (!childMap.has(pid)) childMap.set(pid, []);
        childMap.get(pid)!.push(m.id);
    }
    const result = new Map<string, number>();
    const calc = (id: string): number => {
        if (result.has(id)) return result.get(id)!;
        let count = direct.get(id) || 0;
        for (const cid of (childMap.get(id) || [])) count += calc(cid);
        result.set(id, count);
        return count;
    };
    for (const m of rawModules.value) calc(m.id);
    return result;
});

// ============ Plan Cases ============

const cases = ref<any[]>([]);
const casesLoading = ref(false);
const casesTotal = ref(0);
const caseKeyword = ref("");
const caseSortOpen = ref(false);

const SORT_STORAGE_KEY = "vortflow_test_plan_case_sort";

const loadSavedSort = (): string => {
    try {
        return localStorage.getItem(SORT_STORAGE_KEY) || "priority";
    } catch { return "priority"; }
};

const caseSortBy = ref(loadSavedSort());

const sortOptions = [
    { value: "", label: "默认排序" },
    { value: "id", label: "编号" },
    { value: "priority", label: "优先级" },
    { value: "created_at", label: "创建时间" },
    { value: "updated_at", label: "更新时间" },
];

const currentSortLabel = computed(() => sortOptions.find(o => o.value === caseSortBy.value)?.label || "默认排序");

const handleSortChange = (value: string) => {
    caseSortBy.value = value;
    caseSortOpen.value = false;
    try { localStorage.setItem(SORT_STORAGE_KEY, value); } catch { /* ignore */ }
    loadCases();
};

const caseFilterOpen = ref(false);
const caseFilterType = ref("");
const caseFilterPriority = ref("");

const caseFilterCount = computed(() => {
    let count = 0;
    if (caseFilterType.value) count++;
    if (caseFilterPriority.value) count++;
    return count;
});

const handleApplyFilter = () => {
    caseFilterOpen.value = false;
    loadCases();
};

const handleResetFilter = () => {
    caseFilterType.value = "";
    caseFilterPriority.value = "";
    caseFilterOpen.value = false;
    loadCases();
};

const loadCases = async () => {
    casesLoading.value = true;
    try {
        const res = await getVortflowTestPlanCases(planId.value, {
            module_id: selectedModuleId.value || undefined,
            keyword: caseKeyword.value || undefined,
            sort_by: caseSortBy.value || undefined,
            case_type: caseFilterType.value || undefined,
            priority: caseFilterPriority.value ? parseInt(caseFilterPriority.value) : undefined,
        });
        cases.value = (res as any).items || [];
        casesTotal.value = (res as any).total || 0;
    } finally {
        casesLoading.value = false;
    }
};

const handleRemoveCase = async (planCaseId: string) => {
    await removeVortflowTestPlanCase(planId.value, planCaseId);
    message.success("已移除");
    loadCases();
    loadModuleCaseCounts();
    loadPlan();
};

// ============ Execution Result ============

const executionDropdownOpen = ref<Record<string, boolean>>({});

const handleAddExecution = async (planCaseId: string, result: string) => {
    await addVortflowTestPlanExecution(planId.value, planCaseId, { result });
    executionDropdownOpen.value[planCaseId] = false;
    loadCases();
    loadPlan();
};

const latestResultDisplay = (item: any) => {
    if (!item.latest_result) return null;
    return resultIcons[item.latest_result] || null;
};

// ============ Result distribution bar ============

const resultBarStyle = computed(() => {
    const t = plan.value?.total_cases || 0;
    if (!t) return { passed: "0%", failed: "0%", blocked: "0%", rest: "0%" };
    const p = plan.value;
    return {
        passed: `${(p.passed / t) * 100}%`,
        failed: `${(p.failed / t) * 100}%`,
        blocked: `${(p.blocked / t) * 100}%`,
        rest: `${(((t - p.passed - p.failed - p.blocked)) / t) * 100}%`,
    };
});

const resultPercent = computed(() => {
    const t = plan.value?.total_cases || 0;
    if (!t) return "0%";
    return `${Math.round(((plan.value?.executed_cases || 0) / t) * 100)}%`;
});

const resultDistDetail = computed(() => {
    const t = plan.value?.total_cases || 0;
    const pct = (n: number) => t ? `${((n / t) * 100).toFixed(2)}%` : "0%";
    const p = plan.value || {};
    const passed = p.passed || 0;
    const blocked = p.blocked || 0;
    const failed = p.failed || 0;
    const skipped = p.skipped || 0;
    const unexecuted = Math.max(0, t - passed - blocked - failed - skipped);
    return [
        { label: "通过", count: passed, pct: pct(passed), color: "text-green-500", bg: "bg-green-500", icon: CheckCircle },
        { label: "受阻", count: blocked, pct: pct(blocked), color: "text-orange-400", bg: "bg-orange-400", icon: AlertCircle },
        { label: "失败", count: failed, pct: pct(failed), color: "text-red-500", bg: "bg-red-500", icon: XCircle },
        { label: "跳过", count: skipped, pct: pct(skipped), color: "text-blue-400", bg: "bg-blue-400", icon: SkipForward },
        { label: "未执行", count: unexecuted, pct: pct(unexecuted), color: "text-gray-400", bg: "bg-gray-300", icon: null },
    ];
});

// ============ Edit dialog ============

const editDialogOpen = ref(false);
const editData = ref<any>(null);

const handleEditPlan = () => {
    editData.value = { ...plan.value };
    editDialogOpen.value = true;
};

const handleFinishPlan = async () => {
    await updateVortflowTestPlan(planId.value, { status: "completed" });
    message.success("已结束计划");
    loadPlan();
};

// ============ Case Detail Drawer ============

const caseDetailDrawerOpen = ref(false);
const caseDetailId = ref("");

const handleViewCase = (row: any) => {
    caseDetailId.value = row.test_case_id;
    caseDetailDrawerOpen.value = true;
};

// ============ Add Cases Dialog ============

const addCasesDialogOpen = ref(false);

const handleAddCasesSaved = () => {
    loadCases();
    loadModuleCaseCounts();
    loadPlan();
};

// ============ File Bug ============

const fileBugDrawerOpen = ref(false);
const fileBugCaseRow = ref<any>(null);
const createWorkItemRef = ref<InstanceType<typeof WorkItemCreate> | null>(null);

const handleOpenFileBug = (row: any) => {
    fileBugCaseRow.value = row;
    fileBugDrawerOpen.value = true;
};

const handleSubmitFileBug = async () => {
    const formData = createWorkItemRef.value?.submit() as NewBugForm | null;
    if (!formData) return;
    const title = formData.title.trim();
    if (!title) { message.warning("请填写标题"); return; }
    try {
        const ownerId = getMemberIdByName(formData.owner) || undefined;
        const createdBug: any = await createVortflowBug({
            project_id: plan.value?.project_id || undefined,
            title,
            description: formData.description || "",
            severity: formData.priority === "urgent" ? 1 : formData.priority === "high" ? 2 : formData.priority === "medium" ? 3 : 4,
            assignee_id: ownerId,
            tags: [...formData.tags],
            collaborators: [...formData.collaborators],
        });
        const bugId = createdBug?.id;
        const testCaseId = fileBugCaseRow.value?.test_case_id;
        if (bugId && testCaseId) {
            try {
                await createVortflowTestCaseLink({
                    test_case_id: testCaseId,
                    entity_type: "bug",
                    entity_id: String(bugId),
                });
            } catch { /* link failed silently */ }
        }
        message.success("缺陷已创建并关联测试用例");
        fileBugDrawerOpen.value = false;
        fileBugCaseRow.value = null;
    } catch (e: any) {
        message.error(e?.message || "创建失败");
    }
};

const handleCancelFileBug = () => {
    fileBugDrawerOpen.value = false;
    fileBugCaseRow.value = null;
};

// ============ Code Reviews ============

const reviews = ref<any[]>([]);
const reviewsLoading = ref(false);
const addPRDialogOpen = ref(false);

const reviewStatusLabels: Record<string, string> = {
    pending: "待评审",
    approved: "已通过",
    rejected: "已驳回",
    changes_requested: "需修改",
};
const reviewStatusColors: Record<string, string> = {
    pending: "default",
    approved: "green",
    rejected: "red",
    changes_requested: "orange",
};

const loadReviews = async () => {
    reviewsLoading.value = true;
    try {
        const res = await getVortflowTestPlanReviews(planId.value) as any;
        reviews.value = res.items || [];
    } finally {
        reviewsLoading.value = false;
    }
};

// --- Review status change with notes dialog ---
const reviewNotesDialogOpen = ref(false);
const reviewNotesTarget = ref<{ review: any; status: string } | null>(null);
const reviewNotesText = ref("");
const reviewNotesSubmitting = ref(false);

const handleReviewStatusClick = (review: any, status: string) => {
    if (status === "approved") {
        doUpdateReviewStatus(review, status, "");
    } else {
        reviewNotesTarget.value = { review, status };
        reviewNotesText.value = "";
        reviewNotesDialogOpen.value = true;
    }
};

const handleReviewNotesSubmit = async () => {
    if (!reviewNotesTarget.value) return;
    const { review, status } = reviewNotesTarget.value;
    if (!reviewNotesText.value.trim()) {
        message.warning("请填写评审意见");
        return;
    }
    reviewNotesSubmitting.value = true;
    try {
        await doUpdateReviewStatus(review, status, reviewNotesText.value.trim());
        reviewNotesDialogOpen.value = false;
    } finally {
        reviewNotesSubmitting.value = false;
    }
};

const doUpdateReviewStatus = async (review: any, status: string, notes: string) => {
    try {
        const data: any = { review_status: status };
        if (notes) data.review_notes = notes;
        await updateVortflowTestPlanReview(planId.value, review.id, data);
        await loadReviews();
        await loadPlan();
    } catch {
        message.error("更新失败");
    }
};

// --- Reviewer picker ---
const reviewerPickerOpenMap = ref<Record<string, boolean>>({});

const handleAssignReviewer = async (review: any, memberName: string) => {
    const memberId = getMemberIdByName(memberName);
    if (!memberId && memberName) return;
    try {
        await updateVortflowTestPlanReview(planId.value, review.id, { reviewer_id: memberId || null });
        await loadReviews();
    } catch {
        message.error("指定失败");
    }
};

const handleRemoveReview = async (reviewId: string) => {
    try {
        await removeVortflowTestPlanReview(planId.value, reviewId);
        message.success("已移除");
        await loadReviews();
        await loadPlan();
    } catch {
        message.error("移除失败");
    }
};

const handleAddPRSaved = () => {
    loadReviews();
    loadPlan();
};

// --- Review detail drawer ---
const reviewDetailDrawerOpen = ref(false);
const reviewDetailTarget = ref<any>(null);

const handleShowReviewNotes = (row: any) => {
    reviewDetailTarget.value = row;
    reviewDetailDrawerOpen.value = true;
};

// --- Review history ---
const historyDialogOpen = ref(false);
const historyTarget = ref<any>(null);
const historyItems = ref<any[]>([]);
const historyLoading = ref(false);

const handleShowHistory = async (review: any) => {
    historyTarget.value = review;
    historyDialogOpen.value = true;
    historyLoading.value = true;
    try {
        const res = await getVortflowReviewHistory(planId.value, review.id) as any;
        historyItems.value = res.items || [];
    } finally {
        historyLoading.value = false;
    }
};

// --- AI review ---
const aiReviewLoadingMap = ref<Record<string, boolean>>({});

const handleAiReview = async (review: any) => {
    aiReviewLoadingMap.value[review.id] = true;
    try {
        await triggerVortflowAiReview(planId.value, review.id);
        message.success("AI 评审完成");
        await loadReviews();
        await loadPlan();
    } catch {
        message.error("AI 评审失败");
    } finally {
        aiReviewLoadingMap.value[review.id] = false;
    }
};

// ============ Test Reports ============

const reports = ref<any[]>([]);
const reportsLoading = ref(false);
const reportsTotal = ref(0);
const reportGenerating = ref(false);

const loadReports = async () => {
    reportsLoading.value = true;
    try {
        const res = await getVortflowTestReports({ plan_id: planId.value }) as any;
        reports.value = res.items || [];
        reportsTotal.value = res.total || 0;
    } finally {
        reportsLoading.value = false;
    }
};

const handleGenerateReport = async () => {
    reportGenerating.value = true;
    try {
        const res = await createVortflowTestReport({ plan_id: planId.value }) as any;
        if (res?.error) {
            message.error(res.error);
            return;
        }
        message.success("报告已生成");
        await loadReports();
    } catch {
        message.error("生成失败");
    } finally {
        reportGenerating.value = false;
    }
};

const handleDeleteReport = async (reportId: string) => {
    try {
        await deleteVortflowTestReport(reportId);
        message.success("已删除");
        await loadReports();
    } catch {
        message.error("删除失败");
    }
};

const handleViewReport = (reportId: string) => {
    router.push(`/vortflow/test-reports/${reportId}`);
};

const handleCopyReportLink = (reportId: string) => {
    const url = `${window.location.origin}/vortflow/test-reports/${reportId}`;
    navigator.clipboard.writeText(url).then(() => {
        message.success("链接已复制");
    }).catch(() => {
        message.warning("复制失败，请手动复制");
    });
};

// ============ Link Iteration / Version ============

const iterationOptions = ref<{ id: string; name: string; status?: string }[]>([]);
const versionOptions = ref<{ id: string; name: string; stage?: string }[]>([]);
const iterLinkOpen = ref(false);
const verLinkOpen = ref(false);
const iterLinkSearch = ref("");
const verLinkSearch = ref("");

const filteredIterations = computed(() => {
    const kw = iterLinkSearch.value.trim().toLowerCase();
    if (!kw) return iterationOptions.value;
    return iterationOptions.value.filter(i => i.name.toLowerCase().includes(kw));
});

const filteredVersions = computed(() => {
    const kw = verLinkSearch.value.trim().toLowerCase();
    if (!kw) return versionOptions.value;
    return versionOptions.value.filter(v => v.name.toLowerCase().includes(kw));
});

const loadLinkOptions = async () => {
    const projectId = plan.value?.project_id;
    if (!projectId) return;
    const [iterRes, verRes] = await Promise.all([
        getVortflowIterations({ project_id: projectId, page_size: 100 }),
        getVortflowVersions({ project_id: projectId, page_size: 100 }),
    ]);
    iterationOptions.value = ((iterRes as any).items || []).map((i: any) => ({ id: i.id, name: i.name, status: i.status }));
    versionOptions.value = ((verRes as any).items || []).map((v: any) => ({ id: v.id, name: v.name, stage: v.stage }));
};

const handleLinkIteration = async (iterationId: string | null) => {
    await updateVortflowTestPlan(planId.value, { iteration_id: iterationId || "" });
    iterLinkOpen.value = false;
    iterLinkSearch.value = "";
    loadPlan();
};

const handleLinkVersion = async (versionId: string | null) => {
    await updateVortflowTestPlan(planId.value, { version_id: versionId || "" });
    verLinkOpen.value = false;
    verLinkSearch.value = "";
    loadPlan();
};

const iterStatusLabels: Record<string, string> = { planning: "待开始", active: "进行中", completed: "已结束" };
const verStageLabels: Record<string, string> = { dev: "开发环境", staging: "预发布", production: "生产环境", archived: "已归档" };

// ============ Init ============

onMounted(async () => {
    await loadMemberOptions();
    await loadPlan();
    await Promise.all([loadModules(), loadCases(), loadModuleCaseCounts(), loadReviews(), loadReports(), loadLinkOptions(), loadPlanSwitcherList()]);
});

watch(planId, async () => {
    await loadPlan();
    await Promise.all([loadModules(), loadCases(), loadModuleCaseCounts(), loadReviews()]);
});
</script>

<template>
    <div class="space-y-4">
        <!-- Header -->
        <div class="bg-white rounded-xl p-6">
            <vort-spin :spinning="planLoading">
                <div class="flex items-start justify-between mb-3">
                    <Dropdown v-model:open="planSwitcherOpen" trigger="click">
                        <h2 class="text-lg font-semibold text-gray-800 inline-flex items-center gap-1 cursor-pointer hover:text-blue-600 transition-colors">
                            {{ plan.title }}
                            <ChevronsUpDown :size="16" class="text-gray-400" />
                        </h2>
                        <template #overlay>
                            <div class="p-2 w-[280px]">
                                <vort-input-search
                                    v-model="planSwitcherSearch"
                                    placeholder="搜索测试计划..."
                                    allow-clear
                                    size="small"
                                    class="mb-2"
                                />
                                <div class="max-h-[300px] overflow-y-auto">
                                    <div
                                        v-for="item in filteredPlanList"
                                        :key="item.id"
                                        class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 flex items-center justify-between"
                                        :class="item.id === planId ? 'bg-blue-50 text-blue-600 font-medium' : 'text-gray-700'"
                                        @click="handleSwitchPlan(item.id)"
                                    >
                                        <span class="truncate mr-2">{{ item.title }}</span>
                                        <vort-tag :color="statusColorMap[item.status] || 'default'" size="small">
                                            {{ statusLabels[item.status] || item.status }}
                                        </vort-tag>
                                    </div>
                                    <div v-if="!filteredPlanList.length" class="px-3 py-4 text-sm text-gray-400 text-center">
                                        无匹配项
                                    </div>
                                </div>
                            </div>
                        </template>
                    </Dropdown>
                    <div class="flex items-center gap-2">
                        <vort-button v-if="plan.status !== 'completed'" @click="handleFinishPlan">结束测试计划</vort-button>
                        <Dropdown trigger="click" placement="bottomRight">
                            <a class="text-gray-400 hover:text-gray-600 cursor-pointer inline-flex items-center justify-center w-8 h-8 rounded-md hover:bg-gray-50">
                                <Ellipsis :size="16" />
                            </a>
                            <template #overlay>
                                <DropdownMenuItem @click="handleEditPlan">编辑</DropdownMenuItem>
                            </template>
                        </Dropdown>
                    </div>
                </div>

                <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-gray-500">
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">状态:</span>
                        <vort-tag :color="statusColorMap[plan.status] || 'default'">
                            {{ statusLabels[plan.status] || plan.status }}
                        </vort-tag>
                    </div>
                    <div v-if="plan.owner_name" class="flex items-center gap-1.5">
                        <span class="text-gray-400">负责人:</span>
                        <span
                            class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                            :style="{ backgroundColor: getAvatarBg(plan.owner_name) }"
                        >
                            <img
                                v-if="getMemberAvatarUrl(plan.owner_name)"
                                :src="getMemberAvatarUrl(plan.owner_name)"
                                class="w-full h-full object-cover"
                            >
                            <template v-else>{{ getAvatarLabel(plan.owner_name) }}</template>
                        </span>
                        <span>{{ plan.owner_name }}</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">已测:</span>
                        <span>{{ plan.executed_cases || 0 }} / {{ plan.total_cases || 0 }}</span>
                    </div>
                    <div class="flex items-center gap-1.5 min-w-[200px]">
                        <span class="text-gray-400">最新结果分布:</span>
                        <vort-tooltip>
                            <div class="flex items-center gap-2 cursor-default">
                                <div class="h-2 bg-gray-100 rounded-full overflow-hidden flex w-[160px]">
                                    <div class="h-full bg-green-500" :style="{ width: resultBarStyle.passed }" />
                                    <div class="h-full bg-red-500" :style="{ width: resultBarStyle.failed }" />
                                    <div class="h-full bg-orange-400" :style="{ width: resultBarStyle.blocked }" />
                                </div>
                                <span class="text-xs text-gray-400">{{ resultPercent }}</span>
                            </div>
                            <template #title>
                                <div class="space-y-1.5 text-sm whitespace-nowrap">
                                    <div v-for="item in resultDistDetail" :key="item.label" class="flex items-center gap-2">
                                        <component v-if="item.icon" :is="item.icon" :size="14" :class="item.color" />
                                        <span v-else class="w-3.5 h-3.5 rounded-full inline-flex items-center justify-center shrink-0">
                                            <span class="w-2 h-2 rounded-full bg-gray-300 inline-block" />
                                        </span>
                                        <span>{{ item.label }}: {{ item.count }} ({{ item.pct }})</span>
                                    </div>
                                </div>
                            </template>
                        </vort-tooltip>
                    </div>
                    <div v-if="plan.review_total > 0" class="flex items-center gap-1.5">
                        <span class="text-gray-400">评审通过:</span>
                        <span :class="plan.review_approved === plan.review_total ? 'text-green-600' : ''">
                            {{ plan.review_approved || 0 }} / {{ plan.review_total }}
                        </span>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">关联迭代:</span>
                        <Dropdown v-model:open="iterLinkOpen" trigger="click">
                            <span class="text-blue-600 cursor-pointer hover:underline" v-if="plan.iteration_name">{{ plan.iteration_name }}</span>
                            <span v-else class="text-gray-500 cursor-pointer hover:text-blue-600">点击关联</span>
                            <template #overlay>
                                <div class="p-2 w-[240px]">
                                    <vort-input-search
                                        v-model="iterLinkSearch"
                                        placeholder="搜索..."
                                        allow-clear
                                        size="small"
                                        class="mb-2"
                                    />
                                    <div class="max-h-[240px] overflow-y-auto">
                                        <div
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 font-medium text-gray-700"
                                            @click="handleLinkIteration(null)"
                                        >
                                            无关联迭代
                                        </div>
                                        <div
                                            v-for="opt in filteredIterations"
                                            :key="opt.id"
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 flex items-center justify-between"
                                            :class="plan.iteration_id === opt.id ? 'bg-blue-50 text-blue-600' : 'text-gray-700'"
                                            @click="handleLinkIteration(opt.id)"
                                        >
                                            <span>{{ opt.name }}</span>
                                            <vort-tag v-if="opt.status" size="small" :color="opt.status === 'active' ? 'processing' : 'default'">
                                                {{ iterStatusLabels[opt.status] || opt.status }}
                                            </vort-tag>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Dropdown>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <span class="text-gray-400">关联版本:</span>
                        <Dropdown v-model:open="verLinkOpen" trigger="click">
                            <span class="text-blue-600 cursor-pointer hover:underline" v-if="plan.version_name">{{ plan.version_name }}</span>
                            <span v-else class="text-gray-500 cursor-pointer hover:text-blue-600">点击关联</span>
                            <template #overlay>
                                <div class="p-2 w-[240px]">
                                    <vort-input-search
                                        v-model="verLinkSearch"
                                        placeholder="搜索..."
                                        allow-clear
                                        size="small"
                                        class="mb-2"
                                    />
                                    <div class="max-h-[240px] overflow-y-auto">
                                        <div
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 font-medium text-gray-700"
                                            @click="handleLinkVersion(null)"
                                        >
                                            无关联版本
                                        </div>
                                        <div
                                            v-for="opt in filteredVersions"
                                            :key="opt.id"
                                            class="px-3 py-2 text-sm cursor-pointer rounded hover:bg-gray-50 flex items-center justify-between"
                                            :class="plan.version_id === opt.id ? 'bg-blue-50 text-blue-600' : 'text-gray-700'"
                                            @click="handleLinkVersion(opt.id)"
                                        >
                                            <span>{{ opt.name }}</span>
                                            <vort-tag v-if="opt.stage" size="small">
                                                {{ verStageLabels[opt.stage] || opt.stage }}
                                            </vort-tag>
                                        </div>
                                    </div>
                                </div>
                            </template>
                        </Dropdown>
                    </div>
                </div>

                <div v-if="plan.start_date" class="mt-2 text-sm text-gray-400">
                    计划时间: {{ plan.start_date }} ~ {{ plan.end_date || "" }}
                </div>
            </vort-spin>
        </div>

        <!-- Tabs -->
        <div class="bg-white rounded-xl">
            <vort-tabs v-model:activeKey="activeTab" class="px-6 pt-2">
                <vort-tab-pane tab-key="cases" tab="执行用例" />
                <vort-tab-pane tab-key="reviews">
                    <template #tab>代码评审 <span v-if="plan.review_total" class="text-blue-500 ml-0.5">{{ plan.review_total }}</span></template>
                </vort-tab-pane>
                <vort-tab-pane tab-key="report">
                    <template #tab>测试报告 <span v-if="reportsTotal" class="text-blue-500 ml-0.5">{{ reportsTotal }}</span></template>
                </vort-tab-pane>
            </vort-tabs>

            <!-- Cases Tab Content -->
            <div v-if="activeTab === 'cases'" class="flex min-h-[500px]">
                <!-- Left: Module tree -->
                <div class="w-[220px] border-r border-gray-100 p-4 shrink-0 overflow-y-auto">
                    <div class="flex items-center justify-between mb-3">
                        <span class="text-sm font-medium text-gray-700">功能模块</span>
                        <Search
                            :size="14"
                            class="text-gray-400 cursor-pointer hover:text-gray-600"
                            @click="showModuleSearch = !showModuleSearch"
                        />
                    </div>

                    <div v-if="showModuleSearch" class="mb-2">
                        <vort-input-search
                            v-model="moduleSearch"
                            placeholder="搜索模块"
                            allow-clear
                            size="small"
                        />
                    </div>

                    <!-- All cases -->
                    <div
                        class="flex items-center gap-1.5 px-2 py-1.5 rounded cursor-pointer text-sm mb-1"
                        :class="selectedModuleId === '' ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                        @click="selectModule('')"
                    >
                        <FolderOpen :size="14" />
                        <span>全部用例</span>
                    </div>

                    <!-- Tree nodes -->
                    <div
                        v-for="node in flatNodes"
                        :key="node.id"
                        class="flex items-center gap-1 px-2 py-1.5 rounded cursor-pointer text-sm"
                        :class="selectedModuleId === node.id ? 'bg-blue-50 text-blue-600' : 'text-gray-600 hover:bg-gray-50'"
                        :style="{ paddingLeft: `${8 + node.depth * 16}px` }"
                        @click="selectModule(node.id)"
                    >
                        <span
                            v-if="node.hasChildren"
                            class="shrink-0 cursor-pointer"
                            @click.stop="toggleModuleExpand(node.id)"
                        >
                            <ChevronDown v-if="node.expanded" :size="12" />
                            <ChevronRight v-else :size="12" />
                        </span>
                        <span v-else class="w-3 shrink-0" />
                        <component :is="node.hasChildren && node.expanded ? FolderOpen : Folder" :size="14" class="shrink-0" />
                        <span class="truncate">{{ node.name }}</span>
                        <vort-badge
                            v-if="moduleAggCounts.get(node.id)"
                            :count="moduleAggCounts.get(node.id)"
                            :overflow-count="999"
                            size="small"
                            class="shrink-0 ml-auto"
                        />
                    </div>
                </div>

                <!-- Right: Cases table -->
                <div class="flex-1 p-4 overflow-x-auto">
                    <div class="flex items-center justify-between mb-3">
                        <div class="flex items-center gap-3">
                            <vort-input-search
                                v-model="caseKeyword"
                                placeholder="搜索用例"
                                allow-clear
                                size="small"
                                class="w-[200px]"
                                @search="loadCases"
                                @keyup.enter="loadCases"
                            />
                            <span class="text-sm text-gray-400 whitespace-nowrap">共 {{ casesTotal }} 项</span>
                        </div>
                        <div class="flex items-center gap-2">
                            <Dropdown v-model:open="caseSortOpen" trigger="click" placement="bottomRight">
                                <vort-button size="small">
                                    <ArrowUpDown :size="14" class="mr-1" /> {{ currentSortLabel }}
                                </vort-button>
                                <template #overlay>
                                    <DropdownMenuItem
                                        v-for="opt in sortOptions"
                                        :key="opt.value"
                                        @click="handleSortChange(opt.value)"
                                    >
                                        <Check v-if="caseSortBy === opt.value" :size="14" class="text-blue-500 mr-1.5" />
                                        <span v-else class="w-[14px] mr-1.5 inline-block" />
                                        {{ opt.label }}
                                    </DropdownMenuItem>
                                </template>
                            </Dropdown>
                            <Dropdown v-model:open="caseFilterOpen" trigger="click" placement="bottomRight">
                                <vort-button size="small">
                                    <Filter :size="14" class="mr-1" /> 筛选
                                    <span v-if="caseFilterCount" class="ml-1 text-blue-500">{{ caseFilterCount }}</span>
                                </vort-button>
                                <template #overlay>
                                    <div class="p-3 w-[220px] space-y-3" @click.stop>
                                        <div>
                                            <div class="text-xs text-gray-400 mb-1.5">用例类型</div>
                                            <vort-select v-model="caseFilterType" placeholder="全部" allow-clear size="small" style="width: 100%">
                                                <vort-select-option value="functional">功能测试</vort-select-option>
                                                <vort-select-option value="performance">性能测试</vort-select-option>
                                                <vort-select-option value="api">接口测试</vort-select-option>
                                                <vort-select-option value="ui">UI 测试</vort-select-option>
                                                <vort-select-option value="security">安全测试</vort-select-option>
                                            </vort-select>
                                        </div>
                                        <div>
                                            <div class="text-xs text-gray-400 mb-1.5">优先级</div>
                                            <vort-select v-model="caseFilterPriority" placeholder="全部" allow-clear size="small" style="width: 100%">
                                                <vort-select-option value="0">P0</vort-select-option>
                                                <vort-select-option value="1">P1</vort-select-option>
                                                <vort-select-option value="2">P2</vort-select-option>
                                                <vort-select-option value="3">P3</vort-select-option>
                                            </vort-select>
                                        </div>
                                        <div class="flex justify-end gap-2 pt-1">
                                            <vort-button size="small" @click="handleResetFilter">重置</vort-button>
                                            <vort-button variant="primary" size="small" @click="handleApplyFilter">确定</vort-button>
                                        </div>
                                    </div>
                                </template>
                            </Dropdown>
                            <vort-button variant="primary" size="small" @click="addCasesDialogOpen = true">
                                <Plus :size="14" class="mr-1" /> 添加用例
                            </vort-button>
                        </div>
                    </div>

                    <vort-table :data-source="cases" :loading="casesLoading" :pagination="false" row-key="plan_case_id">
                        <vort-table-column label="编号" :width="80">
                            <template #default="{ row }">
                                <span class="text-xs text-gray-400 font-mono">{{ row.test_case_id?.slice(0, 5)?.toUpperCase() }}</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="标题" :min-width="180">
                            <template #default="{ row }">
                                <a class="text-sm text-blue-600 cursor-pointer hover:underline" @click="handleViewCase(row)">{{ row.title }}</a>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="类型" :width="100">
                            <template #default="{ row }">
                                <span class="text-sm text-gray-500">{{ caseTypeLabels[row.case_type] || row.case_type }}</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="优先级" :width="70">
                            <template #default="{ row }">
                                <vort-tag :color="priorityColors[row.priority] || 'default'" size="small">
                                    {{ priorityLabels[row.priority] || `P${row.priority}` }}
                                </vort-tag>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="负责人" :width="100">
                            <template #default="{ row }">
                                <div v-if="row.maintainer_name" class="flex items-center gap-1.5">
                                    <span
                                        class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                                        :style="{ backgroundColor: getAvatarBg(row.maintainer_name) }"
                                    >
                                        <img
                                            v-if="getMemberAvatarUrl(row.maintainer_name)"
                                            :src="getMemberAvatarUrl(row.maintainer_name)"
                                            class="w-full h-full object-cover"
                                        >
                                        <template v-else>{{ getAvatarLabel(row.maintainer_name) }}</template>
                                    </span>
                                    <span class="text-sm text-gray-600 truncate">{{ row.maintainer_name }}</span>
                                </div>
                                <span v-else class="text-sm text-gray-400">无</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="执行结果分布" :width="140">
                            <template #default="{ row }">
                                <vort-tooltip v-if="row.execution_count">
                                    <div class="flex items-center gap-1">
                                        <span v-if="row.execution_distribution?.passed" class="exec-badge exec-badge-passed">
                                            {{ row.execution_distribution.passed }}
                                        </span>
                                        <span v-if="row.execution_distribution?.blocked" class="exec-badge exec-badge-blocked">
                                            {{ row.execution_distribution.blocked }}
                                        </span>
                                        <span v-if="row.execution_distribution?.failed" class="exec-badge exec-badge-failed">
                                            {{ row.execution_distribution.failed }}
                                        </span>
                                        <span v-if="row.execution_distribution?.skipped" class="exec-badge exec-badge-skipped">
                                            {{ row.execution_distribution.skipped }}
                                        </span>
                                    </div>
                                    <template #title>
                                        <div class="space-y-1 text-sm whitespace-nowrap">
                                            <div v-if="row.execution_distribution?.passed" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-green-500 inline-block shrink-0" />
                                                <span>通过: {{ row.execution_distribution.passed }}</span>
                                            </div>
                                            <div v-if="row.execution_distribution?.blocked" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-orange-400 inline-block shrink-0" />
                                                <span>受阻: {{ row.execution_distribution.blocked }}</span>
                                            </div>
                                            <div v-if="row.execution_distribution?.failed" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-red-500 inline-block shrink-0" />
                                                <span>失败: {{ row.execution_distribution.failed }}</span>
                                            </div>
                                            <div v-if="row.execution_distribution?.skipped" class="flex items-center gap-2">
                                                <span class="w-2 h-2 rounded-full bg-blue-400 inline-block shrink-0" />
                                                <span>跳过: {{ row.execution_distribution.skipped }}</span>
                                            </div>
                                        </div>
                                    </template>
                                </vort-tooltip>
                                <span v-else class="text-sm text-gray-400">0</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="最新执行结果" :width="120">
                            <template #default="{ row }">
                                <template v-if="latestResultDisplay(row)">
                                    <div class="flex items-center gap-1">
                                        <component
                                            :is="latestResultDisplay(row)!.icon"
                                            :size="14"
                                            :class="latestResultDisplay(row)!.color"
                                        />
                                        <span class="text-sm" :class="latestResultDisplay(row)!.color">
                                            {{ latestResultDisplay(row)!.label }}
                                        </span>
                                    </div>
                                </template>
                                <span v-else class="text-sm text-gray-400">未执行</span>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="新增执行结果" :width="110">
                            <template #default="{ row }">
                                <Dropdown v-model:open="executionDropdownOpen[row.plan_case_id]" trigger="click">
                                    <vort-button size="small" class="!px-2">
                                        <Plus :size="12" />
                                    </vort-button>
                                    <template #overlay>
                                        <DropdownMenuItem
                                            v-for="opt in resultOptions"
                                            :key="opt.value"
                                            @click="handleAddExecution(row.plan_case_id, opt.value)"
                                        >
                                            <component :is="opt.icon" :size="14" :class="opt.color" />
                                            <span>{{ opt.label }}</span>
                                        </DropdownMenuItem>
                                    </template>
                                </Dropdown>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="提缺陷" :width="70" align="center">
                            <template #default="{ row }">
                                <vort-tooltip title="提缺陷">
                                    <a class="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 cursor-pointer text-gray-400 hover:text-blue-500 transition-colors" @click="handleOpenFileBug(row)">
                                        <Bug :size="16" />
                                    </a>
                                </vort-tooltip>
                            </template>
                        </vort-table-column>

                        <vort-table-column label="操作" :width="60" fixed="right">
                            <template #default="{ row }">
                                <vort-popconfirm title="确认移除此用例？" @confirm="handleRemoveCase(row.plan_case_id)">
                                    <a class="text-sm text-red-500 cursor-pointer">移除</a>
                                </vort-popconfirm>
                            </template>
                        </vort-table-column>
                    </vort-table>
                </div>
            </div>

            <!-- Reviews Tab Content -->
            <div v-if="activeTab === 'reviews'" class="p-4">
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-3">
                        <span class="text-sm text-gray-400">
                            共 {{ reviews.length }} 个 PR
                            <template v-if="reviews.length > 0">
                                <span class="mx-1">|</span>
                                待评审 {{ reviews.filter((r: any) => r.review_status === 'pending').length }}
                                <span class="mx-1">|</span>
                                <span class="text-green-600">已通过 {{ reviews.filter((r: any) => r.review_status === 'approved').length }}</span>
                                <span class="mx-1">|</span>
                                <span class="text-red-500">已驳回 {{ reviews.filter((r: any) => r.review_status === 'rejected').length }}</span>
                            </template>
                        </span>
                    </div>
                    <vort-button variant="primary" size="small" @click="addPRDialogOpen = true">
                        <Plus :size="14" class="mr-1" /> 添加 PR
                    </vort-button>
                </div>

                <vort-table :data-source="reviews" :loading="reviewsLoading" :pagination="false" row-key="id">
                    <vort-table-column label="仓库" :width="120">
                        <template #default="{ row }">
                            <span class="text-sm text-gray-600">{{ row.repo_name || '-' }}</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="PR" :min-width="240">
                        <template #default="{ row }">
                            <div class="flex items-center gap-1.5">
                                <GitPullRequest :size="14" class="text-gray-400 shrink-0" />
                                <a
                                    v-if="row.pr_url"
                                    :href="row.pr_url"
                                    target="_blank"
                                    class="text-sm text-blue-600 hover:underline truncate"
                                >
                                    #{{ row.pr_number }} {{ row.pr_title }}
                                </a>
                                <span v-else class="text-sm text-gray-800 truncate">#{{ row.pr_number }} {{ row.pr_title }}</span>
                            </div>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="分支" :width="220">
                        <template #default="{ row }">
                            <span class="text-xs text-gray-500 font-mono">{{ row.head_branch }} &rarr; {{ row.base_branch }}</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="评审人" :width="140">
                        <template #default="{ row }">
                            <WorkItemMemberPicker
                                v-model:open="reviewerPickerOpenMap[row.id]"
                                mode="owner"
                                :owner="row.reviewer_name || ''"
                                :groups="ownerGroups"
                                :bordered="false"
                                :dropdown-max-height="320"
                                placeholder="指定评审人"
                                :get-avatar-bg="getAvatarBg"
                                :get-avatar-label="getAvatarLabel"
                                :get-avatar-url="getMemberAvatarUrl"
                                @update:owner="(name: string) => handleAssignReviewer(row, name)"
                            >
                                <template #trigger>
                                    <div class="flex items-center gap-1.5 cursor-pointer py-0.5">
                                        <template v-if="row.reviewer_name">
                                            <span
                                                class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                                                :style="{ backgroundColor: getAvatarBg(row.reviewer_name) }"
                                            >
                                                <img
                                                    v-if="getMemberAvatarUrl(row.reviewer_name)"
                                                    :src="getMemberAvatarUrl(row.reviewer_name)"
                                                    class="w-full h-full object-cover"
                                                >
                                                <template v-else>{{ getAvatarLabel(row.reviewer_name) }}</template>
                                            </span>
                                            <span class="text-sm text-gray-700 truncate">{{ row.reviewer_name }}</span>
                                        </template>
                                        <span v-else class="text-sm text-gray-400">指定评审人</span>
                                    </div>
                                </template>
                            </WorkItemMemberPicker>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="评审状态" :width="140">
                        <template #default="{ row }">
                            <div class="flex items-center gap-1">
                                <Dropdown trigger="click">
                                    <vort-tag
                                        :color="reviewStatusColors[row.review_status] || 'default'"
                                        class="cursor-pointer"
                                    >
                                        {{ reviewStatusLabels[row.review_status] || row.review_status }}
                                    </vort-tag>
                                    <template #overlay>
                                        <div class="py-1">
                                            <DropdownMenuItem
                                                v-for="(label, key) in reviewStatusLabels"
                                                :key="key"
                                                class="!py-2"
                                                @click="handleReviewStatusClick(row, key as string)"
                                            >
                                                <vort-tag :color="reviewStatusColors[key as string]" size="small">{{ label }}</vort-tag>
                                            </DropdownMenuItem>
                                        </div>
                                    </template>
                                </Dropdown>
                                <a
                                    v-if="row.review_notes"
                                    class="inline-flex items-center justify-center w-6 h-6 rounded hover:bg-gray-100 cursor-pointer text-gray-400 hover:text-blue-500 transition-colors shrink-0"
                                    @click="handleShowReviewNotes(row)"
                                >
                                    <MessageSquare :size="14" />
                                </a>
                            </div>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="操作" :width="140" fixed="right">
                        <template #default="{ row }">
                            <div class="flex items-center gap-1">
                                <vort-tooltip title="AI 评审">
                                    <a
                                        class="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 cursor-pointer"
                                        :class="aiReviewLoadingMap[row.id] ? 'text-blue-400' : 'text-gray-400 hover:text-blue-500'"
                                        @click="!aiReviewLoadingMap[row.id] && handleAiReview(row)"
                                    >
                                        <Loader2 v-if="aiReviewLoadingMap[row.id]" :size="14" class="animate-spin" />
                                        <Bot v-else :size="14" />
                                    </a>
                                </vort-tooltip>
                                <vort-tooltip title="评审历史">
                                    <a class="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 text-gray-400 hover:text-blue-500 cursor-pointer" @click="handleShowHistory(row)">
                                        <History :size="14" />
                                    </a>
                                </vort-tooltip>
                                <vort-tooltip v-if="row.pr_url" title="打开 PR">
                                    <a :href="row.pr_url" target="_blank" class="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 text-gray-400 hover:text-blue-500">
                                        <ExternalLink :size="14" />
                                    </a>
                                </vort-tooltip>
                                <vort-popconfirm title="确认移除此评审项？" @confirm="handleRemoveReview(row.id)">
                                    <a class="inline-flex items-center justify-center w-7 h-7 rounded hover:bg-gray-100 text-gray-400 hover:text-red-500 cursor-pointer">
                                        <Trash2 :size="14" />
                                    </a>
                                </vort-popconfirm>
                            </div>
                        </template>
                    </vort-table-column>
                </vort-table>
            </div>

            <!-- Report Tab Content -->
            <div v-if="activeTab === 'report'" class="p-4">
                <div class="flex items-center justify-between mb-3">
                    <span class="text-sm text-gray-400">共 {{ reportsTotal }} 项</span>
                    <vort-button variant="primary" size="small" :loading="reportGenerating" @click="handleGenerateReport">
                        <Plus :size="14" class="mr-1" /> 生成测试报告
                    </vort-button>
                </div>

                <vort-table :data-source="reports" :loading="reportsLoading" :pagination="false" row-key="id">
                    <vort-table-column label="标题" :min-width="200">
                        <template #default="{ row }">
                            <a class="text-sm text-blue-600 cursor-pointer hover:underline" @click="handleViewReport(row.id)">
                                {{ row.title }}
                            </a>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="创建人" :width="120">
                        <template #default="{ row }">
                            <div v-if="row.creator_name" class="flex items-center gap-1.5">
                                <span
                                    class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                                    :style="{ backgroundColor: getAvatarBg(row.creator_name) }"
                                >
                                    <img
                                        v-if="getMemberAvatarUrl(row.creator_name)"
                                        :src="getMemberAvatarUrl(row.creator_name)"
                                        class="w-full h-full object-cover"
                                    >
                                    <template v-else>{{ getAvatarLabel(row.creator_name) }}</template>
                                </span>
                                <span class="text-sm text-gray-600">{{ row.creator_name }}</span>
                            </div>
                            <span v-else class="text-sm text-gray-400">-</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="关联测试计划" :width="180">
                        <template #default="{ row }">
                            <span class="text-sm text-gray-600">{{ row.plan_title || '-' }}</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="创建时间" :width="160">
                        <template #default="{ row }">
                            <span class="text-sm text-gray-500">{{ row.created_at?.replace('T', ' ')?.slice(0, 16) || '-' }}</span>
                        </template>
                    </vort-table-column>

                    <vort-table-column label="操作" :width="60" fixed="right">
                        <template #default="{ row }">
                            <Dropdown trigger="click" placement="bottomRight">
                                <button class="p-1 rounded hover:bg-gray-100">
                                    <MoreHorizontal :size="16" class="text-gray-400" />
                                </button>
                                <template #overlay>
                                    <DropdownMenuItem @click="handleCopyReportLink(row.id)">
                                        <Copy :size="14" class="mr-1.5 text-gray-400" />
                                        复制报告链接
                                    </DropdownMenuItem>
                                    <DropdownMenuItem class="text-red-500" @click="handleDeleteReport(row.id)">
                                        <Trash2 :size="14" class="mr-1.5" />
                                        删除
                                    </DropdownMenuItem>
                                </template>
                            </Dropdown>
                        </template>
                    </vort-table-column>
                </vort-table>
            </div>
        </div>

        <!-- Edit Dialog -->
        <TestPlanEditDialog
            v-model:open="editDialogOpen"
            :edit-data="editData"
            @saved="loadPlan"
        />

        <!-- Add Cases Dialog -->
        <TestPlanAddCasesDialog
            v-model:open="addCasesDialogOpen"
            :plan-id="planId"
            :project-id="plan.project_id || ''"
            @saved="handleAddCasesSaved"
        />

        <!-- Add PR Dialog -->
        <TestPlanAddPRDialog
            v-model:open="addPRDialogOpen"
            :plan-id="planId"
            :project-id="plan.project_id || ''"
            @saved="handleAddPRSaved"
        />

        <!-- Review Notes Dialog -->
        <Dialog
            :open="reviewNotesDialogOpen"
            title="填写评审意见"
            :confirm-loading="reviewNotesSubmitting"
            ok-text="确认"
            @ok="handleReviewNotesSubmit"
            @update:open="reviewNotesDialogOpen = $event"
        >
            <div class="space-y-3">
                <div class="flex items-center gap-2 text-sm text-gray-500">
                    <span>将标记为</span>
                    <vort-tag v-if="reviewNotesTarget" :color="reviewStatusColors[reviewNotesTarget.status] || 'default'">
                        {{ reviewStatusLabels[reviewNotesTarget?.status] || '' }}
                    </vort-tag>
                </div>
                <vort-textarea
                    v-model="reviewNotesText"
                    :rows="4"
                    placeholder="请填写评审意见，说明需要修改的内容或驳回原因..."
                />
            </div>
        </Dialog>

        <!-- Review History Dialog -->
        <Dialog
            :open="historyDialogOpen"
            :title="`评审历史 — #${historyTarget?.pr_number || ''} ${historyTarget?.pr_title || ''}`"
            :width="600"
            :footer="false"
            @update:open="historyDialogOpen = $event"
        >
            <vort-spin :spinning="historyLoading">
                <div v-if="historyItems.length === 0 && !historyLoading" class="text-center py-8 text-sm text-gray-400">
                    暂无评审记录
                </div>
                <div v-else class="space-y-3 max-h-[400px] overflow-y-auto">
                    <div v-for="item in historyItems" :key="item.id" class="flex gap-3 text-sm">
                        <div class="flex flex-col items-center">
                            <span
                                class="w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-white text-[10px]"
                                :class="item.is_ai ? 'bg-blue-500' : 'bg-gray-400'"
                            >
                                <Bot v-if="item.is_ai" :size="14" />
                                <template v-else>{{ item.actor_name?.slice(0, 1) || '?' }}</template>
                            </span>
                            <div class="w-px flex-1 bg-gray-200 mt-1" />
                        </div>
                        <div class="flex-1 pb-4">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="font-medium text-gray-700">{{ item.is_ai ? 'AI 评审' : (item.actor_name || '未知') }}</span>
                                <template v-if="item.action === 'status_changed'">
                                    <vort-tag :color="reviewStatusColors[item.old_status] || 'default'" size="small">{{ reviewStatusLabels[item.old_status] || item.old_status }}</vort-tag>
                                    <span class="text-gray-400">&rarr;</span>
                                    <vort-tag :color="reviewStatusColors[item.new_status] || 'default'" size="small">{{ reviewStatusLabels[item.new_status] || item.new_status }}</vort-tag>
                                </template>
                                <template v-else-if="item.action === 'reviewer_assigned'">
                                    <span class="text-gray-500">指定了评审人</span>
                                </template>
                                <span class="text-xs text-gray-400 ml-auto shrink-0">{{ item.created_at?.replace('T', ' ')?.slice(0, 16) }}</span>
                            </div>
                            <div v-if="item.notes" class="text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-3 text-xs leading-relaxed">
                                {{ item.notes }}
                            </div>
                        </div>
                    </div>
                </div>
            </vort-spin>
        </Dialog>

        <!-- Review Detail Drawer -->
        <vort-drawer
            v-model:open="reviewDetailDrawerOpen"
            title="评审详情"
            :width="580"
        >
            <template v-if="reviewDetailTarget">
                <div class="space-y-5">
                    <div class="bg-gray-50 rounded-lg p-4 space-y-2.5">
                        <div class="flex items-center gap-2">
                            <GitPullRequest :size="14" class="text-gray-400 shrink-0" />
                            <a
                                v-if="reviewDetailTarget.pr_url"
                                :href="reviewDetailTarget.pr_url"
                                target="_blank"
                                class="text-sm text-blue-600 hover:underline"
                            >
                                #{{ reviewDetailTarget.pr_number }} {{ reviewDetailTarget.pr_title }}
                            </a>
                            <span v-else class="text-sm text-gray-800">
                                #{{ reviewDetailTarget.pr_number }} {{ reviewDetailTarget.pr_title }}
                            </span>
                        </div>
                        <div class="flex items-center gap-4 text-sm">
                            <div class="flex items-center gap-1.5">
                                <span class="text-gray-400">仓库:</span>
                                <span class="text-gray-700">{{ reviewDetailTarget.repo_name || '-' }}</span>
                            </div>
                            <div class="flex items-center gap-1.5">
                                <span class="text-gray-400">分支:</span>
                                <span class="text-gray-500 font-mono text-xs">{{ reviewDetailTarget.head_branch }} &rarr; {{ reviewDetailTarget.base_branch }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="flex items-center gap-2">
                            <span class="text-sm text-gray-400">评审状态</span>
                            <vort-tag :color="reviewStatusColors[reviewDetailTarget.review_status] || 'default'">
                                {{ reviewStatusLabels[reviewDetailTarget.review_status] || reviewDetailTarget.review_status }}
                            </vort-tag>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-sm text-gray-400">评审人</span>
                            <div v-if="reviewDetailTarget.reviewer_name" class="flex items-center gap-1.5">
                                <span
                                    class="w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center shrink-0 overflow-hidden"
                                    :style="{ backgroundColor: getAvatarBg(reviewDetailTarget.reviewer_name) }"
                                >
                                    <img
                                        v-if="getMemberAvatarUrl(reviewDetailTarget.reviewer_name)"
                                        :src="getMemberAvatarUrl(reviewDetailTarget.reviewer_name)"
                                        class="w-full h-full object-cover"
                                    >
                                    <template v-else>{{ getAvatarLabel(reviewDetailTarget.reviewer_name) }}</template>
                                </span>
                                <span class="text-sm text-gray-700">{{ reviewDetailTarget.reviewer_name }}</span>
                            </div>
                            <span v-else class="text-sm text-gray-500">未指定</span>
                        </div>
                    </div>

                    <div>
                        <span class="text-sm text-gray-400">评审意见</span>
                        <div class="mt-2 bg-gray-50 rounded-lg p-5 max-h-[calc(100vh-360px)] overflow-y-auto">
                            <MarkdownView :content="reviewDetailTarget.review_notes" />
                        </div>
                    </div>
                </div>
            </template>
        </vort-drawer>

        <!-- Case Detail Drawer -->
        <TestCaseDetailDrawer v-model:open="caseDetailDrawerOpen" :case-id="caseDetailId" />

        <!-- File Bug Drawer -->
        <vort-drawer
            v-model:open="fileBugDrawerOpen"
            title="提缺陷"
            :width="1180"
            :body-style="{ padding: '16px 20px 20px' }"
        >
            <WorkItemCreate
                ref="createWorkItemRef"
                type="缺陷"
                title="提缺陷"
                use-api
                :project-id="plan.project_id || ''"
                @close="handleCancelFileBug"
            />
            <template #footer>
                <div class="flex items-center gap-2">
                    <vort-button variant="primary" @click="handleSubmitFileBug">新建</vort-button>
                    <vort-button @click="handleCancelFileBug">取消</vort-button>
                </div>
            </template>
        </vort-drawer>
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

.exec-badge-passed {
    color: #16a34a;
    background: #f0fdf4;
}

.exec-badge-blocked {
    color: #ea580c;
    background: #fff7ed;
}

.exec-badge-failed {
    color: #dc2626;
    background: #fef2f2;
}

.exec-badge-skipped {
    color: #2563eb;
    background: #eff6ff;
}
</style>
