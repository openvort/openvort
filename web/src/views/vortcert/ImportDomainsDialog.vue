<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@openvort/vort-ui";
import { message } from "@openvort/vort-ui";
import { importCertDomains, getCertDnsProviders } from "@/api";

const props = defineProps<{
    open: boolean;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    success: [];
}>();

const loading = ref(false);
const domainsText = ref("");
const label = ref("");
const dnsProviderId = ref("");
const dnsProviders = ref<any[]>([]);

watch(() => props.open, async (val) => {
    if (val) {
        domainsText.value = "";
        label.value = "";
        dnsProviderId.value = "";
        try {
            const res = await getCertDnsProviders() as any;
            dnsProviders.value = res.items || [];
        } catch {}
    }
});

const handleOk = async () => {
    const domains = domainsText.value
        .split(/[\n,;]+/)
        .map(d => d.trim())
        .filter(Boolean);

    if (!domains.length) {
        message.warning("请输入至少一个域名");
        return;
    }

    loading.value = true;
    try {
        const res = await importCertDomains({
            domains,
            label: label.value,
            dns_provider_id: dnsProviderId.value || undefined,
        }) as any;
        message.success(`导入完成：新增 ${res.imported} 个，跳过 ${res.skipped} 个`);
        emit("success");
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "导入失败");
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <Dialog
        :open="open"
        title="批量导入域名"
        :width="560"
        :confirm-loading="loading"
        ok-text="导入"
        @update:open="emit('update:open', $event)"
        @ok="handleOk"
    >
        <vort-form label-width="100px">
            <vort-form-item label="域名列表" required>
                <vort-textarea
                    v-model="domainsText"
                    :rows="6"
                    placeholder="每行一个域名，支持逗号/分号分隔&#10;例如：&#10;example.com&#10;*.example.com&#10;api.example.com"
                />
                <div class="text-xs text-gray-400 mt-1">支持换行、逗号、分号分隔，以 *. 开头自动识别为通配符</div>
            </vort-form-item>
            <vort-form-item label="标签">
                <vort-input v-model="label" placeholder="统一标签（可选）" />
            </vort-form-item>
            <vort-form-item label="DNS 服务商">
                <vort-select v-model="dnsProviderId" placeholder="统一关联（可选）" allow-clear>
                    <vort-select-option v-for="p in dnsProviders" :key="p.id" :value="p.id">
                        {{ p.name }} ({{ p.provider_type }})
                    </vort-select-option>
                </vort-select>
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>
