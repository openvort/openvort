<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import { useRouter } from "vue-router";
import { getCertStats, getCertDomains, checkAllDomains, checkSingleDomain, deleteCertDomain } from "@/api";
import { message } from "@openvort/vort-ui";
import { ShieldCheck, ShieldAlert, ShieldX, Globe, RefreshCw, Plus, Search, Rocket } from "lucide-vue-next";
import IssueDialog from "./IssueDialog.vue";
import CertDetailDrawer from "./CertDetailDrawer.vue";
import DeployDialog from "./DeployDialog.vue";
import DeployLogsDrawer from "./DeployLogsDrawer.vue";
import dayjs from "dayjs";

const router = useRouter();

interface Stats {
    total: number;
    ok: number;
    warning: number;
    expired: number;
    error: number;
    unchecked: number;
}

interface DomainItem {
    id: string;
    domain: string;
    domain_type: string;
    label: string;
    last_check_status: string;
    expires_at: string | null;
    issuer: string;
    last_check_at: string | null;
}

const stats = ref<Stats>({ total: 0, ok: 0, warning: 0, expired: 0, error: 0, unchecked: 0 });
const domains = ref<DomainItem[]>([]);
const loading = ref(false);
const checkingAll = ref(false);
const checkingId = ref("");
const keyword = ref("");
const statusFilter = ref("");
const issueDialogOpen = ref(false);
const certDrawerOpen = ref(false);
const certDrawerDomainId = ref("");
const certDrawerDomainName = ref("");
const deployDialogOpen = ref(false);
const deployDomainId = ref("");
const deployDomainName = ref("");
const deployLogsOpen = ref(false);
const deployLogsDomainName = ref("");

const handleViewCert = (domain: DomainItem) => {
    certDrawerDomainId.value = domain.id;
    certDrawerDomainName.value = domain.domain;
    certDrawerOpen.value = true;
};

const handleDeploy = (domain: DomainItem) => {
    deployDomainId.value = domain.id;
    deployDomainName.value = domain.domain;
    deployDialogOpen.value = true;
};

const handleViewDeployLogs = (domain: DomainItem) => {
    deployLogsDomainName.value = domain.domain;
    deployLogsOpen.value = true;
};

const handleDelete = async (domain: DomainItem) => {
    try {
        await deleteCertDomain(domain.id);
        message.success(`已删除域名 ${domain.domain}`);
        await loadData();
    } catch {
        message.error("删除失败");
    }
};

const filteredDomains = computed(() => {
    let list = domains.value;
    if (keyword.value) {
        const kw = keyword.value.toLowerCase();
        list = list.filter(d => d.domain.toLowerCase().includes(kw) || d.label?.toLowerCase().includes(kw));
    }
    if (statusFilter.value) {
        list = list.filter(d => d.last_check_status === statusFilter.value);
    }
    return list;
});

const loadData = async () => {
    loading.value = true;
    try {
        const [statsRes, domainsRes] = await Promise.all([
            getCertStats(),
            getCertDomains({ page: 1, page_size: 200 }),
        ]);
        stats.value = statsRes as any;
        domains.value = ((domainsRes as any).items || []);
    } catch (e) {
        console.error(e);
    } finally {
        loading.value = false;
    }
};

const handleCheckAll = async () => {
    checkingAll.value = true;
    try {
        const res = await checkAllDomains() as any;
        message.success(`巡检完成，共检查 ${res.checked} 个域名`);
        await loadData();
    } catch (e) {
        message.error("巡检失败");
    } finally {
        checkingAll.value = false;
    }
};

const handleCheckSingle = async (domain: DomainItem) => {
    checkingId.value = domain.id;
    try {
        await checkSingleDomain(domain.id);
        message.success(`${domain.domain} 检查完成`);
        await loadData();
    } catch (e) {
        message.error("检查失败");
    } finally {
        checkingId.value = "";
    }
};

const statusTagColor = (status: string) => {
    const map: Record<string, string> = {
        ok: "green",
        warning: "orange",
        critical: "red",
        expired: "red",
        error: "default",
    };
    return map[status] || "default";
};

const statusLabel = (status: string) => {
    const map: Record<string, string> = {
        ok: "正常",
        warning: "即将到期",
        critical: "即将到期",
        expired: "已过期",
        error: "异常",
        "": "未检查",
    };
    return map[status] || status;
};

const expiresColor = (expiresAt: string | null) => {
    if (!expiresAt) return "text-gray-400";
    const days = dayjs(expiresAt).diff(dayjs(), "day");
    if (days < 0) return "text-red-600 font-medium";
    if (days <= 7) return "text-red-500";
    if (days <= 30) return "text-orange-500";
    return "text-gray-700";
};

const daysRemaining = (expiresAt: string | null) => {
    if (!expiresAt) return null;
    return dayjs(expiresAt).diff(dayjs(), "day");
};

const handleIssueSuccess = () => {
    issueDialogOpen.value = false;
    loadData();
};

onMounted(loadData);
</script>

<template>
    <div class="space-y-4">
        <!-- Stats Cards -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div class="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-sm transition-shadow">
                <div class="flex items-center justify-between mb-3">
                    <p class="text-xs text-gray-500 font-medium">域名总数</p>
                    <div class="w-9 h-9 rounded-lg flex items-center justify-center bg-gradient-to-br from-blue-500 to-blue-600 shadow-sm">
                        <Globe :size="18" class="text-white" />
                    </div>
                </div>
                <p class="text-2xl font-semibold text-gray-800">{{ stats.total }}</p>
            </div>
            <div class="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-sm transition-shadow cursor-pointer" @click="statusFilter = statusFilter === 'ok' ? '' : 'ok'">
                <div class="flex items-center justify-between mb-3">
                    <p class="text-xs text-gray-500 font-medium">证书正常</p>
                    <div class="w-9 h-9 rounded-lg flex items-center justify-center bg-gradient-to-br from-green-500 to-green-600 shadow-sm">
                        <ShieldCheck :size="18" class="text-white" />
                    </div>
                </div>
                <p class="text-2xl font-semibold text-green-600">{{ stats.ok }}</p>
            </div>
            <div class="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-sm transition-shadow cursor-pointer" @click="statusFilter = statusFilter === 'warning' ? '' : 'warning'">
                <div class="flex items-center justify-between mb-3">
                    <p class="text-xs text-gray-500 font-medium">即将到期</p>
                    <div class="w-9 h-9 rounded-lg flex items-center justify-center bg-gradient-to-br from-orange-400 to-orange-500 shadow-sm">
                        <ShieldAlert :size="18" class="text-white" />
                    </div>
                </div>
                <p class="text-2xl font-semibold text-orange-500">{{ stats.warning }}</p>
            </div>
            <div class="bg-white rounded-xl border border-gray-100 p-5 hover:shadow-sm transition-shadow cursor-pointer" @click="statusFilter = statusFilter === 'expired' ? '' : 'expired'">
                <div class="flex items-center justify-between mb-3">
                    <p class="text-xs text-gray-500 font-medium">已过期</p>
                    <div class="w-9 h-9 rounded-lg flex items-center justify-center bg-gradient-to-br from-red-500 to-red-600 shadow-sm">
                        <ShieldX :size="18" class="text-white" />
                    </div>
                </div>
                <p class="text-2xl font-semibold text-red-500">{{ stats.expired }}</p>
            </div>
        </div>

        <!-- Domain Certificate Table -->
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-4">
                <h3 class="text-base font-medium text-gray-800">域名证书状态</h3>
                <div class="flex items-center gap-2">
                    <vort-button :loading="checkingAll" @click="handleCheckAll">
                        <RefreshCw :size="14" class="mr-1" /> 全量巡检
                    </vort-button>
                    <vort-button variant="primary" @click="issueDialogOpen = true">
                        <Plus :size="14" class="mr-1" /> 签发证书
                    </vort-button>
                </div>
            </div>

            <div class="flex items-center gap-3 mb-4">
                <vort-input-search
                    v-model="keyword"
                    placeholder="搜索域名..."
                    allow-clear
                    class="w-[260px]"
                />
                <vort-select v-model="statusFilter" placeholder="状态筛选" allow-clear class="w-[140px]">
                    <vort-select-option value="ok">正常</vort-select-option>
                    <vort-select-option value="warning">即将到期</vort-select-option>
                    <vort-select-option value="expired">已过期</vort-select-option>
                    <vort-select-option value="error">异常</vort-select-option>
                    <vort-select-option value="">未检查</vort-select-option>
                </vort-select>
            </div>

            <vort-table :data-source="filteredDomains" :loading="loading" :pagination="false" row-key="id">
                <vort-table-column label="域名" prop="domain" :min-width="220">
                    <template #default="{ row }">
                        <div class="font-medium text-gray-800">{{ row.domain }}</div>
                        <div v-if="row.label" class="text-xs text-gray-400 mt-0.5">{{ row.label }}</div>
                    </template>
                </vort-table-column>
                <vort-table-column label="签发机构" prop="issuer" :min-width="160">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-600">{{ row.issuer || '-' }}</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="到期时间" prop="expires_at" :min-width="180">
                    <template #default="{ row }">
                        <template v-if="row.expires_at">
                            <div :class="expiresColor(row.expires_at)">
                                {{ dayjs(row.expires_at).format("YYYY-MM-DD HH:mm") }}
                            </div>
                            <div class="text-xs mt-0.5" :class="expiresColor(row.expires_at)">
                                {{ daysRemaining(row.expires_at)! >= 0 ? `剩余 ${daysRemaining(row.expires_at)} 天` : `已过期 ${Math.abs(daysRemaining(row.expires_at)!)} 天` }}
                            </div>
                        </template>
                        <span v-else class="text-sm text-gray-400">-</span>
                    </template>
                </vort-table-column>
                <vort-table-column label="状态" prop="last_check_status" :width="100">
                    <template #default="{ row }">
                        <vort-tag :color="statusTagColor(row.last_check_status)" size="small">
                            {{ statusLabel(row.last_check_status) }}
                        </vort-tag>
                    </template>
                </vort-table-column>
                <vort-table-column label="最后巡检" prop="last_check_at" :width="150">
                    <template #default="{ row }">
                        <span class="text-sm text-gray-500">
                            {{ row.last_check_at ? dayjs(row.last_check_at).format("MM-DD HH:mm") : '-' }}
                        </span>
                    </template>
                </vort-table-column>
                <vort-table-column label="操作" :width="260" fixed="right">
                    <template #default="{ row }">
                        <div class="flex items-center gap-2 whitespace-nowrap">
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleViewCert(row)">证书</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleDeploy(row)">部署</a>
                            <vort-divider type="vertical" />
                            <a class="text-sm text-blue-600 cursor-pointer" @click="handleViewDeployLogs(row)">日志</a>
                            <vort-divider type="vertical" />
                            <a
                                class="text-sm text-blue-600 cursor-pointer"
                                @click="handleCheckSingle(row)"
                            >
                                {{ checkingId === row.id ? '检查中...' : '检查' }}
                            </a>
                            <vort-divider type="vertical" />
                            <vort-popconfirm title="确认删除该域名？关联的证书和巡检记录也将一并删除。" @confirm="handleDelete(row)">
                                <a class="text-sm text-red-500 cursor-pointer">删除</a>
                            </vort-popconfirm>
                        </div>
                    </template>
                </vort-table-column>
            </vort-table>
        </div>

        <IssueDialog
            :open="issueDialogOpen"
            @update:open="issueDialogOpen = $event"
            @success="handleIssueSuccess"
        />

        <CertDetailDrawer
            :open="certDrawerOpen"
            :domain-id="certDrawerDomainId"
            :domain-name="certDrawerDomainName"
            @update:open="certDrawerOpen = $event"
        />

        <DeployDialog
            :open="deployDialogOpen"
            :domain-id="deployDomainId"
            :domain-name="deployDomainName"
            @update:open="deployDialogOpen = $event"
            @success="loadData"
        />

        <DeployLogsDrawer
            :open="deployLogsOpen"
            :domain-name="deployLogsDomainName"
            @update:open="deployLogsOpen = $event"
        />
    </div>
</template>
