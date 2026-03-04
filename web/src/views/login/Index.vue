<script setup lang="ts">
import { ref, reactive } from "vue";
import { z } from "zod";
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores";
import { User, Lock } from "lucide-vue-next";
import { message } from "@/components/vort/message";
import { login } from "@/api";

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);
const formRef = ref();
const formData = reactive({
    userId: "",
    password: "",
});

const loginValidationSchema = z.object({
    userId: z.string().min(1, '用户 ID 不能为空'),
    password: z.string().min(1, '密码不能为空'),
});

const handleLogin = async () => {
    try { await formRef.value?.validate(); } catch { return; }
    loading.value = true;
    try {
        const res: any = await login(formData.userId, formData.password);
        userStore.setToken(res.token);
        userStore.setUserInfo({
            member_id: res.user.member_id,
            name: res.user.name,
            email: res.user.email || "",
            position: res.user.position || "",
            department: res.user.department || "",
            roles: res.user.roles || [],
            platform_accounts: res.user.platform_accounts || {}
        });
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
        <div class="flex items-center mb-8">
            <div class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center mr-3">
                <span class="text-white font-bold text-lg">O</span>
            </div>
            <h1 class="text-2xl font-semibold text-gray-800">OpenVort</h1>
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
                <VortFormItem class="login-form-item !mb-0 !mt-4">
                    <VortButton type="primary" block size="large" :loading="loading" class="!text-base font-medium" @click="handleLogin">
                        登录
                    </VortButton>
                </VortFormItem>
            </VortForm>
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
