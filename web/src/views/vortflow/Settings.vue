<script setup lang="ts">
import { ref } from "vue";
import TagSettings from "./TagSettings.vue";
import StatusSettings from "./StatusSettings.vue";
import TemplateSettings from "./TemplateSettings.vue";

const activeTab = ref("tags");
</script>

<template>
    <div class="space-y-4">
        <div class="bg-white rounded-xl p-6">
            <vort-tabs v-model:active-key="activeTab" :bordered="false">
                <vort-tab-pane tab-key="tags" tab="标签设置">
                    <TagSettings />
                </vort-tab-pane>
                <vort-tab-pane tab-key="statuses" tab="状态设置">
                    <StatusSettings />
                </vort-tab-pane>
                <vort-tab-pane tab-key="templates" tab="内容模板">
                    <TemplateSettings />
                </vort-tab-pane>
            </vort-tabs>
        </div>
    </div>
</template>
