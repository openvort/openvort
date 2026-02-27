<script setup lang="ts">
import { ref, onMounted } from "vue";
import { getSettings, updateSettings, restartService } from "@/api";
import { message } from "@/components/vort/message";
import { Save, RotateCw } from "lucide-vue-next";

const loading = ref(false);
const saving = ref(false);

const form = ref({
    llm_model: "",
    llm_api_base: "",
    llm_max_tokens: 4096,
    llm_timeout: 120,
    session_max_messages: 50,
    session_max_age: 3600
});

onMounted(async () => {
    loading.value = true;
    try {
        const res: any = await getSettings();
        if (res) Object.assign(form.value, res);
    } catch { /* 使用默认值 */ }
    finally { loading.value = false; }
});

async function handleSave() {
    saving.value = true;
    try {
        await updateSettings(form.value);
        message.success("保存成功");
    } catch {
        message.error("保存失败");
    } finally { saving.value = false; }
}

const restarting = ref(false);
async function handleRestart() {
    restarting.value = true;
    try {
        await restartService();
        message.success("服务正在重启，请稍候...");
        // 等待后端重启完成后自动刷新页面
        setTimeout(() => { window.location.reload(); }, 5000);
    } catch {
        message.error("重启请求失败");
        restarting.value = false;
    }
}
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6 max-w-2xl">
            <h3 class="text-base font-medium text-gray-800 mb-6">系统设置</h3>

            <VortSpin :spinning="loading">
                <VortForm label-width="120px">
                    <h4 class="text-sm font-medium text-gray-700 mb-4">LLM 配置</h4>
                    <VortFormItem label="模型">
                        <VortInput v-model="form.llm_model" placeholder="claude-sonnet-4-20250514" />
                    </VortFormItem>
                    <VortFormItem label="API Base URL">
                        <VortInput v-model="form.llm_api_base" placeholder="https://api.anthropic.com" />
                    </VortFormItem>
                    <VortFormItem label="Max Tokens">
                        <VortInputNumber v-model="form.llm_max_tokens" :min="256" :max="200000" class="w-full" />
                    </VortFormItem>
                    <VortFormItem label="超时 (秒)">
                        <VortInputNumber v-model="form.llm_timeout" :min="10" :max="600" class="w-full" />
                    </VortFormItem>

                    <VortDivider />

                    <h4 class="text-sm font-medium text-gray-700 mb-4">会话配置</h4>
                    <VortFormItem label="最大消息数">
                        <VortInputNumber v-model="form.session_max_messages" :min="10" :max="200" class="w-full" />
                    </VortFormItem>
                    <VortFormItem label="会话超时 (秒)">
                        <VortInputNumber v-model="form.session_max_age" :min="300" :max="86400" class="w-full" />
                    </VortFormItem>

                    <VortFormItem>
                        <VortButton variant="primary" :loading="saving" @click="handleSave">
                            <Save :size="14" class="mr-1" /> 保存设置
                        </VortButton>
                    </VortFormItem>
                </VortForm>
            </VortSpin>
        </div>

        <div class="bg-white rounded-xl p-6 max-w-2xl">
            <h3 class="text-base font-medium text-gray-800 mb-2">服务管理</h3>
            <p class="text-sm text-gray-500 mb-4">重启后端服务，使配置或代码变更生效。</p>
            <VortButton variant="outline" :loading="restarting" @click="handleRestart">
                <RotateCw :size="14" class="mr-1" /> 重启服务
            </VortButton>
        </div>
    </div>
</template>
