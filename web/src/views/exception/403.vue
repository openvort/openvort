<script setup lang="ts">
import { useRouter } from "vue-router";
import { ShieldX } from "lucide-vue-next";
const router = useRouter();
</script>

<template>
    <div class="flex flex-col items-center justify-center min-h-[60vh]">
        <ShieldX :size="80" class="text-gray-200 mb-6" />
        <h1 class="text-5xl font-bold text-gray-800 mb-2">403</h1>
        <p class="text-lg text-gray-400 mb-8">抱歉，你无权访问该页面</p>
        <vort-button variant="primary" @click="router.push('/')">返回首页</vort-button>
    </div>
</template>
