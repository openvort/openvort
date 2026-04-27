<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog } from "@openvort/vort-ui";
import { message } from "@openvort/vort-ui";
import { getCertDomains, issueCertificate } from "@/api";

const props = defineProps<{
    open: boolean;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    success: [];
}>();

const loading = ref(false);
const loadingDomains = ref(false);
const domains = ref<any[]>([]);
const selectedDomainId = ref("");
const wildcard = ref(false);

const selectedDomain = computed(() => {
    return domains.value.find(d => d.id === selectedDomainId.value);
});

const isWildcardDomain = computed(() => {
    return selectedDomain.value?.domain_type === "wildcard";
});

const hasDnsProvider = computed(() => {
    return selectedDomain.value?.dns_provider_id;
});

watch(() => selectedDomainId.value, () => {
    wildcard.value = isWildcardDomain.value;
});

watch(() => props.open, async (val) => {
    if (val) {
        selectedDomainId.value = "";
        wildcard.value = false;
        loadingDomains.value = true;
        try {
            const res = await getCertDomains({ page: 1, page_size: 200 }) as any;
            domains.value = res.items || [];
        } catch {}
        loadingDomains.value = false;
    }
});

const handleOk = async () => {
    if (!selectedDomainId.value) {
        message.warning("请选择域名");
        return;
    }
    if (!hasDnsProvider.value) {
        message.warning("该域名未配置 DNS 服务商，请先在域名管理中关联 DNS 服务商");
        return;
    }

    loading.value = true;
    try {
        await issueCertificate({
            domain_id: selectedDomainId.value,
            wildcard: isWildcardDomain.value || wildcard.value,
        });
        message.success("证书签发成功");
        emit("success");
    } catch (e: any) {
        const detail = e?.response?.data?.detail || "签发失败";
        message.error(typeof detail === "string" ? detail : "签发失败");
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <Dialog
        :open="open"
        title="签发 SSL 证书"
        :width="520"
        :confirm-loading="loading"
        ok-text="签发"
        @update:open="emit('update:open', $event)"
        @ok="handleOk"
    >
        <vort-form label-width="100px">
            <vort-form-item label="选择域名" required>
                <vort-select
                    v-model="selectedDomainId"
                    placeholder="选择要签发证书的域名"
                    show-search
                    :loading="loadingDomains"
                >
                    <vort-select-option v-for="d in domains" :key="d.id" :value="d.id">
                        {{ d.domain }}{{ !d.dns_provider_id ? ' (未配DNS)' : '' }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <vort-form-item v-if="selectedDomain && !isWildcardDomain" label="通配符证书">
                <vort-switch v-model:checked="wildcard" />
                <span class="text-sm text-gray-500 ml-2">
                    {{ wildcard ? '签发 *.domain + domain 双证书' : '仅签发单域名证书' }}
                </span>
            </vort-form-item>

            <vort-form-item v-if="selectedDomain && isWildcardDomain" label="证书类型">
                <span class="text-sm text-gray-600">通配符证书（*.domain + domain）</span>
            </vort-form-item>
        </vort-form>

        <div v-if="selectedDomain && !hasDnsProvider" class="mt-3 p-3 bg-orange-50 rounded-lg text-sm text-orange-600">
            该域名未配置 DNS 服务商，Let's Encrypt 通过 DNS-01 验证需要 DNS API 权限。请先前往「域名管理」关联 DNS 服务商。
        </div>

        <div class="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-500 leading-relaxed">
            <p class="font-medium text-gray-600 mb-1">签发说明</p>
            <ul class="list-disc list-inside space-y-0.5">
                <li>使用 Let's Encrypt 免费签发 DV 级 SSL 证书</li>
                <li>通过 DNS-01 验证域名所有权，需要 DNS 服务商 API 权限</li>
                <li>证书有效期 90 天，到期前可续期</li>
                <li>签发完成后可在「证书总览」中查看和下载证书</li>
            </ul>
        </div>
    </Dialog>
</template>
