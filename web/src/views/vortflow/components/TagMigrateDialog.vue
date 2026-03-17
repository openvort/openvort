<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { ArrowRight } from "lucide-vue-next";
import { migrateVortflowTag } from "@/api";
import { message } from "@/components/vort/message";

interface TagItem {
    id: string;
    name: string;
    color: string;
    usage_count?: number;
}

interface Props {
    open: boolean;
    tag: TagItem | null;
    allTags: TagItem[];
}

const props = defineProps<Props>();
const emit = defineEmits<{
    "update:open": [val: boolean];
    saved: [];
}>();

const loading = ref(false);
const targetTagId = ref<string | null>(null);

watch(() => props.open, (val) => {
    if (val) targetTagId.value = null;
});

const targetOptions = computed(() => {
    if (!props.tag) return props.allTags;
    return props.allTags.filter((t) => t.id !== props.tag!.id);
});

const affectedCount = computed(() => props.tag?.usage_count ?? 0);

const handleConfirm = async () => {
    if (!props.tag) return;
    loading.value = true;
    try {
        const res: any = await migrateVortflowTag(props.tag.id, {
            target_tag_id: targetTagId.value,
        });
        if (res?.error) {
            message.error(res.error);
            return;
        }
        message.success(`迁移完成，共影响 ${res.affected ?? 0} 个工作项`);
        emit("update:open", false);
        emit("saved");
    } catch (e: any) {
        message.error(e?.message || "迁移失败");
    } finally {
        loading.value = false;
    }
};

const close = () => emit("update:open", false);
</script>

<template>
    <vort-dialog
        :open="open"
        title="标签数据迁移"
        :width="640"
        :centered="true"
        @update:open="close"
    >
        <div class="mt-2">
            <vort-alert
                type="warning"
                show-icon
                message="请选择迁移目标，确认迁移后，原标签将被锁定无法使用，直至数据迁移结束。"
                class="mb-6"
            />

            <div class="migrate-layout">
                <div class="migrate-panel">
                    <div class="migrate-panel-title">原标签</div>
                    <div class="migrate-panel-body">
                        <vort-tag v-if="tag" :color="tag.color">{{ tag.name }}</vort-tag>
                        <div class="migrate-stat">
                            使用的工作项：<span class="migrate-stat-num">{{ affectedCount }}</span>
                        </div>
                    </div>
                </div>

                <div class="migrate-arrow">
                    <ArrowRight :size="20" />
                </div>

                <div class="migrate-panel">
                    <div class="migrate-panel-title">将标签变更为</div>
                    <div class="migrate-panel-body">
                        <vort-select
                            v-model="targetTagId"
                            placeholder="无标签"
                            allow-clear
                            class="w-full"
                        >
                            <vort-select-option
                                v-for="opt in targetOptions"
                                :key="opt.id"
                                :value="opt.id"
                            >
                                <div class="flex items-center gap-2">
                                    <span
                                        class="inline-block w-3 h-3 rounded-full flex-shrink-0"
                                        :style="{ backgroundColor: opt.color }"
                                    />
                                    {{ opt.name }}
                                </div>
                            </vort-select-option>
                        </vort-select>
                        <div class="migrate-stat">
                            受影响的工作项：<span class="migrate-stat-num">{{ affectedCount }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button variant="primary" :loading="loading" @click="handleConfirm">确认迁移</vort-button>
                <vort-button @click="close">取消</vort-button>
            </div>
        </template>
    </vort-dialog>
</template>

<style scoped>
.migrate-layout {
    display: flex;
    align-items: flex-start;
    gap: 16px;
}
.migrate-panel {
    flex: 1;
    min-width: 0;
}
.migrate-panel-title {
    font-size: 14px;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
    margin-bottom: 12px;
}
.migrate-panel-body {
    background: var(--vort-bg-layout, #f5f5f5);
    border: 1px solid var(--vort-border, #d9d9d9);
    border-radius: var(--vort-radius, 8px);
    padding: 16px;
}
.migrate-arrow {
    flex-shrink: 0;
    color: var(--vort-text-quaternary, rgba(0, 0, 0, 0.25));
    padding-top: 44px;
}
.migrate-stat {
    font-size: 14px;
    color: var(--vort-text-secondary, rgba(0, 0, 0, 0.65));
    margin-top: 12px;
}
.migrate-stat-num {
    color: var(--vort-primary, #1456f0);
    font-weight: 500;
}
</style>
