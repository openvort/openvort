<script setup lang="ts">
import { ref, onMounted, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
    getReports, getPublications, deletePublication, getReportStats,
    sendReminders, sendSummary,
} from "@/api";
import { Plus, Search, Clock, Users, Bell, Pencil } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import { useUserStore } from "@/stores";
import PublicationDrawer from "./components/PublicationDrawer.vue";
import WriteReportDrawer from "./components/WriteReportDrawer.vue";
import ReportDetailDrawer from "./components/ReportDetailDrawer.vue";

// ---- Types ----

interface ReportItem {
    id: string;
    publication_id: string;
    report_type: string;
    report_date: string;
    title: string;
    content: string;
    status: string;
    reporter_id: string;
    reporter_name: string;
    reporter_avatar_url: string;
    auto_generated: boolean;
    submitted_at: string | null;
    created_at: string;
}

interface DateGroup {
    date: string;
    label: string;
    items: ReportItem[];
}

interface PublicationItem {
    id: string;
    name: string;
    description: string;
    report_type: string;
    repeat_cycle: string;
    deadline_time: string;
    reminder_enabled: boolean;
    skip_weekends: boolean;
    skip_holidays: boolean;
    allow_multiple: boolean;
    allow_edit: boolean;
    notify_summary: boolean;
    notify_on_receive: boolean;
    enabled: boolean;
    submitter_ids: string[];
    submitter_names: string[];
    submitter_count: number;
    whitelist_ids: string[];
    whitelist_names: string[];
    receiver_ids: string[];
    receiver_names: string[];
    receiver_filters: Record<string, string[]>;
    owner_id: string;
    owner_name: string;
    created_at: string;
}

// ---- State ----

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.isAdmin || userStore.userInfo.roles?.includes("manager"));
const validTabs = ["read", "publish"];
const activeTab = ref(validTabs.includes(route.query.tab as string) ? (route.query.tab as string) : "read");
const readSubTab = ref("received");

watch(activeTab, (tab) => {
    router.replace({ query: { ...route.query, tab } });
});

// Reports
const receivedReports = ref<ReportItem[]>([]);
const myReports = ref<ReportItem[]>([]);
const loadingReceived = ref(false);
const loadingMy = ref(false);
const filterReporter = ref("");
const filterPubId = ref("");
const filterDate = ref("");
const filterStatus = ref("");
const searchKeyword = ref("");

// Publications (admin)
const publications = ref<PublicationItem[]>([]);
const loadingPubs = ref(false);

// Stats
const stats = ref({ total: 0, draft: 0, submitted: 0 });

// Drawers
const pubDrawerOpen = ref(false);
const editingPub = ref<any>(null);
const writeDrawerOpen = ref(false);
const detailDrawerOpen = ref(false);
const detailReportId = ref("");

// ---- Helpers ----

const typeLabel = (v: string) => ({ daily: "日报", weekly: "周报", monthly: "月报", quarterly: "季报" }[v] || v);
const typeColor = (v: string) => ({ daily: "blue", weekly: "purple", monthly: "orange", quarterly: "cyan" }[v] || "default");
const cycleLabel = (v: string) => ({ daily: "按日", weekly: "按周", monthly: "按月" }[v] || v);

const AVATAR_COLORS = ["#1677ff", "#52c41a", "#faad14", "#eb2f96", "#722ed1", "#13c2c2", "#fa541c", "#2f54eb"];
function avatarBg(name: string): string {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]!;
}

function formatContentPreview(content: string): string {
    const plain = content
        .replace(/^#{1,6}\s+/gm, "")
        .replace(/\*\*(.+?)\*\*/g, "$1")
        .replace(/\*(.+?)\*/g, "$1")
        .replace(/~~(.+?)~~/g, "$1")
        .replace(/`(.+?)`/g, "$1")
        .replace(/^\s*[-*+]\s+/gm, "- ")
        .replace(/^\s*\d+\.\s+/gm, "");
    const lines = plain.split("\n").filter(l => l.trim());
    return lines.slice(0, 3).join("\n").slice(0, 200);
}

function formatDateLabel(dateStr: string): string {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

function formatMemberSummary(names: string[], max = 3): string {
    if (names.length <= max) return names.join("、");
    return `${names.slice(0, max).join("、")} 等 ${names.length} 人`;
}

// unique reporter list for the person filter
const reporterOptions = computed(() => {
    const reports = readSubTab.value === "received" ? receivedReports.value : myReports.value;
    const map = new Map<string, string>();
    reports.forEach(r => { if (r.reporter_id && r.reporter_name) map.set(r.reporter_id, r.reporter_name); });
    return Array.from(map, ([id, name]) => ({ id, name }));
});

// ---- Data loading ----

async function loadReceivedReports() {
    loadingReceived.value = true;
    try {
        const params: Record<string, any> = { scope: "received", page_size: 100 };
        if (filterPubId.value) params.publication_id = filterPubId.value;
        if (filterDate.value) { params.since = filterDate.value; params.until = filterDate.value; }
        if (filterReporter.value) params.reporter_id = filterReporter.value;
        const res: any = await getReports(params);
        receivedReports.value = res?.items || [];
    } catch { receivedReports.value = []; }
    finally { loadingReceived.value = false; }
}

async function loadMyReports() {
    loadingMy.value = true;
    try {
        const params: Record<string, any> = { page_size: 100 };
        if (filterPubId.value) params.publication_id = filterPubId.value;
        if (filterDate.value) { params.since = filterDate.value; params.until = filterDate.value; }
        const res: any = await getReports(params);
        myReports.value = res?.items || [];
    } catch { myReports.value = []; }
    finally { loadingMy.value = false; }
}

async function loadPublications() {
    loadingPubs.value = true;
    try {
        const res: any = await getPublications();
        publications.value = res?.publications || [];
    } catch { publications.value = []; }
    finally { loadingPubs.value = false; }
}

async function loadStats() {
    try {
        const res: any = await getReportStats();
        stats.value = res || { total: 0, draft: 0, submitted: 0 };
    } catch { /* ignore */ }
}

function refreshReportData() {
    loadReceivedReports();
    loadMyReports();
    loadStats();
}

function reloadCurrentTab() {
    if (readSubTab.value === "received") loadReceivedReports();
    else loadMyReports();
}

function resetFilters() {
    filterReporter.value = "";
    filterPubId.value = "";
    filterDate.value = "";
    filterStatus.value = "";
    searchKeyword.value = "";
    reloadCurrentTab();
}

// ---- Filtered & grouped ----

function applyLocalFilters(reports: ReportItem[]): ReportItem[] {
    let items = reports;
    if (filterStatus.value) {
        items = items.filter(r => r.status === filterStatus.value);
    }
    if (searchKeyword.value.trim()) {
        const q = searchKeyword.value.trim().toLowerCase();
        items = items.filter(r =>
            r.title.toLowerCase().includes(q) || r.reporter_name.toLowerCase().includes(q) || r.content.toLowerCase().includes(q)
        );
    }
    return items;
}

function groupByDate(reports: ReportItem[]): DateGroup[] {
    const map = new Map<string, ReportItem[]>();
    for (const r of reports) {
        const key = r.report_date || "unknown";
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(r);
    }
    return Array.from(map, ([date, items]) => ({
        date,
        label: formatDateLabel(date),
        items: items.sort((a, b) => (b.submitted_at || "").localeCompare(a.submitted_at || "")),
    })).sort((a, b) => b.date.localeCompare(a.date));
}

const groupedReceived = computed(() => groupByDate(applyLocalFilters(receivedReports.value)));
const groupedMy = computed(() => groupByDate(applyLocalFilters(myReports.value)));

const hasReceivedData = computed(() => groupedReceived.value.some(g => g.items.length > 0));
const hasMyData = computed(() => groupedMy.value.some(g => g.items.length > 0));

// ---- Actions ----

function openDetail(reportId: string) {
    detailReportId.value = reportId;
    detailDrawerOpen.value = true;
}

function openPubDrawer(pub?: PublicationItem) {
    editingPub.value = pub || null;
    pubDrawerOpen.value = true;
}

function handleCopyPub(pub: PublicationItem) {
    const { id, submitter_names, submitter_count, whitelist_names, receiver_names, owner_id, owner_name, created_at, enabled, ...rest } = pub;
    editingPub.value = { ...rest, name: `${pub.name} (副本)` };
    pubDrawerOpen.value = true;
}

async function handleDeletePub(id: string) {
    try {
        const res: any = await deletePublication(id);
        if (res?.success) {
            message.success("已删除");
            await loadPublications();
        }
    } catch { message.error("删除失败"); }
}

async function handleSendReminder(id: string) {
    try {
        const res: any = await sendReminders(id);
        if (res?.ok) {
            if (res.sent > 0) {
                message.success(`已发送提醒：${res.sent} 人`);
            } else if (res.submitter_count > 0 && res.submitted_count >= res.submitter_count) {
                message.warning("所有提交人今日已提交，无需催报");
            } else if (res.submitter_count === 0) {
                message.warning("该发布暂无提交人");
            } else {
                message.success("已发送提醒：0 人");
            }
        } else { message.error(res?.error || "发送失败"); }
    } catch { message.error("发送失败"); }
}

async function handleSendSummary(id: string) {
    try {
        const res: any = await sendSummary(id);
        if (res?.ok) {
            message.success(`已发送汇总：${res.sent} 人`);
        } else { message.error(res?.error || "发送失败"); }
    } catch { message.error("发送失败"); }
}

// ---- Init ----

onMounted(() => {
    refreshReportData();
    loadPublications();
});
</script>

<template>
    <div class="space-y-4">
        <!-- Main content -->
        <div class="bg-white rounded-xl p-6">
            <!-- Tabs -->
            <VortTabs v-model:activeKey="activeTab" :hide-content="true" class="mb-5">
                <VortTabPane tab-key="read" tab="读汇报" />
                <VortTabPane v-if="isAdmin" tab-key="publish" tab="发布汇报" />
            </VortTabs>

            <!-- ===== 读汇报 content ===== -->
            <div v-show="activeTab === 'read'">
                    <!-- Sub tabs (segment style) -->
                    <div class="flex items-center gap-1 bg-gray-50 rounded-lg p-0.5 w-fit mb-5">
                        <button
                            class="px-4 py-1.5 rounded-md text-sm font-medium transition-all"
                            :class="readSubTab === 'received' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                            @click="readSubTab = 'received'; resetFilters()"
                        >我收到的</button>
                        <button
                            class="px-4 py-1.5 rounded-md text-sm font-medium transition-all"
                            :class="readSubTab === 'submitted' ? 'bg-white text-gray-800 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
                            @click="readSubTab = 'submitted'; resetFilters()"
                        >我提交的</button>
                    </div>

                    <!-- Filters -->
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2">
                            <vort-select v-model="filterReporter" placeholder="所有人" allow-clear style="width: 110px" @change="reloadCurrentTab">
                                <vort-select-option value="">所有人</vort-select-option>
                                <vort-select-option v-for="m in reporterOptions" :key="m.id" :value="m.id">{{ m.name }}</vort-select-option>
                            </vort-select>
                            <vort-select v-model="filterPubId" placeholder="所有模板" allow-clear style="width: 140px" @change="reloadCurrentTab">
                                <vort-select-option value="">所有模板</vort-select-option>
                                <vort-select-option v-for="pub in publications" :key="pub.id" :value="pub.id">{{ pub.name }}</vort-select-option>
                            </vort-select>
                            <vort-date-picker v-model="filterDate" value-format="YYYY-MM-DD" placeholder="选择日期" allow-clear style="width: 140px" @change="reloadCurrentTab" />
                            <vort-select v-model="filterStatus" placeholder="全部状态" allow-clear style="width: 120px">
                                <vort-select-option value="">全部状态</vort-select-option>
                                <vort-select-option value="submitted">已提交</vort-select-option>
                                <vort-select-option value="draft">草稿</vort-select-option>
                            </vort-select>
                        </div>
                        <div class="flex items-center gap-2">
                            <vort-input-search
                                v-model="searchKeyword"
                                placeholder="搜索汇报内容"
                                allow-clear
                                style="width: 180px"
                            />
                            <vort-button variant="primary" @click="writeDrawerOpen = true">
                                <Pencil :size="14" class="mr-1" /> 写汇报
                            </vort-button>
                        </div>
                    </div>

                    <!-- Received reports (date grouped) -->
                    <div v-if="readSubTab === 'received'">
                        <vort-spin :spinning="loadingReceived">
                            <div v-if="hasReceivedData" class="space-y-6">
                                <div v-for="group in groupedReceived" :key="group.date">
                                    <div class="text-xs text-gray-400 pb-2 mb-2 border-b border-gray-100">{{ group.label }}</div>
                                    <div class="space-y-0">
                                        <div
                                            v-for="r in group.items" :key="r.id"
                                            class="flex items-start gap-3 px-3 py-3.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                                            @click="openDetail(r.id)"
                                        >
                                            <div
                                                class="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center overflow-hidden mt-0.5"
                                                :style="{ backgroundColor: r.reporter_avatar_url ? undefined : avatarBg(r.reporter_name) }"
                                            >
                                                <img v-if="r.reporter_avatar_url" :src="r.reporter_avatar_url" class="w-full h-full object-cover" />
                                                <span v-else class="text-white text-xs font-medium">{{ (r.reporter_name || '?')[0] }}</span>
                                            </div>
                                            <div class="flex-1 min-w-0">
                                                <div class="flex items-center gap-2 mb-0.5">
                                                    <span class="text-sm font-semibold text-gray-900">{{ r.reporter_name }}</span>
                                                </div>
                                                <p class="text-sm text-gray-500 line-clamp-2 whitespace-pre-line leading-relaxed">{{ formatContentPreview(r.content) || r.title }}</p>
                                            </div>
                                            <span class="text-xs text-gray-400 flex-shrink-0 mt-1">
                                                {{ r.submitted_at?.slice(11, 16) || '' }}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div v-else class="text-gray-400 text-sm text-center py-16">暂无收到的汇报</div>
                        </vort-spin>
                    </div>

                    <!-- Submitted reports (date grouped) -->
                    <div v-if="readSubTab === 'submitted'">
                        <vort-spin :spinning="loadingMy">
                            <div v-if="hasMyData" class="space-y-6">
                                <div v-for="group in groupedMy" :key="group.date">
                                    <div class="text-xs text-gray-400 pb-2 mb-2 border-b border-gray-100">{{ group.label }}</div>
                                    <div class="space-y-0">
                                        <div
                                            v-for="r in group.items" :key="r.id"
                                            class="flex items-start gap-3 px-3 py-3.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                                            @click="openDetail(r.id)"
                                        >
                                            <div
                                                class="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center overflow-hidden mt-0.5"
                                                :style="{ backgroundColor: r.reporter_avatar_url ? undefined : avatarBg(r.reporter_name) }"
                                            >
                                                <img v-if="r.reporter_avatar_url" :src="r.reporter_avatar_url" class="w-full h-full object-cover" />
                                                <span v-else class="text-white text-xs font-medium">{{ (r.reporter_name || '?')[0] }}</span>
                                            </div>
                                            <div class="flex-1 min-w-0">
                                                <div class="flex items-center gap-2 mb-0.5">
                                                    <span class="text-sm font-semibold text-gray-900">{{ r.reporter_name }}</span>
                                                    <vort-tag v-if="r.auto_generated" size="small" color="cyan">AI</vort-tag>
                                                </div>
                                                <p class="text-sm text-gray-500 line-clamp-2 whitespace-pre-line leading-relaxed">{{ formatContentPreview(r.content) || r.title }}</p>
                                            </div>
                                            <span class="text-xs text-gray-400 flex-shrink-0 mt-1">
                                                {{ r.submitted_at?.slice(11, 16) || '' }}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div v-else class="text-gray-400 text-sm text-center py-16">暂无提交记录</div>
                        </vort-spin>
                    </div>
            </div>

            <!-- ===== 发布汇报 content ===== -->
            <div v-if="isAdmin" v-show="activeTab === 'publish'">
                    <div class="flex items-center justify-between mb-4">
                        <h4 class="text-sm font-medium text-gray-600">已发布的汇报</h4>
                        <vort-button variant="primary" @click="openPubDrawer()">
                            <Plus :size="14" class="mr-1" /> 发布汇报
                        </vort-button>
                    </div>

                    <vort-spin :spinning="loadingPubs">
                        <div v-if="publications.length" class="space-y-3">
                            <div
                                v-for="pub in publications" :key="pub.id"
                                class="border border-gray-100 rounded-lg p-4"
                            >
                                <div class="flex items-start justify-between">
                                    <div class="min-w-0 flex-1">
                                        <div class="flex items-center gap-2 mb-1">
                                            <span class="text-sm font-medium text-gray-800">{{ pub.name }}</span>
                                            <vort-tag :color="typeColor(pub.report_type)" size="small">{{ typeLabel(pub.report_type) }}</vort-tag>
                                            <vort-tag size="small" :color="pub.enabled ? 'green' : 'default'">
                                                {{ pub.enabled ? '启用' : '停用' }}
                                            </vort-tag>
                                        </div>
                                        <p class="text-xs text-gray-400 mb-2 truncate max-w-lg">{{ pub.description || '暂无描述' }}</p>
                                        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
                                            <span class="flex items-center gap-1">
                                                <Users :size="12" /> 提交人 {{ pub.submitter_count }} 人
                                            </span>
                                            <span class="flex items-center gap-1">
                                                <Clock :size="12" /> {{ cycleLabel(pub.repeat_cycle) }} {{ pub.deadline_time }}
                                            </span>
                                            <span class="flex items-center gap-1">
                                                <Bell :size="12" /> 接收人 {{ formatMemberSummary(pub.receiver_names) }}
                                            </span>
                                            <span v-if="pub.skip_weekends">跳过周末</span>
                                            <span v-if="pub.skip_holidays">跳过节假日</span>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2 whitespace-nowrap flex-shrink-0 ml-4">
                                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleSendReminder(pub.id)">催报</a>
                                        <vort-divider type="vertical" />
                                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleSendSummary(pub.id)">汇总</a>
                                        <vort-divider type="vertical" />
                                        <a class="text-sm text-blue-600 cursor-pointer" @click="openPubDrawer(pub)">编辑</a>
                                        <vort-divider type="vertical" />
                                        <a class="text-sm text-blue-600 cursor-pointer" @click="handleCopyPub(pub)">复制</a>
                                        <vort-divider type="vertical" />
                                        <vort-popconfirm title="确认删除此发布？" @confirm="handleDeletePub(pub.id)">
                                            <a class="text-sm text-red-500 cursor-pointer">删除</a>
                                        </vort-popconfirm>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-else class="text-gray-400 text-sm text-center py-16">
                            暂无发布，点击右上角「发布汇报」开始
                        </div>
                    </vort-spin>
            </div>
        </div>

        <!-- Drawers -->
        <PublicationDrawer
            :open="pubDrawerOpen"
            :edit-data="editingPub"
            @update:open="pubDrawerOpen = $event"
            @saved="loadPublications"
        />

        <WriteReportDrawer
            :open="writeDrawerOpen"
            @update:open="writeDrawerOpen = $event"
            @saved="refreshReportData"
        />

        <ReportDetailDrawer
            :open="detailDrawerOpen"
            :report-id="detailReportId"
            @update:open="detailDrawerOpen = $event"
            @updated="refreshReportData"
        />
    </div>
</template>
