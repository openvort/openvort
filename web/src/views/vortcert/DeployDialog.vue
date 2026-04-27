<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog, message } from "@openvort/vort-ui";
import { getCertCertificates, getCertDeployTargets, deployCertificate } from "@/api";
import dayjs from "dayjs";

const props = defineProps<{
    open: boolean;
    domainId?: string;
    domainName?: string;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    success: [];
}>();

interface CertItem {
    id: string;
    domain: string;
    cert_type: string;
    issued_by: string;
    status: string;
    issued_at: string | null;
}

interface TargetItem {
    id: string;
    name: string;
    target_type: string;
    config: string;
}

const loading = ref(false);
const deploying = ref(false);
const certificates = ref<CertItem[]>([]);
const targets = ref<TargetItem[]>([]);
const selectedCertId = ref("");
const selectedTargetIds = ref<string[]>([]);

const targetTypeLabels: Record<string, string> = {
    aliyun_cdn: "阿里云 CDN",
    baota: "宝塔面板",
};

const getTargetSummary = (t: TargetItem) => {
    try {
        const config = JSON.parse(t.config || "{}");
        if (t.target_type === "aliyun_cdn") return config.cdn_domain || "";
        if (t.target_type === "baota") return config.site_name || "";
    } catch { /* ignore */ }
    return "";
};

const selectedCertDomain = computed(() => {
    const cert = certificates.value.find(c => c.id === selectedCertId.value);
    if (cert) return cert.domain.replace(/^\*\./, "");
    return props.domainName?.replace(/^\*\./, "") || "";
});

const filteredTargets = computed(() => {
    const baseDomain = selectedCertDomain.value;
    if (!baseDomain) return targets.value;
    return targets.value.filter(t => {
        const summary = getTargetSummary(t).toLowerCase();
        return summary.includes(baseDomain.toLowerCase());
    });
});

watch(selectedCertId, () => {
    selectedTargetIds.value = [];
});

const allSelected = computed(() =>
    filteredTargets.value.length > 0 && filteredTargets.value.every(t => selectedTargetIds.value.includes(t.id))
);

const toggleAll = () => {
    if (allSelected.value) {
        selectedTargetIds.value = [];
    } else {
        selectedTargetIds.value = filteredTargets.value.map(t => t.id);
    }
};

const canDeploy = computed(() => selectedCertId.value && selectedTargetIds.value.length > 0);

watch(() => props.open, async (val) => {
    if (!val) return;
    selectedCertId.value = "";
    selectedTargetIds.value = [];
    loading.value = true;
    try {
        const [certRes, targetRes] = await Promise.all([
            getCertCertificates({
                domain_id: props.domainId || "",
                status: "active",
                page_size: 50,
            }),
            getCertDeployTargets(),
        ]);
        certificates.value = ((certRes as any).items || []);
        targets.value = ((targetRes as any).items || []);
        if (certificates.value.length > 0) {
            selectedCertId.value = certificates.value[0].id;
        }
    } catch {
        message.error("加载数据失败");
    } finally {
        loading.value = false;
    }
});

const toggleTarget = (id: string) => {
    const idx = selectedTargetIds.value.indexOf(id);
    if (idx >= 0) {
        selectedTargetIds.value.splice(idx, 1);
    } else {
        selectedTargetIds.value.push(id);
    }
};

const handleDeploy = async () => {
    if (!canDeploy.value) return;
    deploying.value = true;
    try {
        const res = await deployCertificate({
            certificate_id: selectedCertId.value,
            target_ids: selectedTargetIds.value,
        }) as any;

        const results = res.results || [];
        const successes = results.filter((r: any) => r.ok);
        const failures = results.filter((r: any) => !r.ok);

        if (failures.length === 0) {
            message.success(`证书已成功部署到 ${successes.length} 个目标`);
        } else if (successes.length > 0) {
            message.warning(`${successes.length} 个成功，${failures.length} 个失败`);
        } else {
            const msgs = failures.map((r: any) => `${r.target_name}: ${r.message}`).join("; ");
            message.error(`部署失败: ${msgs}`);
        }

        if (successes.length > 0) {
            emit("success");
            emit("update:open", false);
        }
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "部署失败");
    } finally {
        deploying.value = false;
    }
};
</script>

<template>
    <Dialog
        :open="open"
        title="部署证书"
        :width="540"
        :confirm-loading="deploying"
        ok-text="开始部署"
        @update:open="emit('update:open', $event)"
        @ok="handleDeploy"
    >
        <vort-spin :spinning="loading">
            <div v-if="certificates.length === 0 && !loading" class="py-6 text-center text-gray-400 text-sm">
                暂无可部署的有效证书，请先签发证书
            </div>

            <template v-if="certificates.length > 0">
                <!-- Certificate selection -->
                <div class="mb-5">
                    <label class="text-sm font-medium text-gray-700 mb-2 block">选择证书</label>
                    <vort-select v-model="selectedCertId" placeholder="选择要部署的证书" class="w-full">
                        <vort-select-option v-for="c in certificates" :key="c.id" :value="c.id">
                            {{ c.domain }} ({{ c.cert_type === "wildcard" ? "通配符" : "单域名" }}){{ c.issued_at ? ' ' + dayjs(c.issued_at).format('MM-DD HH:mm') : '' }}
                        </vort-select-option>
                    </vort-select>
                </div>

                <!-- Target selection -->
                <div>
                    <div class="flex items-center justify-between mb-2">
                        <label class="text-sm font-medium text-gray-700">选择部署目标</label>
                        <a v-if="filteredTargets.length > 1" class="text-xs text-blue-600 cursor-pointer" @click="toggleAll">
                            {{ allSelected ? '取消全选' : '全选' }}
                        </a>
                    </div>
                    <div v-if="targets.length === 0" class="text-sm text-gray-400 py-4 text-center bg-gray-50 rounded-lg">
                        暂无部署目标，请先在「部署目标」页面添加
                    </div>
                    <div v-else class="space-y-2">
                        <div v-if="selectedCertId && filteredTargets.length === 0" class="text-sm text-gray-400 py-4 text-center bg-gray-50 rounded-lg">
                            没有匹配当前域名的部署目标
                        </div>
                        <div
                            v-for="t in filteredTargets"
                            :key="t.id"
                            class="flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors"
                            :class="selectedTargetIds.includes(t.id) ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-gray-300'"
                            @click="toggleTarget(t.id)"
                        >
                            <vort-checkbox :checked="selectedTargetIds.includes(t.id)" @update:checked="toggleTarget(t.id)" />
                            <div class="flex-1 min-w-0">
                                <div class="text-sm font-medium text-gray-800">{{ t.name }}</div>
                                <div class="text-xs text-gray-400 mt-0.5">
                                    {{ targetTypeLabels[t.target_type] || t.target_type }}
                                    <template v-if="getTargetSummary(t)"> — {{ getTargetSummary(t) }}</template>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </template>
        </vort-spin>
    </Dialog>
</template>
