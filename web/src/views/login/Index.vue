<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useUserStore } from "@/stores";
import { User, Lock } from "lucide-vue-next";
import { message } from "@/components/vort/message";
import { login } from "@/api";

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);
const userId = ref("");
const password = ref("");

const handleLogin = async () => {
    if (!userId.value) {
        message.warning("请输入用户 ID");
        return;
    }
    if (!password.value) {
        message.warning("请输入密码");
        return;
    }
    loading.value = true;
    try {
        const res: any = await login(userId.value, password.value);
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
            <h2 class="text-lg font-medium text-gray-700 mb-6 text-center">登录</h2>
            <div class="space-y-5">
                <VortInput
                    v-model="userId"
                    placeholder="用户 ID / 姓名"
                    size="large"
                >
                    <template #prefix>
                        <User :size="16" class="text-gray-400" />
                    </template>
                </VortInput>
                <VortInputPassword
                    v-model="password"
                    placeholder="密码"
                    size="large"
                    @press-enter="handleLogin"
                >
                    <template #prefix>
                        <Lock :size="16" class="text-gray-400" />
                    </template>
                </VortInputPassword>
            </div>

            <VortButton type="primary" block size="large" :loading="loading" class="mt-8" @click="handleLogin">
                登 录
            </VortButton>
        </div>

        <div class="mt-8 text-center text-xs text-gray-400">
            Copyright © 2025 OpenVort
        </div>
    </div>
</template>
