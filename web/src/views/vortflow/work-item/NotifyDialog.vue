<template>
    <Dialog
        :open="open"
        title="发送通知"
        :confirm-loading="submitting"
        ok-text="发送"
        @ok="handleSubmit"
        @update:open="$emit('update:open', $event)"
    >
        <div class="space-y-5">
            <div>
                <div class="text-sm font-medium text-gray-700 mb-2">通知类型</div>
                <vort-radio-group v-model="form.notifyType">
                    <vort-radio-button value="remind">
                        <span class="inline-flex items-center gap-1">
                            <Bell :size="14" />
                            提醒
                        </span>
                    </vort-radio-button>
                    <vort-radio-button value="urge">
                        <span class="inline-flex items-center gap-1">
                            <AlarmClock :size="14" />
                            催办
                        </span>
                    </vort-radio-button>
                </vort-radio-group>
                <p class="text-xs text-gray-400 mt-1">
                    {{ form.notifyType === "urge" ? "催办将以更高优先级发送通知，提醒对方尽快处理" : "温和地提醒相关人员关注此工作项" }}
                </p>
            </div>

            <div>
                <div class="text-sm font-medium text-gray-700 mb-2">通知对象</div>
                <div class="flex items-center gap-2 mb-3">
                    <vort-button
                        :variant="quickSelect === 'all' ? 'primary' : undefined"
                        size="small"
                        @click="selectQuick('all')"
                    >全部成员</vort-button>
                    <vort-button
                        v-if="hasOwner"
                        :variant="quickSelect === 'owner' ? 'primary' : undefined"
                        size="small"
                        @click="selectQuick('owner')"
                    >仅负责人</vort-button>
                    <vort-button
                        v-if="hasCollaborators"
                        :variant="quickSelect === 'collaborators' ? 'primary' : undefined"
                        size="small"
                        @click="selectQuick('collaborators')"
                    >仅协作人</vort-button>
                </div>
                <div class="border rounded-lg p-3 max-h-[180px] overflow-y-auto">
                    <template v-if="candidateMembers.length > 0">
                        <label
                            v-for="m in candidateMembers"
                            :key="m.id"
                            class="flex items-center gap-2 py-1.5 px-1 rounded hover:bg-gray-50 cursor-pointer select-none"
                        >
                            <vort-checkbox
                                :checked="form.recipientIds.includes(m.id)"
                                @update:checked="(v: boolean) => toggleRecipient(m.id, v)"
                            />
                            <span
                                class="inline-flex items-center justify-center w-6 h-6 rounded-full text-white text-xs font-medium flex-shrink-0 overflow-hidden"
                                :style="{ background: getAvatarBg(m.name) }"
                            >
                                <img v-if="m.avatarUrl" :src="m.avatarUrl" class="w-full h-full object-cover" />
                                <template v-else>{{ m.name.slice(0, 1) }}</template>
                            </span>
                            <span class="text-sm text-gray-700">{{ m.name }}</span>
                            <vort-tag v-if="m.role === 'owner'" color="blue" size="small">负责人</vort-tag>
                            <vort-tag v-else-if="m.role === 'collaborator'" size="small">协作人</vort-tag>
                        </label>
                    </template>
                    <p v-else class="text-sm text-gray-400 text-center py-2">暂无可通知的成员</p>
                </div>
            </div>

            <div>
                <div class="text-sm font-medium text-gray-700 mb-2">附言 <span class="text-gray-400 font-normal">(可选)</span></div>
                <vort-textarea
                    v-model="form.message"
                    placeholder="输入附加说明..."
                    :rows="3"
                />
            </div>
        </div>
    </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Dialog, message } from "@openvort/vort-ui";
import { Bell, AlarmClock } from "lucide-vue-next";
import { sendVortflowNotify } from "@/api";

interface CandidateMember {
    id: string;
    name: string;
    avatarUrl: string;
    role: "owner" | "collaborator" | "other";
}

const props = defineProps<{
    open: boolean;
    entityType: string;
    entityId: string;
    title: string;
    projectId: string;
    ownerId: string;
    ownerName: string;
    collaboratorNames: string[];
    getMemberIdByName: (name: string) => string;
    getAvatarBg: (name: string) => string;
    getMemberAvatarUrl: (name: string) => string;
}>();

const emit = defineEmits<{
    (e: "update:open", val: boolean): void;
    (e: "sent"): void;
}>();

const submitting = ref(false);
const quickSelect = ref<"all" | "owner" | "collaborators" | "">("");
const form = ref({
    notifyType: "remind" as "remind" | "urge",
    recipientIds: [] as string[],
    message: "",
});

const hasOwner = computed(() => Boolean(props.ownerId));
const hasCollaborators = computed(() => props.collaboratorNames.length > 0);

const candidateMembers = computed<CandidateMember[]>(() => {
    const members: CandidateMember[] = [];
    const seen = new Set<string>();

    if (props.ownerId && props.ownerName) {
        members.push({
            id: props.ownerId,
            name: props.ownerName,
            avatarUrl: props.getMemberAvatarUrl(props.ownerName),
            role: "owner",
        });
        seen.add(props.ownerId);
    }

    for (const name of props.collaboratorNames) {
        const id = props.getMemberIdByName(name);
        if (id && !seen.has(id)) {
            members.push({
                id,
                name,
                avatarUrl: props.getMemberAvatarUrl(name),
                role: "collaborator",
            });
            seen.add(id);
        }
    }

    return members;
});

const selectQuick = (mode: "all" | "owner" | "collaborators") => {
    quickSelect.value = mode;
    if (mode === "all") {
        form.value.recipientIds = candidateMembers.value.map((m) => m.id);
    } else if (mode === "owner") {
        form.value.recipientIds = props.ownerId ? [props.ownerId] : [];
    } else if (mode === "collaborators") {
        form.value.recipientIds = candidateMembers.value
            .filter((m) => m.role === "collaborator")
            .map((m) => m.id);
    }
};

const toggleRecipient = (id: string, checked: boolean) => {
    quickSelect.value = "";
    const ids = form.value.recipientIds;
    if (checked && !ids.includes(id)) {
        ids.push(id);
    } else if (!checked) {
        const idx = ids.indexOf(id);
        if (idx >= 0) ids.splice(idx, 1);
    }
};

watch(() => props.open, (val) => {
    if (val) {
        form.value = { notifyType: "remind", recipientIds: [], message: "" };
        quickSelect.value = "";
        submitting.value = false;
        if (candidateMembers.value.length > 0) {
            selectQuick("all");
        }
    }
});

async function handleSubmit() {
    if (form.value.recipientIds.length === 0) {
        message.warning("请选择至少一个通知对象");
        return;
    }
    submitting.value = true;
    try {
        await sendVortflowNotify({
            entity_type: props.entityType,
            entity_id: props.entityId,
            title: props.title,
            project_id: props.projectId,
            notify_type: form.value.notifyType,
            recipient_ids: form.value.recipientIds,
            message: form.value.message || undefined,
        });
        message.success("通知已发送");
        emit("sent");
        emit("update:open", false);
    } catch {
        message.error("发送通知失败");
    } finally {
        submitting.value = false;
    }
}
</script>
