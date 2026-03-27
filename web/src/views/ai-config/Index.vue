<script setup lang="ts">
import { ref } from "vue";
import { RotateCw } from "lucide-vue-next";
import { restartService } from "@/api";
import { message } from "@openvort/vort-ui";
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
                <VortTabPane tab-key="models" tab="模型管理">
                    <div class="mt-4">
                        <ModelLibrary />
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="chat" tab="LLM 对话">
                    <div class="mt-4">
                        <ChatModel />
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="coding" tab="Coding CLI">
                    <div class="mt-4">
                        <CodingTools />
                    </div>
                </VortTabPane>

                <VortTabPane tab-key="voice" tab="语音识别">
                    <div class="mt-4">
                        <VoiceProviders />
                    </div>
                </VortTabPane>
            </VortTabs>
        </div>
    </div>
</template>
