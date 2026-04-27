<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog } from "@openvort/vort-ui";
import { message } from "@openvort/vort-ui";
import { createCertDomain, updateCertDomain, getCertDnsProviders } from "@/api";
import { toTypedSchema } from "@vee-validate/zod";
import * as z from "zod";

const props = defineProps<{
    open: boolean;
    editData?: any;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    success: [];
}>();

const formRef = ref();
const loading = ref(false);
const dnsProviders = ref<any[]>([]);

const form = ref({
    domain: "",
    domain_type: "single",
    label: "",
    note: "",
    dns_provider_id: "",
});

const rules = toTypedSchema(
    z.object({
        domain: z.string().min(1, "请输入域名"),
    })
);

const isEdit = !!props.editData;

const inferredType = computed(() => {
    return form.value.domain.startsWith("*.") ? "wildcard" : "single";
});

watch(() => form.value.domain, () => {
    if (!props.editData) {
        form.value.domain_type = inferredType.value;
    }
});

watch(() => props.open, async (val) => {
    if (val) {
        if (props.editData) {
            form.value = {
                domain: props.editData.domain || "",
                domain_type: props.editData.domain_type || "single",
                label: props.editData.label || "",
                note: props.editData.note || "",
                dns_provider_id: props.editData.dns_provider_id || "",
            };
        } else {
            form.value = { domain: "", domain_type: "single", label: "", note: "", dns_provider_id: "" };
        }
        try {
            const res = await getCertDnsProviders() as any;
            dnsProviders.value = res.items || [];
        } catch {}
    }
});

const handleOk = async () => {
    try {
        await formRef.value?.validate();
    } catch {
        return;
    }
    loading.value = true;
    try {
        const data = { ...form.value, dns_provider_id: form.value.dns_provider_id || undefined };
        if (props.editData) {
            await updateCertDomain(props.editData.id, data);
            message.success("域名已更新");
        } else {
            await createCertDomain(data);
            message.success("域名已添加");
        }
        emit("success");
    } catch (e: any) {
        message.error(e?.response?.data?.detail || "操作失败");
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <Dialog
        :open="open"
        :title="editData ? '编辑域名' : '添加域名'"
        :width="520"
        :confirm-loading="loading"
        ok-text="保存"
        @update:open="emit('update:open', $event)"
        @ok="handleOk"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <vort-form-item label="域名" name="domain" required>
                <vort-input v-model="form.domain" placeholder="例如 example.com 或 *.example.com" :disabled="!!editData" />
            </vort-form-item>
            <vort-form-item label="类型">
                <vort-tag :color="form.domain_type === 'wildcard' ? 'blue' : 'default'" size="small">
                    {{ form.domain_type === 'wildcard' ? '通配符' : '单域名' }}
                </vort-tag>
                <span class="text-xs text-gray-400 ml-2">根据域名自动识别</span>
            </vort-form-item>
            <vort-form-item label="标签" name="label">
                <vort-input v-model="form.label" placeholder="分组标签，如：生产环境" />
            </vort-form-item>
            <vort-form-item label="DNS 服务商" name="dns_provider_id">
                <vort-select v-model="form.dns_provider_id" placeholder="选择 DNS 服务商" allow-clear>
                    <vort-select-option v-for="p in dnsProviders" :key="p.id" :value="p.id">
                        {{ p.name }} ({{ p.provider_type }})
                    </vort-select-option>
                </vort-select>
            </vort-form-item>
            <vort-form-item label="备注" name="note">
                <vort-textarea v-model="form.note" :rows="2" placeholder="可选备注信息" />
            </vort-form-item>
        </vort-form>
    </Dialog>
</template>
