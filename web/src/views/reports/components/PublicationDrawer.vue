<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { z } from "zod";
import { message } from "@openvort/vort-ui";
import { Settings, X, Plus } from "lucide-vue-next";
import { createPublication, updatePublication, getMembersSimple } from "@/api";
import { MemberPicker } from "@/components/vort-biz/member-picker";
import { VortEditor } from "@/components/vort-biz/editor";

interface ReceiverFilters {
    [receiverId: string]: string[];
}

interface PublicationData {
    id?: string;
    name: string;
    description: string;
    report_type: string;
    content_template: string;
    repeat_cycle: string;
    deadline_time: string;
    reminder_enabled: boolean;
    reminder_time: string;
    skip_weekends: boolean;
    skip_holidays: boolean;
    allow_multiple: boolean;
    allow_edit: boolean;
    notify_summary: boolean;
    notify_on_receive: boolean;
    submitter_ids: string[];
    whitelist_ids: string[];
    receiver_ids: string[];
    receiver_filters: ReceiverFilters;
}

interface SimpleMember {
    id: string;
    name: string;
}

const props = defineProps<{
    open: boolean;
    editData?: PublicationData | null;
}>();

const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const step = ref(1);
const submitting = ref(false);
const formRef = ref();
const memberMap = ref<Record<string, string>>({});

const defaultForm = (): PublicationData => ({
    name: "", description: "", report_type: "daily",
    content_template: "",
    repeat_cycle: "daily", deadline_time: "次日 10:00",
    reminder_enabled: true, reminder_time: "10:00",
    skip_weekends: true, skip_holidays: true,
    allow_multiple: true, allow_edit: true,
    notify_summary: true, notify_on_receive: true,
    submitter_ids: [], whitelist_ids: [], receiver_ids: [],
    receiver_filters: {},
});

const form = ref<PublicationData>(defaultForm());

const rules = z.object({
    name: z.string().min(1, "请输入标题"),
    description: z.string().optional(),
});

const isEdit = computed(() => !!props.editData?.id);
const title = computed(() => isEdit.value ? "编辑汇报" : "发布汇报");

watch(() => props.open, async (val) => {
    if (val) {
        step.value = 1;
        submitting.value = false;
        form.value = props.editData
            ? { ...defaultForm(), ...props.editData, receiver_filters: { ...(props.editData.receiver_filters || {}) } }
            : defaultForm();
        await loadMemberNames();
    }
});

async function loadMemberNames() {
    try {
        const res: any = await getMembersSimple({ size: 500 });
        const members: SimpleMember[] = res?.members || [];
        const map: Record<string, string> = {};
        for (const m of members) {
            if (m.id) map[m.id] = m.name;
        }
        memberMap.value = map;
    } catch { /* ignore */ }
}

function memberName(id: string): string {
    return memberMap.value[id] || id.slice(0, 8);
}

function handleClose() {
    emit("update:open", false);
}

async function handleNextStep() {
    if (step.value === 1) {
        try { await formRef.value?.validate(); } catch { return; }
        step.value = 2;
    }
}

function handlePrevStep() {
    if (step.value === 2) step.value = 1;
}

async function handleSubmit() {
    if (form.value.submitter_ids.length === 0) {
        message.warning("请至少添加一位提交人");
        return;
    }
    if (form.value.receiver_ids.length === 0) {
        message.warning("请至少添加一位接收人");
        return;
    }
    submitting.value = true;
    try {
        const payload = { ...form.value };
        if (isEdit.value && props.editData?.id) {
            const res: any = await updatePublication(props.editData.id, payload);
            if (res?.success) {
                message.success("已更新");
                emit("saved");
                handleClose();
            } else { message.error("更新失败"); }
        } else {
            const res: any = await createPublication(payload);
            if (res?.success) {
                message.success("已发布");
                emit("saved");
                handleClose();
            } else { message.error("发布失败"); }
        }
    } catch { message.error("操作失败"); }
    finally { submitting.value = false; }
}

// ---- Pickers ----

const showSubmitterPicker = ref(false);
const showWhitelistPicker = ref(false);
const showReceiverPicker = ref(false);

// When submitters change, remove invalid filter entries
watch(() => form.value.submitter_ids, (sids) => {
    const sidSet = new Set(sids);
    const filters = form.value.receiver_filters;
    for (const rid of Object.keys(filters)) {
        const kept = (filters[rid] || []).filter(sid => sidSet.has(sid));
        if (kept.length === 0) delete filters[rid];
        else filters[rid] = kept;
    }
}, { deep: true });

// When receivers change, remove filter entries for removed receivers
watch(() => form.value.receiver_ids, (rids) => {
    const ridSet = new Set(rids);
    const filters = form.value.receiver_filters;
    for (const rid of Object.keys(filters)) {
        if (!ridSet.has(rid)) delete filters[rid];
    }
}, { deep: true });

// ---- Receiver filter dialog ----

const filterDialogOpen = ref(false);
const filterDialogReceiverId = ref("");
const filterDialogMode = ref<"all" | "specific">("all");
const filterDialogSelected = ref<string[]>([]);

function openFilterDialog(receiverId: string) {
    filterDialogReceiverId.value = receiverId;
    const existing = form.value.receiver_filters[receiverId];
    if (existing && existing.length > 0) {
        filterDialogMode.value = "specific";
        filterDialogSelected.value = [...existing];
    } else {
        filterDialogMode.value = "all";
        filterDialogSelected.value = [];
    }
    filterDialogOpen.value = true;
}

function saveFilterDialog() {
    const rid = filterDialogReceiverId.value;
    if (filterDialogMode.value === "all") {
        delete form.value.receiver_filters[rid];
    } else {
        if (filterDialogSelected.value.length === 0) {
            message.warning("请至少选择一位提交人");
            return;
        }
        form.value.receiver_filters[rid] = [...filterDialogSelected.value];
    }
    filterDialogOpen.value = false;
}

function removeReceiver(id: string) {
    form.value.receiver_ids = form.value.receiver_ids.filter(r => r !== id);
    delete form.value.receiver_filters[id];
}

function getReceiverFilterLabel(receiverId: string): string {
    const f = form.value.receiver_filters[receiverId];
    if (!f || f.length === 0) return "接收全部";
    return `接收 ${f.length} 位指定提交人`;
}

function toggleFilterSubmitter(sid: string) {
    const idx = filterDialogSelected.value.indexOf(sid);
    if (idx > -1) filterDialogSelected.value.splice(idx, 1);
    else filterDialogSelected.value.push(sid);
}

// ---- Deadline helpers ----

const deadlineDay = computed({
    get: () => {
        const v = form.value.deadline_time;
        return v.startsWith("当日") ? "当日" : "次日";
    },
    set: (val: string) => {
        form.value.deadline_time = `${val} ${deadlineHM.value}`;
    },
});

const deadlineHM = computed({
    get: () => {
        const m = form.value.deadline_time.match(/\d{2}:\d{2}/);
        return m ? m[0] : "10:00";
    },
    set: (val: string) => {
        form.value.deadline_time = `${deadlineDay.value} ${val}`;
    },
});

const AVATAR_COLORS = ["#1677ff", "#52c41a", "#faad14", "#eb2f96", "#722ed1", "#13c2c2", "#fa541c", "#2f54eb"];
function avatarBg(name: string): string {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length]!;
}
</script>

<template>
    <vort-drawer :open="open" :title="title" :width="640" @update:open="handleClose">
        <!-- Step indicator -->
        <vort-steps
            type="navigation"
            :current="step - 1"
            :items="[{ title: '编辑内容' }, { title: '设置规则' }]"
            :clickable="true"
            class="mb-6"
            @change="(idx: number) => idx === 0 ? step = 1 : handleNextStep()"
        />

        <!-- Step 1: Content -->
        <div v-show="step === 1">
            <vort-form ref="formRef" :model="form" :rules="rules" label-width="100px">
                <vort-form-item label="标题" name="name" required>
                    <vort-input v-model="form.name" placeholder="如：技术团队日报" />
                </vort-form-item>
                <vort-form-item label="描述" name="description">
                    <vort-textarea v-model="form.description" :rows="3" placeholder="描述此汇报要提交的内容" />
                </vort-form-item>
                <vort-form-item label="汇报类型" name="report_type">
                    <vort-select v-model="form.report_type" style="width: 100%">
                        <vort-select-option value="daily">日报</vort-select-option>
                        <vort-select-option value="weekly">周报</vort-select-option>
                        <vort-select-option value="monthly">月报</vort-select-option>
                    </vort-select>
                </vort-form-item>
                <vort-form-item label="内容模板" name="content_template">
                    <VortEditor v-model="form.content_template" placeholder="设置汇报默认内容，如：&#10;## 今日工作&#10;&#10;## 遇到的问题&#10;&#10;## 明日计划" min-height="200px" />
                </vort-form-item>
            </vort-form>
        </div>

        <!-- Step 2: Rules -->
        <div v-show="step === 2" class="space-y-5">
            <!-- Submitters -->
            <div class="bg-gray-50 rounded-lg p-4 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-sm font-medium text-gray-700">提交人</span>
                    <a class="text-sm text-blue-600 cursor-pointer" @click="showSubmitterPicker = true">
                        {{ form.submitter_ids.length ? `已选 ${form.submitter_ids.length} 人` : '未添加' }} &gt;
                    </a>
                </div>
                <div class="flex items-center justify-between">
                    <div>
                        <span class="text-sm font-medium text-gray-700">白名单</span>
                        <div class="text-xs text-gray-400">白名单内的成员无需汇报</div>
                    </div>
                    <a class="text-sm text-blue-600 cursor-pointer" @click="showWhitelistPicker = true">
                        {{ form.whitelist_ids.length ? `${form.whitelist_ids.length} 人` : '未添加' }} &gt;
                    </a>
                </div>
            </div>

            <!-- Schedule -->
            <div class="bg-gray-50 rounded-lg p-4 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-sm font-medium text-gray-700">汇报方式</span>
                    <span class="text-sm text-gray-500">
                        {{ { daily: '按日', weekly: '按周', monthly: '按月' }[form.repeat_cycle] || form.repeat_cycle }}
                        每日{{ deadlineHM }}
                    </span>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">重复周期</span>
                    <vort-select v-model="form.repeat_cycle" style="width: 200px">
                        <vort-select-option value="daily">按日</vort-select-option>
                        <vort-select-option value="weekly">按周</vort-select-option>
                        <vort-select-option value="monthly">按月</vort-select-option>
                    </vort-select>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">汇报截止时间</span>
                    <div class="flex items-center gap-2">
                        <vort-select v-model="deadlineDay" style="width: 90px">
                            <vort-select-option value="当日">当日</vort-select-option>
                            <vort-select-option value="次日">次日</vort-select-option>
                        </vort-select>
                        <VortTimePicker v-model="deadlineHM" format="HH:mm" value-format="HH:mm" :minute-step="15" :show-second="false" style="width: 120px" />
                    </div>
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">提醒填写</span>
                    <vort-switch v-model:checked="form.reminder_enabled" size="small" />
                </div>
                <div v-if="form.reminder_enabled" class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">提醒时间</span>
                    <VortTimePicker v-model="form.reminder_time" format="HH:mm" value-format="HH:mm" :minute-step="15" :show-second="false" style="width: 120px" />
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">允许提交多份</span>
                    <vort-switch v-model:checked="form.allow_multiple" size="small" />
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">允许修改结果</span>
                    <vort-switch v-model:checked="form.allow_edit" size="small" />
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">跳过周末</span>
                    <vort-switch v-model:checked="form.skip_weekends" size="small" />
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">跳过节假日</span>
                    <vort-switch v-model:checked="form.skip_holidays" size="small" />
                </div>
            </div>

            <!-- Receivers & notifications -->
            <div class="bg-gray-50 rounded-lg p-4 space-y-3">
                <div class="flex items-center justify-between">
                    <span class="text-sm font-medium text-gray-700">接收人</span>
                    <a class="text-sm text-blue-600 cursor-pointer" @click="showReceiverPicker = true">
                        <Plus :size="14" class="inline mr-0.5" />添加
                    </a>
                </div>

                <!-- Receiver list -->
                <div v-if="form.receiver_ids.length" class="space-y-2">
                    <div
                        v-for="rid in form.receiver_ids" :key="rid"
                        class="flex items-center justify-between bg-white rounded-md px-3 py-2"
                    >
                        <div class="flex items-center gap-2.5 min-w-0">
                            <span
                                class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                                :style="{ backgroundColor: avatarBg(memberName(rid)) }"
                            >{{ (memberName(rid) || '?')[0] }}</span>
                            <div class="min-w-0">
                                <span class="text-sm text-gray-800">{{ memberName(rid) }}</span>
                                <span class="text-xs text-gray-400 ml-2">{{ getReceiverFilterLabel(rid) }}</span>
                            </div>
                        </div>
                        <div class="flex items-center gap-1 flex-shrink-0">
                            <button
                                class="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-blue-600"
                                title="设置接收范围"
                                @click="openFilterDialog(rid)"
                            >
                                <Settings :size="14" />
                            </button>
                            <button
                                class="p-1 rounded hover:bg-gray-100 text-gray-400 hover:text-red-500"
                                title="移除"
                                @click="removeReceiver(rid)"
                            >
                                <X :size="14" />
                            </button>
                        </div>
                    </div>
                </div>
                <div v-else class="text-xs text-gray-400 py-1">未添加接收人</div>

                <div class="flex items-center justify-between pt-1 border-t border-gray-200">
                    <span class="text-sm text-gray-600">汇报截止时发送汇总通知</span>
                    <vort-switch v-model:checked="form.notify_summary" size="small" />
                </div>
                <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-600">收到汇报时立即通知</span>
                    <vort-switch v-model:checked="form.notify_on_receive" size="small" />
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="handleClose">取消</vort-button>
                <vort-button v-if="step === 2" @click="handlePrevStep">上一步</vort-button>
                <vort-button v-if="step === 1" variant="primary" @click="handleNextStep">下一步</vort-button>
                <vort-button v-if="step === 2" variant="primary" :loading="submitting" @click="handleSubmit">
                    {{ isEdit ? '保存' : '发布' }}
                </vort-button>
            </div>
        </template>
    </vort-drawer>

    <!-- Member pickers -->
    <vort-dialog v-model:open="showSubmitterPicker" title="选择提交人" :width="640">
        <MemberPicker v-model="form.submitter_ids" title="已选提交人" :show-send-reminder="true" />
        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="showSubmitterPicker = false">取消</vort-button>
                <vort-button variant="primary" @click="showSubmitterPicker = false">确定</vort-button>
            </div>
        </template>
    </vort-dialog>

    <vort-dialog v-model:open="showWhitelistPicker" title="选择白名单" :width="640">
        <MemberPicker v-model="form.whitelist_ids" title="白名单成员" />
        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="showWhitelistPicker = false">取消</vort-button>
                <vort-button variant="primary" @click="showWhitelistPicker = false">确定</vort-button>
            </div>
        </template>
    </vort-dialog>

    <vort-dialog v-model:open="showReceiverPicker" title="添加接收人" :width="640">
        <MemberPicker v-model="form.receiver_ids" title="已选接收人" />
        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="showReceiverPicker = false">取消</vort-button>
                <vort-button variant="primary" @click="showReceiverPicker = false">确定</vort-button>
            </div>
        </template>
    </vort-dialog>

    <!-- Receiver filter dialog -->
    <vort-dialog v-model:open="filterDialogOpen" :title="`设置接收范围 (${memberName(filterDialogReceiverId)})`" :width="480">
        <div class="space-y-4">
            <div class="space-y-2">
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="filter-mode" value="all" v-model="filterDialogMode" class="accent-blue-600" />
                    <span class="text-sm text-gray-700">接收全部提交人的汇报</span>
                </label>
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="filter-mode" value="specific" v-model="filterDialogMode" class="accent-blue-600" />
                    <span class="text-sm text-gray-700">仅接收指定提交人的汇报</span>
                </label>
            </div>

            <div v-if="filterDialogMode === 'specific'" class="border border-gray-200 rounded-lg max-h-120 overflow-y-auto">
                <div v-if="form.submitter_ids.length" class="divide-y divide-gray-50">
                    <label
                        v-for="sid in form.submitter_ids" :key="sid"
                        class="flex items-center gap-3 px-3 py-2.5 hover:bg-gray-50 cursor-pointer"
                    >
                        <vort-checkbox
                            :checked="filterDialogSelected.includes(sid)"
                            @update:checked="toggleFilterSubmitter(sid)"
                        />
                        <span
                            class="inline-flex items-center justify-center w-7 h-7 rounded-full text-white text-xs font-medium flex-shrink-0"
                            :style="{ backgroundColor: avatarBg(memberName(sid)) }"
                        >{{ (memberName(sid) || '?')[0] }}</span>
                        <span class="text-sm text-gray-800">{{ memberName(sid) }}</span>
                    </label>
                </div>
                <div v-else class="text-gray-400 text-sm text-center py-6">请先添加提交人</div>
            </div>

            <p v-if="filterDialogMode === 'all'" class="text-xs text-gray-400">
                该接收人将收到所有提交人的汇报。
            </p>
            <p v-else class="text-xs text-gray-400">
                已选择 {{ filterDialogSelected.length }} 位提交人，该接收人仅会收到这些提交人的汇报。
            </p>
        </div>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="filterDialogOpen = false">取消</vort-button>
                <vort-button variant="primary" @click="saveFilterDialog">确定</vort-button>
            </div>
        </template>
    </vort-dialog>
</template>
