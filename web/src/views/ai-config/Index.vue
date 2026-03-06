<script setup lang="ts">
import { ref } from "vue";
import { RotateCw } from "lucide-vue-next";
import { restartService } from "@/api";
import { message } from "@/components/vort";
import ModelLibrary from "./ModelLibrary.vue";
import ChatModel from "./ChatModel.vue";
import CodingTools from "./CodingTools.vue";
import VoiceProviders from "./VoiceProviders.vue";

const activeTab = ref("models");

const restarting = ref(false);
async function handleRestart() {
    restarting.value = true;
    try {
        await restartService();
        message.success("服务正在重启，请稍候...");
        setTimeout(() => {
            window.location.reload();
        }, 5000);
    } catch {
        message.error("重启请求失败");
        restarting.value = false;
    }
}
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <div class="flex items-center justify-between mb-6">
                <h3 class="text-base font-medium text-gray-800">AI 配置</h3>
                <VortButton :loading="restarting" @click="handleRestart">
                    <RotateCw :size="14" class="mr-1" /> 重启服务
                </VortButton>
            </div>

            <VortTabs v-model:activeKey="activeTab">
                <VortTabPane tab-key="models" tab="模型库">
                    <div class="mt-4">
                        <ModelLibrary />
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="chat" tab="对话模型">
                    <div class="mt-4">
                        <ChatModel />
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="coding" tab="编码工具">
                    <div class="mt-4">
                        <CodingTools />
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="voice" tab="语音服务">
                    <div class="mt-4">
                        <VoiceProviders />
                    </div>
                </VortTabPane>
            </VortTabs>
        </div>
    </div>
</template>
