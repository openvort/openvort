<script setup lang="ts">
import { ref, computed } from "vue";
import { Monitor } from "lucide-vue-next";

const props = defineProps<{ nodeId: string }>();

const novncPort = ref(6080);
const fullscreen = ref(false);

const novncUrl = computed(() => {
    const proto = location.protocol === "https:" ? "https:" : "http:";
    const host = location.hostname;
    return `${proto}//${host}:${novncPort.value}/vnc.html?autoconnect=true&resize=scale`;
});
</script>

<template>
    <div class="browser-preview">
        <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2 text-sm text-gray-500">
                <Monitor :size="14" />
                <span>noVNC 浏览器实时预览</span>
            </div>
            <VortButton size="small" @click="fullscreen = !fullscreen">
                {{ fullscreen ? "退出全屏" : "全屏" }}
            </VortButton>
        </div>
        <div class="text-xs text-gray-400 mb-2">
            需要先为该节点启动浏览器沙箱容器（ghcr.io/openvort/browser-sandbox 镜像）。
            启动后可在此处实时观看 AI 员工的浏览器操作，也可直接手动操作接管。
        </div>
        <iframe
            :src="novncUrl"
            :class="['novnc-frame', { 'novnc-fullscreen': fullscreen }]"
            allow="clipboard-read; clipboard-write"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
        />
    </div>
</template>

<style scoped>
.novnc-frame {
    width: 100%;
    height: 560px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #1e1e2e;
}
.novnc-fullscreen {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 9999;
    border-radius: 0;
}
</style>
