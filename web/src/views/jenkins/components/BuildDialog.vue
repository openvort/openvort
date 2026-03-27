<template>
    <Dialog :open="open" @update:open="$emit('update:open', $event)">
        <template #title>构建 {{ jobName }}</template>

        <!-- Parameterized build -->
        <div v-if="parameters.length > 0" class="space-y-4">
            <div v-for="param in parameters" :key="param.name">
                <label class="block text-sm font-medium text-gray-700 mb-1">
                    {{ param.name }}
                    <span v-if="param.description" class="font-normal text-gray-400 ml-1">{{ param.description }}</span>
                </label>

                <!-- Choice / branch parameter: searchable select -->
                <Select
                    v-if="param.choices && param.choices.length > 0"
                    :model-value="formValues[param.name] ?? param.default ?? ''"
                    :options="param.choices.map((c: string) => ({ label: c, value: c }))"
                    show-search
                    placeholder="请选择"
                    @update:model-value="formValues[param.name] = $event"
                />

                <!-- Boolean parameter -->
                <div v-else-if="param.type === 'BooleanParameterDefinition'" class="flex items-center gap-2">
                    <Switch
                        :model-value="formValues[param.name] === 'true' || formValues[param.name] === true"
                        @update:model-value="formValues[param.name] = String($event)"
                    />
                </div>

                <!-- Text parameter -->
                <Textarea
                    v-else-if="param.type === 'TextParameterDefinition'"
                    :model-value="formValues[param.name] ?? param.default ?? ''"
                    :rows="3"
                    @update:model-value="formValues[param.name] = $event"
                />

                <!-- String / other parameter -->
                <Input
                    v-else
                    :model-value="formValues[param.name] ?? param.default ?? ''"
                    @update:model-value="formValues[param.name] = $event"
                />
            </div>
        </div>

        <!-- No-parameter build: confirm message -->
        <div v-else class="py-4 text-sm text-gray-600">
            即将触发 Job「<span class="font-medium text-gray-800">{{ jobName }}</span>」的构建，该 Job 无需构建参数，点击确认后将立即开始构建。
        </div>

        <template #footer>
            <div class="flex justify-end gap-2">
                <VortButton @click="$emit('update:open', false)">取消</VortButton>
                <VortButton variant="primary" :loading="triggering" @click="handleBuild">确认构建</VortButton>
            </div>
        </template>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { Dialog, Input, Select, Switch, Textarea } from "@openvort/vort-ui";
import type { JenkinsParameterDef } from "../types";

const props = defineProps<{
    open: boolean;
    jobName: string;
    parameters: JenkinsParameterDef[];
    triggering: boolean;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "confirm", params: Record<string, any>): void;
}>();

const formValues = ref<Record<string, any>>({});

watch(() => props.open, (val) => {
    if (val) {
        const defaults: Record<string, any> = {};
        for (const p of props.parameters) {
            defaults[p.name] = p.default ?? "";
        }
        formValues.value = defaults;
    }
});

function handleBuild() {
    emit("confirm", { ...formValues.value });
}
</script>
