<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { z } from "zod";
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores";
import openvortLogo from "@/assets/brand/openvort-logo.png";
import { User, Lock } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import { login, getSiteInfo } from "@/api";

const router = useRouter();
const userStore = useUserStore();

// Demo flag comes from backend at runtime (OPENVORT_IS_DEMO in .env), with
// build-time VITE_IS_DEMO kept as a fallback for local development.
const isDemo = ref(import.meta.env.VITE_IS_DEMO === "1");

const loading = ref(false);
const formRef = ref();
const formData = reactive({
    userId: "",
    password: "",
});
const rememberMe = ref(false);

const fillDemoCredentials = () => {
    formData.userId = "demo";
    formData.password = "openvort";
};

if (isDemo.value) {
    fillDemoCredentials();
}

onMounted(async () => {
    try {
        const info = await getSiteInfo();
        if (info?.is_demo) {
            isDemo.value = true;
            fillDemoCredentials();
        }
    } catch {
        // Older backends may not expose /auth/site-info; silently fall back to env flag.
    }
});

const loginValidationSchema = z.object({
    userId: z.string().min(1, '用户 ID 不能为空'),
    password: z.string().min(1, '密码不能为空'),
});

const handleLogin = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    loading.value = true;
    try {
        const res: any = await login(formData.userId, formData.password, rememberMe.value);
        userStore.setToken(res.token);
        userStore.setUserInfo({
            member_id: res.user.member_id,
            name: res.user.name,
            email: res.user.email || "",
            avatar_url: res.user.avatar_url || "",
            position: res.user.position || "",
            department: res.user.department || "",
            roles: res.user.roles || [],
            platform_accounts: res.user.platform_accounts || {}
        });
        userStore.setMustChangePassword(!!res.must_change_password);
        message.success("登录成功，您好，欢迎回来");
        router.push("/");
    } catch {
        message.error("用户不存在或密码错误");
    } finally {
        loading.value = false;
    }
};
</script>

<template>
    <div class="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
        <!-- Logo -->
        <div class="mb-8 flex justify-center">
            <img :src="openvortLogo" alt="OpenVort" class="h-14 w-auto object-contain" />
        </div>

        <p class="text-gray-400 text-sm mb-8">AI 研发工作流引擎</p>

        <!-- 登录卡片 -->
        <div class="w-full max-w-[420px] mx-4 md:mx-0 bg-white rounded-2xl shadow-xl p-8 md:p-10">
            <div class="mb-8 text-center">
                <h2 class="text-2xl font-semibold text-gray-800 mb-2">欢迎回来</h2>
                <p class="text-sm text-gray-400">请输入您的账号密码进行登录</p>
            </div>
            <VortForm ref="formRef" :model="formData" :rules="loginValidationSchema" layout="vertical" @keyup.enter="handleLogin" class="login-form">
                <VortFormItem
                    name="userId"
                    :required="true"
                    has-feedback
                    class="login-form-item"
                >
                    <VortInput
                        v-model="formData.userId"
                        placeholder="用户 ID / 姓名"
                        size="large"
                    >
                        <template #prefix>
                            <User :size="16" class="text-gray-400" />
                        </template>
                    </VortInput>
                </VortFormItem>
                <VortFormItem
                    name="password"
                    :required="true"
                    has-feedback
                    class="login-form-item"
                >
                    <VortInputPassword
                        v-model="formData.password"
                        placeholder="密码"
                        size="large"
                    >
                        <template #prefix>
                            <Lock :size="16" class="text-gray-400" />
                        </template>
                    </VortInputPassword>
                </VortFormItem>
                <div class="flex items-center mb-2 -mt-4">
                    <VortCheckbox v-model:checked="rememberMe">保持登录</VortCheckbox>
                </div>
                <VortFormItem class="login-form-item !mb-0 !mt-4">
                    <VortButton type="primary" block size="large" :loading="loading" class="!text-base font-medium" @click="handleLogin">
                        登录
                    </VortButton>
                </VortFormItem>
            </VortForm>
            <p v-if="isDemo" class="mt-6 text-center text-xs text-gray-400">
                演示账号：demo / openvort
            </p>
        </div>

        <div class="mt-8 text-center text-xs text-gray-400">
            Copyright © 2025 OpenVort
        </div>
    </div>
</template>

<style scoped>
.login-form .login-form-item {
    margin-bottom: 36px;
}

.login-form :deep(.vort-form-item-explain-row) {
    margin-top: 4px;
    margin-bottom: -28px;
}
</style>
