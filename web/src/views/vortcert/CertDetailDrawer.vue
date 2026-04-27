<script setup lang="ts">
import { ref, watch } from "vue";
import { Drawer, message } from "@openvort/vort-ui";
import { getCertCertificates, getCertificateDetail, downloadCertificate, deleteCertificate } from "@/api";
import { Download, Copy, Trash2 } from "lucide-vue-next";
import dayjs from "dayjs";

const props = defineProps<{
    open: boolean;
    domainId: string;
    domainName: string;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
}>();

interface CertItem {
    id: string;
    domain: string;
    cert_type: string;
    issued_by: string;
    expires_at: string | null;
    status: string;
    issued_at: string | null;
    created_at: string | null;
}

interface CertDetail extends CertItem {
    cert_pem: string;
    key_pem: string;
    chain_pem: string;
}

const loading = ref(false);
const certs = ref<CertItem[]>([]);
const selectedCert = ref<CertDetail | null>(null);
const loadingDetail = ref(false);
const downloading = ref(false);
const activeTab = ref("cert");

watch(() => props.open, async (val) => {
    if (val && props.domainId) {
        loading.value = true;
        selectedCert.value = null;
        activeTab.value = "cert";
        try {
            const res = await getCertCertificates({ domain_id: props.domainId, page_size: 50 }) as any;
            certs.value = res.items || [];
            if (certs.value.length > 0) {
                await loadDetail(certs.value[0].id);
            }
        } catch {
            message.error("加载证书列表失败");
        } finally {
            loading.value = false;
        }
    }
});

const loadDetail = async (certId: string) => {
    loadingDetail.value = true;
    try {
        selectedCert.value = await getCertificateDetail(certId) as any;
    } catch {
        message.error("加载证书详情失败");
    } finally {
        loadingDetail.value = false;
    }
};

const copyToClipboard = async (text: string, label: string) => {
    try {
        await navigator.clipboard.writeText(text);
        message.success(`${label} 已复制到剪贴板`);
    } catch {
        message.error("复制失败");
    }
};

const handleDownload = async () => {
    if (!selectedCert.value) return;
    downloading.value = true;
    try {
        const res = await downloadCertificate(selectedCert.value.id) as any;
        const blob = new Blob([res], { type: "application/zip" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${selectedCert.value.domain.replace("*.", "wildcard.")}-cert.zip`;
        a.click();
        URL.revokeObjectURL(url);
        message.success("证书已下载");
    } catch {
        message.error("下载失败");
    } finally {
        downloading.value = false;
    }
};

const statusLabel = (s: string) => {
    const m: Record<string, string> = { active: "有效", expired: "已过期", revoked: "已吊销" };
    return m[s] || s;
};

const statusColor = (s: string) => {
    const m: Record<string, string> = { active: "green", expired: "red", revoked: "default" };
    return m[s] || "default";
};

const deleting = ref(false);
const handleDelete = async () => {
    if (!selectedCert.value) return;
    deleting.value = true;
    try {
        await deleteCertificate(selectedCert.value.id);
        message.success("证书已删除");
        certs.value = certs.value.filter(c => c.id !== selectedCert.value!.id);
        if (certs.value.length > 0) {
            await loadDetail(certs.value[0].id);
        } else {
            selectedCert.value = null;
        }
    } catch {
        message.error("删除失败");
    } finally {
        deleting.value = false;
    }
};
</script>

<template>
    <Drawer
        :open="open"
        :title="`证书详情 — ${domainName}`"
        :width="640"
        @update:open="emit('update:open', $event)"
    >
        <vort-spin :spinning="loading">
            <div v-if="certs.length === 0 && !loading" class="py-12 text-center text-gray-400">
                该域名暂无已签发的证书
            </div>

            <template v-if="certs.length > 1">
                <div class="mb-4">
                    <span class="text-sm text-gray-500 mr-2">选择证书</span>
                    <vort-select
                        :model-value="selectedCert?.id"
                        class="w-full"
                        @change="(v: string) => loadDetail(v)"
                    >
                        <vort-select-option v-for="c in certs" :key="c.id" :value="c.id">
                            {{ c.domain }} ({{ c.cert_type === 'wildcard' ? '通配符' : '单域名' }}) — {{ c.issued_at ? dayjs(c.issued_at).format('YYYY-MM-DD') : '未知' }}
                        </vort-select-option>
                    </vort-select>
                </div>
            </template>

            <vort-spin :spinning="loadingDetail">
                <template v-if="selectedCert">
                    <!-- Meta info -->
                    <div class="grid grid-cols-2 gap-4 mb-6">
                        <div>
                            <span class="text-sm text-gray-400">域名</span>
                            <div class="text-sm text-gray-800 mt-1 font-medium">{{ selectedCert.domain }}</div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">类型</span>
                            <div class="mt-1">
                                <vort-tag :color="selectedCert.cert_type === 'wildcard' ? 'blue' : 'default'" size="small">
                                    {{ selectedCert.cert_type === 'wildcard' ? '通配符' : '单域名' }}
                                </vort-tag>
                            </div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">签发机构</span>
                            <div class="text-sm text-gray-800 mt-1">{{ selectedCert.issued_by || '-' }}</div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">状态</span>
                            <div class="mt-1">
                                <vort-tag :color="statusColor(selectedCert.status)" size="small">{{ statusLabel(selectedCert.status) }}</vort-tag>
                            </div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">签发时间</span>
                            <div class="text-sm text-gray-800 mt-1">{{ selectedCert.issued_at ? dayjs(selectedCert.issued_at).format('YYYY-MM-DD HH:mm') : '-' }}</div>
                        </div>
                        <div>
                            <span class="text-sm text-gray-400">到期时间</span>
                            <div class="text-sm text-gray-800 mt-1">{{ selectedCert.expires_at ? dayjs(selectedCert.expires_at).format('YYYY-MM-DD HH:mm') : '-' }}</div>
                        </div>
                    </div>

                    <!-- PEM tabs -->
                    <vort-tabs v-model:activeKey="activeTab" type="line">
                        <vort-tab-pane tab-key="cert" tab="证书 (CRT)">
                            <div class="relative">
                                <vort-button
                                    size="small"
                                    class="absolute top-2 right-2 z-10"
                                    :disabled="!selectedCert.cert_pem"
                                    @click="copyToClipboard(selectedCert.cert_pem, '证书')"
                                >
                                    <Copy :size="12" class="mr-1" /> 复制
                                </vort-button>
                                <pre v-if="selectedCert.cert_pem" class="bg-gray-50 border border-gray-200 rounded-lg p-4 pr-20 text-xs text-gray-600 overflow-auto max-h-[300px] whitespace-pre-wrap break-all font-mono">{{ selectedCert.cert_pem }}</pre>
                                <div v-else class="bg-gray-50 rounded-lg p-6 text-center text-gray-400 text-sm">暂无证书内容</div>
                            </div>
                        </vort-tab-pane>
                        <vort-tab-pane tab-key="key" tab="私钥 (KEY)">
                            <div class="relative">
                                <vort-button
                                    size="small"
                                    class="absolute top-2 right-2 z-10"
                                    :disabled="!selectedCert.key_pem"
                                    @click="copyToClipboard(selectedCert.key_pem, '私钥')"
                                >
                                    <Copy :size="12" class="mr-1" /> 复制
                                </vort-button>
                                <pre v-if="selectedCert.key_pem" class="bg-gray-50 border border-gray-200 rounded-lg p-4 pr-20 text-xs text-gray-600 overflow-auto max-h-[300px] whitespace-pre-wrap break-all font-mono">{{ selectedCert.key_pem }}</pre>
                                <div v-else class="bg-gray-50 rounded-lg p-6 text-center text-gray-400 text-sm">暂无私钥内容</div>
                            </div>
                        </vort-tab-pane>
                        <vort-tab-pane tab-key="chain" tab="证书链 (Chain)">
                            <div class="relative">
                                <vort-button
                                    size="small"
                                    class="absolute top-2 right-2 z-10"
                                    :disabled="!selectedCert.chain_pem"
                                    @click="copyToClipboard(selectedCert.chain_pem, '证书链')"
                                >
                                    <Copy :size="12" class="mr-1" /> 复制
                                </vort-button>
                                <pre v-if="selectedCert.chain_pem" class="bg-gray-50 border border-gray-200 rounded-lg p-4 pr-20 text-xs text-gray-600 overflow-auto max-h-[300px] whitespace-pre-wrap break-all font-mono">{{ selectedCert.chain_pem }}</pre>
                                <div v-else class="bg-gray-50 rounded-lg p-6 text-center text-gray-400 text-sm">暂无证书链内容</div>
                            </div>
                        </vort-tab-pane>
                    </vort-tabs>

                    <!-- Actions -->
                    <div class="mt-4 flex justify-between">
                        <vort-popconfirm title="确认删除该证书？关联的部署记录也将一并删除。" @confirm="handleDelete">
                            <vort-button danger :loading="deleting">
                                <Trash2 :size="14" class="mr-1" /> 删除证书
                            </vort-button>
                        </vort-popconfirm>
                        <vort-button variant="primary" :loading="downloading" @click="handleDownload">
                            <Download :size="14" class="mr-1" /> 下载证书文件 (.zip)
                        </vort-button>
                    </div>
                </template>
            </vort-spin>
        </vort-spin>
    </Drawer>
</template>
