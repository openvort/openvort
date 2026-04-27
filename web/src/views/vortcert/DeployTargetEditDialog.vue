<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { Dialog, message } from "@openvort/vort-ui";
import { createCertDeployTarget, updateCertDeployTarget, getCertDnsProviders } from "@/api";
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
const editingApiKey = ref(false);
const dnsProviders = ref<any[]>([]);

const targetTypes = [
    { value: "aliyun_cdn", label: "阿里云 CDN" },
    { value: "baota", label: "宝塔面板" },
];

const form = ref({
    name: "",
    target_type: "aliyun_cdn",
    cdn_domain: "",
    panel_url: "",
    site_name: "",
    api_key: "",
    dns_provider_id: "",
});

const rules = toTypedSchema(
    z.object({
        name: z.string().min(1, "请输入名称"),
        target_type: z.string().min(1, "请选择类型"),
    })
);

const isAliyunCdn = computed(() => form.value.target_type === "aliyun_cdn");
const isBaota = computed(() => form.value.target_type === "baota");

watch(() => props.open, async (val) => {
    if (val) {
        editingApiKey.value = false;
        if (props.editData) {
            const config = JSON.parse(props.editData.config || "{}");
            form.value = {
                name: props.editData.name || "",
                target_type: props.editData.target_type || "aliyun_cdn",
                cdn_domain: config.cdn_domain || "",
                panel_url: config.panel_url || "",
                site_name: config.site_name || "",
                api_key: "",
                dns_provider_id: props.editData.dns_provider_id || "",
            };
        } else {
            form.value = {
                name: "", target_type: "aliyun_cdn", cdn_domain: "",
                panel_url: "", site_name: "", api_key: "", dns_provider_id: "",
            };
        }
        try {
            const res = await getCertDnsProviders() as any;
            dnsProviders.value = (res.items || []).filter((p: any) => p.provider_type === "aliyun");
        } catch { /* ignore */ }
    }
});

const handleOk = async () => {
    try { await formRef.value?.validate(); } catch { return; }

    if (isAliyunCdn.value && !form.value.cdn_domain) {
        message.error("请输入 CDN 域名");
        return;
    }
    if (isAliyunCdn.value && !form.value.dns_provider_id) {
        message.error("请选择 DNS 服务商（用于获取阿里云 API 凭证）");
        return;
    }
    if (isBaota.value && (!form.value.panel_url || !form.value.site_name)) {
        message.error("请填写面板地址和站点名称");
        return;
    }
    if (isBaota.value && !props.editData && !form.value.api_key) {
        message.error("请输入宝塔面板 API Key");
        return;
    }

    loading.value = true;
    try {
        let config: Record<string, string> = {};
        if (isAliyunCdn.value) {
            config = { cdn_domain: form.value.cdn_domain };
        } else if (isBaota.value) {
            config = { panel_url: form.value.panel_url, site_name: form.value.site_name };
        }

        const data: any = {
            name: form.value.name,
            target_type: form.value.target_type,
            config: JSON.stringify(config),
            dns_provider_id: isAliyunCdn.value ? form.value.dns_provider_id : "",
        };
        if (form.value.api_key) data.api_key = form.value.api_key;

        if (props.editData) {
            await updateCertDeployTarget(props.editData.id, data);
            message.success("部署目标已更新");
        } else {
            await createCertDeployTarget(data);
            message.success("部署目标已添加");
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
        :title="editData ? '编辑部署目标' : '添加部署目标'"
        :width="520"
        :confirm-loading="loading"
        ok-text="保存"
        @update:open="emit('update:open', $event)"
        @ok="handleOk"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="120px">
            <vort-form-item label="名称" name="name" required>
                <vort-input v-model="form.name" placeholder="例如：阿里云 CDN 主站" />
            </vort-form-item>
            <vort-form-item label="目标类型" name="target_type" required>
                <vort-select v-model="form.target_type">
                    <vort-select-option v-for="t in targetTypes" :key="t.value" :value="t.value">
                        {{ t.label }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>

            <!-- Aliyun CDN fields -->
            <template v-if="isAliyunCdn">
                <vort-form-item label="CDN 域名" required>
                    <vort-input v-model="form.cdn_domain" placeholder="例如：cdn.example.com" />
                </vort-form-item>
                <vort-form-item label="DNS 服务商" required>
                    <vort-select v-model="form.dns_provider_id" placeholder="选择阿里云 DNS 服务商">
                        <vort-select-option v-for="p in dnsProviders" :key="p.id" :value="p.id">
                            {{ p.name }}
                        </vort-select-option>
                    </vort-select>
                    <div class="text-xs text-gray-400 mt-1">复用 DNS 配置中的阿里云 AccessKey 进行 CDN API 调用</div>
                </vort-form-item>
            </template>

            <!-- BaoTa fields -->
            <template v-if="isBaota">
                <vort-form-item label="面板地址" required>
                    <vort-input v-model="form.panel_url" placeholder="例如：http://47.xx.xx.xx:8888" />
                </vort-form-item>
                <vort-form-item label="站点名称" required>
                    <vort-input v-model="form.site_name" placeholder="宝塔面板中的站点名称" />
                </vort-form-item>
                <vort-form-item label="API Key">
                    <template v-if="editData && !editingApiKey">
                        <span class="text-sm text-gray-600">{{ editData.api_key_masked || '未设置' }}</span>
                        <a class="text-sm text-blue-600 cursor-pointer ml-3" @click="editingApiKey = true">编辑</a>
                    </template>
                    <template v-else>
                        <div class="flex items-center gap-2 w-full">
                            <vort-input-password v-model="form.api_key" placeholder="宝塔面板 API Key" class="flex-1" />
                            <a v-if="editData" class="text-sm text-gray-500 cursor-pointer whitespace-nowrap" @click="editingApiKey = false; form.api_key = ''">取消</a>
                        </div>
                    </template>
                </vort-form-item>
            </template>
        </vort-form>

        <div class="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-500 leading-relaxed">
            <p class="font-medium text-gray-600 mb-1">配置说明</p>
            <p v-if="isAliyunCdn">阿里云 CDN：通过 SetCdnDomainSSLCertificate API 推送证书。需要 CDN 域名和阿里云 AccessKey（复用 DNS 服务商配置）。</p>
            <p v-else-if="isBaota">宝塔面板：通过面板 API 设置站点 SSL 证书。需在宝塔「面板设置 → API 接口」中开启 API 并将 OpenVort 服务器 IP 加入白名单。</p>
        </div>
    </Dialog>
</template>
