<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog } from "@openvort/vort-ui";
import { message } from "@openvort/vort-ui";
import { createCertDnsProvider, updateCertDnsProvider } from "@/api";
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
const editingKey = ref(false);
const editingSecret = ref(false);

const providerTypes = [
    { value: "aliyun", label: "阿里云" },
    { value: "tencent", label: "腾讯云" },
    { value: "cloudflare", label: "Cloudflare" },
    { value: "namesilo", label: "NameSilo" },
    { value: "godaddy", label: "GoDaddy" },
    { value: "namecheap", label: "Namecheap" },
    { value: "aws", label: "AWS Route53" },
];

const form = ref({
    name: "",
    provider_type: "aliyun",
    api_key: "",
    api_secret: "",
});

const rules = toTypedSchema(
    z.object({
        name: z.string().min(1, "请输入名称"),
        provider_type: z.string().min(1, "请选择类型"),
    })
);

watch(() => props.open, (val) => {
    if (val) {
        editingKey.value = false;
        editingSecret.value = false;
        if (props.editData) {
            form.value = {
                name: props.editData.name || "",
                provider_type: props.editData.provider_type || "aliyun",
                api_key: "",
                api_secret: "",
            };
        } else {
            form.value = { name: "", provider_type: "aliyun", api_key: "", api_secret: "" };
        }
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
        const data: any = {
            name: form.value.name,
            provider_type: form.value.provider_type,
        };
        if (form.value.api_key) data.api_key = form.value.api_key;
        if (form.value.api_secret) data.api_secret = form.value.api_secret;

        if (props.editData) {
            await updateCertDnsProvider(props.editData.id, data);
            message.success("DNS 服务商已更新");
        } else {
            await createCertDnsProvider(data);
            message.success("DNS 服务商已添加");
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
        :title="editData ? '编辑 DNS 服务商' : '添加 DNS 服务商'"
        :width="520"
        :confirm-loading="loading"
        ok-text="保存"
        @update:open="emit('update:open', $event)"
        @ok="handleOk"
    >
        <vort-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <vort-form-item label="名称" name="name" required>
                <vort-input v-model="form.name" placeholder="例如：阿里云主账号" />
            </vort-form-item>
            <vort-form-item label="服务商类型" name="provider_type" required>
                <vort-select v-model="form.provider_type">
                    <vort-select-option v-for="t in providerTypes" :key="t.value" :value="t.value">
                        {{ t.label }}
                    </vort-select-option>
                </vort-select>
            </vort-form-item>
            <vort-form-item label="API Key" name="api_key">
                <template v-if="editData && !editingKey">
                    <span class="text-sm text-gray-600">{{ editData.api_key_masked || '未设置' }}</span>
                    <a class="text-sm text-blue-600 cursor-pointer ml-3" @click="editingKey = true">编辑</a>
                </template>
                <template v-else>
                    <div class="flex items-center gap-2 w-full">
                        <vort-input-password v-model="form.api_key" placeholder="输入 API Key" class="flex-1" />
                        <a v-if="editData" class="text-sm text-gray-500 cursor-pointer whitespace-nowrap" @click="editingKey = false; form.api_key = ''">取消</a>
                    </div>
                </template>
            </vort-form-item>
            <vort-form-item label="API Secret" name="api_secret">
                <template v-if="editData && !editingSecret">
                    <span class="text-sm text-gray-600">{{ editData.api_secret_masked || '未设置' }}</span>
                    <a class="text-sm text-blue-600 cursor-pointer ml-3" @click="editingSecret = true">编辑</a>
                </template>
                <template v-else>
                    <div class="flex items-center gap-2 w-full">
                        <vort-input-password v-model="form.api_secret" placeholder="输入 API Secret" class="flex-1" />
                        <a v-if="editData" class="text-sm text-gray-500 cursor-pointer whitespace-nowrap" @click="editingSecret = false; form.api_secret = ''">取消</a>
                    </div>
                </template>
            </vort-form-item>
        </vort-form>

        <div class="mt-4 p-3 bg-gray-50 rounded-lg text-xs text-gray-500 leading-relaxed">
            <p class="font-medium text-gray-600 mb-1">配置说明</p>
            <p v-if="form.provider_type === 'aliyun'">阿里云：需要 AccessKey ID 和 AccessKey Secret，建议使用 RAM 子账号并仅授予 DNS 管理权限。</p>
            <p v-else-if="form.provider_type === 'tencent'">腾讯云：需要 SecretId 和 SecretKey，建议使用 CAM 子账号。</p>
            <p v-else-if="form.provider_type === 'cloudflare'">Cloudflare：API Key 填 Global API Key，API Secret 填登录邮箱。或使用 API Token（仅需 DNS 编辑权限）。</p>
            <p v-else>请填写对应平台的 API 凭证，用于 DNS-01 验证签发 SSL 证书。</p>
        </div>
    </Dialog>
</template>
