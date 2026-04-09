<script setup lang="ts">
import { ref, watch } from "vue";
import { getSubmissionDetail, sendReminders } from "@/api";
import { message } from "@openvort/vort-ui";

interface MemberItem {
    member_id: string;
    name: string;
    avatar_url: string;
    submitted_at?: string | null;
}

interface DetailData {
    publication_id: string;
    publication_name: string;
    report_date: string;
    deadline_time: string;
    submitted: MemberItem[];
    not_submitted: MemberItem[];
}

const props = defineProps<{
    open: boolean;
    publicationId: string;
    reportDate: string;
    defaultTab?: "submitted" | "not_submitted";
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
}>();

const loading = ref(false);
const detail = ref<DetailData | null>(null);
const activeTab = ref<"submitted" | "not_submitted">("submitted");
const reminding = ref(false);

const AVATAR_COLORS = ["#1677ff", "#52c41a", "#faad14", "#eb2f96", "#722ed1", "#13c2c2", "#fa541c", "#2f54eb"];
function avatarBg(name: string): string {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]!;
}

function formatTime(dt: string): string {
    const d = new Date(dt);
    return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatDateRange(dateStr: string, deadline: string): string {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const hmMatch = deadline?.match(/\d{2}:\d{2}/);
    const hm = hmMatch ? hmMatch[0] : "19:00";
    if (deadline?.startsWith("次日")) {
        const next = new Date(d);
        next.setDate(next.getDate() + 1);
        return `${m}月${day}日 00:00 ~ ${next.getMonth() + 1}月${next.getDate()}日 ${hm}`;
    }
    return `${m}月${day}日 00:00 ~ ${m}月${day}日 ${hm}`;
}

watch(() => props.open, async (val) => {
    if (val && props.publicationId && props.reportDate) {
        activeTab.value = props.defaultTab || "submitted";
        loading.value = true;
        try {
            const res: any = await getSubmissionDetail({
                publication_id: props.publicationId,
                report_date: props.reportDate,
            });
            detail.value = res;
        } catch { detail.value = null; }
        finally { loading.value = false; }
    }
});

async function handleRemind() {
    if (!detail.value) return;
    reminding.value = true;
    try {
        const res: any = await sendReminders(detail.value.publication_id, {
            report_date: detail.value.report_date,
        });
        if (res?.ok) {
            if (res.sent > 0) message.success(`已发送提醒：${res.sent} 人`);
            else message.warning("无需提醒");
        } else { message.error(res?.error || "发送失败"); }
    } catch { message.error("发送失败"); }
    finally { reminding.value = false; }
}
</script>

<template>
    <vort-dialog :open="open" :width="420" @update:open="emit('update:open', $event)">
        <template #title>
            <div class="flex items-center gap-4">
                <button
                    class="pb-1 text-sm font-medium border-b-2 transition-colors"
                    :class="activeTab === 'submitted' ? 'text-gray-800 border-blue-500' : 'text-gray-400 border-transparent hover:text-gray-600'"
                    @click="activeTab = 'submitted'"
                >已提交 · {{ detail?.submitted?.length || 0 }}</button>
                <button
                    class="pb-1 text-sm font-medium border-b-2 transition-colors"
                    :class="activeTab === 'not_submitted' ? 'text-gray-800 border-blue-500' : 'text-gray-400 border-transparent hover:text-gray-600'"
                    @click="activeTab = 'not_submitted'"
                >未提交 · {{ detail?.not_submitted?.length || 0 }}</button>
            </div>
        </template>

        <vort-spin :spinning="loading">
            <template v-if="detail">
                <div class="text-xs text-gray-400 mb-3">
                    汇报周期：{{ formatDateRange(detail.report_date, detail.deadline_time) }}
                </div>

                <div v-if="activeTab === 'submitted'" class="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
                    <div v-for="m in detail.submitted" :key="m.member_id" class="flex items-center gap-3 py-2.5">
                        <div
                            class="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center overflow-hidden"
                            :style="{ backgroundColor: m.avatar_url ? undefined : avatarBg(m.name) }"
                        >
                            <img v-if="m.avatar_url" :src="m.avatar_url" class="w-full h-full object-cover" />
                            <span v-else class="text-white text-xs font-medium">{{ (m.name || '?')[0] }}</span>
                        </div>
                        <span class="text-sm text-gray-800">{{ m.name }}</span>
                        <span v-if="m.submitted_at" class="ml-auto text-xs text-gray-400">提交于 {{ formatTime(m.submitted_at) }}</span>
                    </div>
                    <div v-if="!detail.submitted.length" class="text-gray-400 text-sm text-center py-8">暂无提交</div>
                </div>

                <div v-if="activeTab === 'not_submitted'" class="space-y-0">
                    <div class="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
                        <div v-for="m in detail.not_submitted" :key="m.member_id" class="flex items-center gap-3 py-2.5">
                            <div
                                class="w-9 h-9 rounded-full flex-shrink-0 flex items-center justify-center overflow-hidden"
                                :style="{ backgroundColor: m.avatar_url ? undefined : avatarBg(m.name) }"
                            >
                                <img v-if="m.avatar_url" :src="m.avatar_url" class="w-full h-full object-cover" />
                                <span v-else class="text-white text-xs font-medium">{{ (m.name || '?')[0] }}</span>
                            </div>
                            <span class="text-sm text-gray-800">{{ m.name }}</span>
                        </div>
                        <div v-if="!detail.not_submitted.length" class="text-gray-400 text-sm text-center py-8">全部已提交</div>
                    </div>
                    <vort-button
                        v-if="detail.not_submitted.length"
                        variant="primary"
                        class="w-full mt-4"
                        :loading="reminding"
                        @click="handleRemind"
                    >提醒填写</vort-button>
                </div>
            </template>
        </vort-spin>

        <template #footer><span /></template>
    </vort-dialog>
</template>
