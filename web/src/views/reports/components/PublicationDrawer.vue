<script setup lang="ts">
import { ref, watch, computed } from "vue";
import { z } from "zod";
import { message } from "@openvort/vort-ui";
import { createPublication, updatePublication } from "@/api";
import { MemberPicker } from "@/components/vort-biz/member-picker";

interface PublicationData {
    id?: string;
    name: string;
    description: string;
    report_type: string;
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

const defaultForm = (): PublicationData => ({
    name: "", description: "", report_type: "daily",
    repeat_cycle: "daily", deadline_time: "次日 10:00",
    reminder_enabled: true, reminder_time: "10:00",
    skip_weekends: true, skip_holidays: true,
    allow_multiple: true, allow_edit: true,
    notify_summary: true, notify_on_receive: true,
    submitter_ids: [], whitelist_ids: [], receiver_ids: [],
});

const form = ref<PublicationData>(defaultForm());

const rules = z.object({
    name: z.string().min(1, "请输入标题"),
    description: z.string().optional(),
});

const isEdit = computed(() => !!props.editData?.id);
const title = computed(() => isEdit.value ? "编辑汇报" : "发布汇报");

watch(() => props.open, (val) => {
    if (val) {
        step.value = 1;
        submitting.value = false;
        form.value = props.editData ? { ...defaultForm(), ...props.editData } : defaultForm();
    }
});

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

const showSubmitterPicker = ref(false);
const showWhitelistPicker = ref(false);
const showReceiverPicker = ref(false);

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
                        {{ form.receiver_ids.length ? `${form.receiver_ids.length} 人` : '未添加' }} &gt;
                    </a>
                </div>
                <div class="flex items-center justify-between">
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

    <vort-dialog v-model:open="showReceiverPicker" title="选择接收人" :width="640">
        <MemberPicker v-model="form.receiver_ids" title="已选接收人" />
        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="showReceiverPicker = false">取消</vort-button>
                <vort-button variant="primary" @click="showReceiverPicker = false">确定</vort-button>
            </div>
        </template>
    </vort-dialog>
</template>
