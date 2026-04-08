<script setup lang="ts">
import { ref, reactive, watch, onMounted, computed } from "vue";
import { Bell, Play, Clock, CalendarDays, AlertTriangle, Zap } from "lucide-vue-next";
import { message } from "@openvort/vort-ui";
import {
    getVortflowProjects,
    listVortflowReminderSettings,
    bulkUpdateVortflowReminderSettings,
    testVortflowReminder,
} from "@/api";

interface SceneConfig {
    enabled: boolean;
    time?: string;
    day?: number;
}
interface ReminderForm {
    enabled: boolean;
    scenes: Record<string, SceneConfig>;
    work_days: string;
    near_deadline_days: number;
    ai_suggestion: boolean;
    skip_empty: boolean;
    min_threshold: number;
}

const projects = ref<{ id: string; name: string }[]>([]);
const selectedProjectIds = ref<string[]>([]);
const loading = ref(false);
const saving = ref(false);
const testing = ref(false);

const form = reactive<ReminderForm>({
    enabled: false,
    scenes: {
        morning: { enabled: true, time: "09:00" },
        afternoon: { enabled: false, time: "14:00" },
        weekly: { enabled: true, time: "17:00", day: 5 },
        instant: { enabled: true },
    },
    work_days: "1,2,3,4,5",
    near_deadline_days: 3,
    ai_suggestion: true,
    skip_empty: true,
    min_threshold: 0,
});

const workDayChecks = reactive<Record<number, boolean>>({
    1: true, 2: true, 3: true, 4: true, 5: true, 6: false, 7: false,
});

const allChecked = computed({
    get: () => projects.value.length > 0 && selectedProjectIds.value.length === projects.value.length,
    set: (val: boolean) => {
        selectedProjectIds.value = val ? projects.value.map(p => p.id) : [];
    },
});

const indeterminate = computed(() =>
    selectedProjectIds.value.length > 0 && selectedProjectIds.value.length < projects.value.length
);

const timeOptions = [
    "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00",
    "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00",
    "16:30", "17:00", "17:30", "18:00",
];
const morningTimeOptions = timeOptions.filter(t => t >= "08:00" && t <= "11:00");
const afternoonTimeOptions = timeOptions.filter(t => t >= "13:00" && t <= "16:00");
const weeklyTimeOptions = timeOptions.filter(t => t >= "15:00" && t <= "18:00");

const weekDayOptions = [
    { label: "周一", value: 1 },
    { label: "周二", value: 2 },
    { label: "周三", value: 3 },
    { label: "周四", value: 4 },
    { label: "周五", value: 5 },
    { label: "周六", value: 6 },
    { label: "周日", value: 7 },
];

const nearDaysOptions = [1, 2, 3, 5, 7];
const thresholdOptions = [0, 1, 2, 3, 5];

function syncWorkDaysFromString(s: string) {
    const nums = new Set(s.split(",").map(d => parseInt(d.trim())).filter(Boolean));
    for (let i = 1; i <= 7; i++) workDayChecks[i] = nums.has(i);
}

function workDaysToString(): string {
    return Object.entries(workDayChecks)
        .filter(([, v]) => v)
        .map(([k]) => k)
        .join(",");
}

function toggleProject(projectId: string) {
    const idx = selectedProjectIds.value.indexOf(projectId);
    if (idx >= 0) {
        selectedProjectIds.value.splice(idx, 1);
    } else {
        selectedProjectIds.value.push(projectId);
    }
}

async function loadData() {
    loading.value = true;
    try {
        const [projRes, settingsRes] = await Promise.all([
            getVortflowProjects(),
            listVortflowReminderSettings(),
        ]) as [any, any];

        projects.value = (projRes?.items || []).map((p: any) => ({ id: p.id, name: p.name }));

        const items = settingsRes?.items || [];
        const enabledIds = items.filter((s: any) => s.enabled).map((s: any) => s.project_id);
        selectedProjectIds.value = enabledIds;

        const firstEnabled = items.find((s: any) => s.enabled);
        if (firstEnabled) {
            form.enabled = true;
            form.scenes = firstEnabled.scenes || form.scenes;
            form.work_days = firstEnabled.work_days || "1,2,3,4,5";
            form.near_deadline_days = firstEnabled.near_deadline_days ?? 3;
            form.ai_suggestion = firstEnabled.ai_suggestion ?? true;
            form.skip_empty = firstEnabled.skip_empty ?? true;
            form.min_threshold = firstEnabled.min_threshold ?? 0;
            syncWorkDaysFromString(form.work_days);
        } else {
            form.enabled = false;
        }
    } catch {
        message.error("加载提醒设置失败");
    } finally {
        loading.value = false;
    }
}

async function handleSave() {
    saving.value = true;
    try {
        form.work_days = workDaysToString();
        await bulkUpdateVortflowReminderSettings({
            project_ids: selectedProjectIds.value,
            enabled: form.enabled,
            scenes: form.scenes,
            work_days: form.work_days,
            near_deadline_days: form.near_deadline_days,
            ai_suggestion: form.ai_suggestion,
            skip_empty: form.skip_empty,
            min_threshold: form.min_threshold,
        });
        message.success("提醒设置已保存");
    } catch {
        message.error("保存失败");
    } finally {
        saving.value = false;
    }
}

async function handleTest(scene: string) {
    if (!selectedProjectIds.value.length) {
        message.warning("请先选择至少一个项目");
        return;
    }
    testing.value = true;
    try {
        await testVortflowReminder(selectedProjectIds.value[0], scene);
        message.success("测试提醒已发送，请查看 IM 消息");
    } catch {
        message.error("发送测试提醒失败");
    } finally {
        testing.value = false;
    }
}

function handleReset() {
    form.enabled = false;
    form.scenes = {
        morning: { enabled: true, time: "09:00" },
        afternoon: { enabled: false, time: "14:00" },
        weekly: { enabled: true, time: "17:00", day: 5 },
        instant: { enabled: true },
    };
    form.work_days = "1,2,3,4,5";
    form.near_deadline_days = 3;
    form.ai_suggestion = true;
    form.skip_empty = true;
    form.min_threshold = 0;
    selectedProjectIds.value = [];
    syncWorkDaysFromString(form.work_days);
}

onMounted(() => loadData());
</script>

<template>
    <vort-spin :spinning="loading">
        <div class="space-y-6">
            <!-- Master toggle -->
            <div class="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg">
                <div class="flex items-center gap-2">
                    <Bell :size="18" class="text-gray-600" />
                    <span class="text-sm font-medium text-gray-800">定时提醒</span>
                </div>
                <vort-switch v-model:checked="form.enabled" />
            </div>
            <p class="text-xs text-gray-400 -mt-4 ml-1">
                开启后，系统将按设定时间向勾选项目的成员推送工作项提醒。成员可在个人设置中调整接收偏好。
            </p>

            <!-- Project checkboxes -->
            <div class="space-y-2">
                <div class="flex items-center justify-between">
                    <h4 class="text-sm font-medium text-gray-700">提醒项目</h4>
                    <label class="flex items-center gap-1.5 cursor-pointer text-xs text-gray-500">
                        <vort-checkbox
                            :checked="allChecked"
                            :indeterminate="indeterminate"
                            @update:checked="allChecked = $event"
                        />
                        全选
                    </label>
                </div>
                <div v-if="projects.length" class="flex flex-wrap gap-x-4 gap-y-2 border rounded-lg p-3">
                    <label
                        v-for="p in projects"
                        :key="p.id"
                        class="flex items-center gap-1.5 cursor-pointer select-none"
                    >
                        <vort-checkbox
                            :checked="selectedProjectIds.includes(p.id)"
                            @update:checked="toggleProject(p.id)"
                        />
                        <span class="text-sm text-gray-700">{{ p.name }}</span>
                    </label>
                </div>
                <div v-else class="text-xs text-gray-400">暂无项目</div>
            </div>

            <!-- Scenes -->
            <div class="space-y-3" :class="!form.enabled ? 'opacity-50 pointer-events-none' : ''">
                <h4 class="text-sm font-medium text-gray-700">提醒场景</h4>

                <!-- Morning -->
                <div class="border rounded-lg p-4">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <Clock :size="16" class="text-amber-500" />
                            <span class="text-sm font-medium text-gray-800">晨间工作简报</span>
                            <vort-switch v-model:checked="form.scenes.morning.enabled" size="small" />
                        </div>
                        <vort-button
                            v-if="form.scenes.morning.enabled"
                            size="small"
                            :loading="testing"
                            @click="handleTest('morning')"
                        >
                            <Play :size="12" class="mr-1" /> 测试
                        </vort-button>
                    </div>
                    <p class="text-xs text-gray-400 mb-3">每个工作日推送待办概览、逾期提醒、紧急缺陷和工作建议</p>
                    <div v-if="form.scenes.morning.enabled" class="flex items-center gap-2">
                        <span class="text-xs text-gray-500">提醒时间</span>
                        <vort-select v-model="form.scenes.morning.time" class="w-[100px]">
                            <vort-select-option v-for="t in morningTimeOptions" :key="t" :value="t">{{ t }}</vort-select-option>
                        </vort-select>
                    </div>
                </div>

                <!-- Afternoon -->
                <div class="border rounded-lg p-4">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <CalendarDays :size="16" class="text-blue-500" />
                            <span class="text-sm font-medium text-gray-800">午后进度检查</span>
                            <vort-switch v-model:checked="form.scenes.afternoon.enabled" size="small" />
                        </div>
                        <vort-button
                            v-if="form.scenes.afternoon.enabled"
                            size="small"
                            :loading="testing"
                            @click="handleTest('afternoon')"
                        >
                            <Play :size="12" class="mr-1" /> 测试
                        </vort-button>
                    </div>
                    <p class="text-xs text-gray-400 mb-3">午休结束后推送当日变动和待关注事项</p>
                    <div v-if="form.scenes.afternoon.enabled" class="flex items-center gap-2">
                        <span class="text-xs text-gray-500">提醒时间</span>
                        <vort-select v-model="form.scenes.afternoon.time" class="w-[100px]">
                            <vort-select-option v-for="t in afternoonTimeOptions" :key="t" :value="t">{{ t }}</vort-select-option>
                        </vort-select>
                    </div>
                </div>

                <!-- Weekly -->
                <div class="border rounded-lg p-4">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <AlertTriangle :size="16" class="text-purple-500" />
                            <span class="text-sm font-medium text-gray-800">周工作总结</span>
                            <vort-switch v-model:checked="form.scenes.weekly.enabled" size="small" />
                        </div>
                        <vort-button
                            v-if="form.scenes.weekly.enabled"
                            size="small"
                            :loading="testing"
                            @click="handleTest('weekly')"
                        >
                            <Play :size="12" class="mr-1" /> 测试
                        </vort-button>
                    </div>
                    <p class="text-xs text-gray-400 mb-3">每周推送完成情况、遗留事项和下周建议</p>
                    <div v-if="form.scenes.weekly.enabled" class="flex items-center gap-3">
                        <div class="flex items-center gap-2">
                            <span class="text-xs text-gray-500">推送日</span>
                            <vort-select v-model="form.scenes.weekly.day" class="w-[90px]">
                                <vort-select-option v-for="d in weekDayOptions" :key="d.value" :value="d.value">{{ d.label }}</vort-select-option>
                            </vort-select>
                        </div>
                        <div class="flex items-center gap-2">
                            <span class="text-xs text-gray-500">时间</span>
                            <vort-select v-model="form.scenes.weekly.time" class="w-[100px]">
                                <vort-select-option v-for="t in weeklyTimeOptions" :key="t" :value="t">{{ t }}</vort-select-option>
                            </vort-select>
                        </div>
                    </div>
                </div>

                <!-- Instant -->
                <div class="border rounded-lg p-4">
                    <div class="flex items-center gap-2">
                        <Zap :size="16" class="text-red-500" />
                        <span class="text-sm font-medium text-gray-800">实时紧急通知</span>
                        <vort-switch v-model:checked="form.scenes.instant.enabled" size="small" />
                    </div>
                    <p class="text-xs text-gray-400 mt-2">致命/严重缺陷被分配、工作项逾期时即时通知</p>
                </div>
            </div>

            <!-- Rules -->
            <div class="space-y-4" :class="!form.enabled ? 'opacity-50 pointer-events-none' : ''">
                <h4 class="text-sm font-medium text-gray-700">提醒规则</h4>

                <!-- Work days -->
                <div class="flex items-center gap-3 flex-wrap">
                    <span class="text-sm text-gray-500 w-[100px]">提醒日</span>
                    <div class="flex items-center gap-2">
                        <label
                            v-for="d in weekDayOptions"
                            :key="d.value"
                            class="flex items-center gap-1 cursor-pointer"
                        >
                            <vort-checkbox v-model:checked="workDayChecks[d.value]" />
                            <span class="text-xs text-gray-600">{{ d.label.replace('周', '') }}</span>
                        </label>
                    </div>
                </div>

                <!-- Near deadline days -->
                <div class="flex items-center gap-3">
                    <span class="text-sm text-gray-500 w-[100px]">"即将逾期"天数</span>
                    <vort-select v-model="form.near_deadline_days" class="w-[80px]">
                        <vort-select-option v-for="n in nearDaysOptions" :key="n" :value="n">{{ n }} 天</vort-select-option>
                    </vort-select>
                </div>

                <!-- AI suggestion -->
                <div class="flex items-center gap-3">
                    <span class="text-sm text-gray-500 w-[100px]">AI 智能建议</span>
                    <vort-switch v-model:checked="form.ai_suggestion" />
                    <span class="text-xs text-gray-400">在提醒中包含 AI 生成的优先级建议</span>
                </div>

                <!-- Skip empty -->
                <div class="flex items-center gap-3">
                    <span class="text-sm text-gray-500 w-[100px]">仅提醒有待办的成员</span>
                    <vort-switch v-model:checked="form.skip_empty" />
                </div>

                <!-- Min threshold -->
                <div class="flex items-center gap-3">
                    <span class="text-sm text-gray-500 w-[100px]">最小提醒阈值</span>
                    <vort-select v-model="form.min_threshold" class="w-[80px]">
                        <vort-select-option v-for="n in thresholdOptions" :key="n" :value="n">{{ n }}</vort-select-option>
                    </vort-select>
                    <span class="text-xs text-gray-400">待办数低于此值不发提醒</span>
                </div>
            </div>

            <!-- Actions -->
            <div class="flex justify-end gap-3 pt-2 border-t">
                <vort-button @click="handleReset">恢复默认</vort-button>
                <vort-button variant="primary" :loading="saving" @click="handleSave">保存</vort-button>
            </div>
        </div>
    </vort-spin>
</template>
