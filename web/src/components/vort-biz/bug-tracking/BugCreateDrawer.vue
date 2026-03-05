<script setup lang="ts">
import type { Priority, WorkType, DateRange, BugAttachment } from "./types";
import {
    priorityOptions,
    ownerGroups,
    createBugTagOptions,
    createBugProjectOptions,
    createBugRepoOptions,
    createBugBranchOptions
} from "./types";

interface Props {
    state: ReturnType<typeof import("./useBugTrackingState").useBugTrackingState>;
}

const props = defineProps<Props>();

const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8e44ad"];
const getAvatarBg = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return avatarBgPalette[Math.abs(hash) % avatarBgPalette.length]!;
};

const formatFileSize = (size: number): string => {
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

const closeDrawer = () => {
    props.state.handleCancelCreateBug();
};

const handleSubmit = () => {
    props.state.handleSubmitCreateBug();
};
</script>

<template>
    <vort-drawer
        v-model:open="props.state.createBugDrawerOpen.value"
        :title="props.state.createBugDrawerMode.value === 'create' ? '新建缺陷' : '缺陷详情'"
        :width="680"
        @close="closeDrawer"
    >
        <div class="space-y-4">
            <!-- 标题 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">标题 <span class="text-red-500">*</span></label>
                <vort-input v-model="props.state.createBugForm.title" placeholder="请输入缺陷标题" />
            </div>

            <!-- 类型选择 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">类型 <span class="text-red-500">*</span></label>
                <div class="flex gap-2">
                    <button
                        v-for="t in (['缺陷', '需求', '任务'] as WorkType[])"
                        :key="t"
                        class="h-9 px-4 rounded border text-sm transition-colors"
                        :class="props.state.createBugForm.type === t ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-gray-300 hover:border-gray-400'"
                        @click="props.state.createBugForm.type = t"
                    >
                        {{ t }}
                    </button>
                </div>
            </div>

            <!-- 负责人 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">负责人</label>
                <div class="relative" @click.stop>
                    <button
                        class="h-9 w-full px-3 border border-gray-300 rounded bg-white flex items-center justify-between hover:border-gray-400"
                        @click.stop="props.state.toggleCreateAssigneeMenu()"
                    >
                        <span class="text-sm text-gray-700">{{ props.state.createBugForm.owner || '请选择负责人' }}</span>
                        <span class="status-arrow-simple" :class="{ open: props.state.createAssigneeDropdownOpen.value }" />
                    </button>
                    <div v-if="props.state.createAssigneeDropdownOpen.value" class="absolute z-30 mt-1 w-full max-h-[300px] bg-white border border-gray-200 rounded-lg shadow-md p-3">
                        <div class="mb-2">
                            <input v-model="props.state.createAssigneeKeyword.value" placeholder="搜索..." class="w-full h-8 px-3 border border-gray-300 rounded text-sm" />
                        </div>
                        <div class="max-h-[220px] overflow-y-auto -mx-3">
                            <div v-for="group in props.state.filteredCreateAssigneeGroups.value" :key="group.label + '-create'">
                                <button class="w-full h-9 px-3 bg-slate-100 flex items-center justify-between text-left text-sm" @click.stop="props.state.toggleCreateAssigneeGroup(group.label)">
                                    <span class="text-gray-700">{{ group.label }}</span>
                                    <span class="status-arrow-simple" :class="{ open: props.state.createAssigneeGroupOpen[group.label] }" />
                                </button>
                                <button
                                    v-for="member in (props.state.createAssigneeGroupOpen[group.label] ? group.members : [])"
                                    :key="group.label + member + '-create'"
                                    class="w-full h-9 px-3 flex items-center gap-2 text-left hover:bg-gray-50 text-sm"
                                    @click.stop="props.state.setCreateOwner(member)"
                                >
                                    <span class="w-6 h-6 rounded-full text-white text-xs flex items-center justify-center" :style="{ backgroundColor: getAvatarBg(member) }">
                                        {{ member.slice(0, 1).toUpperCase() }}
                                    </span>
                                    <span class="text-gray-700">{{ member }}</span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 协作人 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">协作人</label>
                <div class="flex flex-wrap gap-2">
                    <button
                        v-for="member in ownerGroups.flatMap(g => g.members)"
                        :key="'create-collab-' + member"
                        class="h-7 px-3 rounded-full text-xs border flex items-center gap-1 transition-colors"
                        :class="props.state.isCreateCollaborator(member) ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-gray-300 hover:border-gray-400'"
                        @click="props.state.toggleCreateCollaborator(member)"
                    >
                        <span v-if="props.state.isCreateCollaborator(member)" class="w-4 h-4 rounded-full bg-blue-500 text-white flex items-center justify-center text-[10px]">✓</span>
                        {{ member }}
                    </button>
                </div>
            </div>

            <!-- 项目信息 -->
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="text-sm text-gray-600 mb-1 block">项目</label>
                    <vort-select v-model="props.state.createBugForm.project" placeholder="请选择项目" class="w-full">
                        <vort-select-option v-for="p in createBugProjectOptions" :key="p" :value="p">{{ p }}</vort-select-option>
                    </vort-select>
                </div>
                <div>
                    <label class="text-sm text-gray-600 mb-1 block">迭代</label>
                    <vort-input v-model="props.state.createBugForm.iteration" placeholder="请输入迭代" />
                </div>
            </div>

            <!-- 版本信息 -->
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="text-sm text-gray-600 mb-1 block">版本</label>
                    <vort-input v-model="props.state.createBugForm.version" placeholder="请输入版本号" />
                </div>
                <div>
                    <label class="text-sm text-gray-600 mb-1 block">优先级</label>
                    <div class="relative" @click.stop>
                        <button
                            class="h-9 w-full px-3 border border-gray-300 rounded bg-white flex items-center justify-between hover:border-gray-400"
                            @click.stop="props.state.toggleCreateBugPriorityMenu()"
                        >
                            <span class="text-sm text-gray-700">{{ priorityOptions.find(p => p.value === props.state.createBugForm.priority)?.label || '请选择优先级' }}</span>
                            <span class="status-arrow-simple" :class="{ open: props.state.createBugPriorityDropdownOpen.value }" />
                        </button>
                        <div v-if="props.state.createBugPriorityDropdownOpen.value" class="absolute z-30 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-sm py-1">
                            <button
                                v-for="opt in priorityOptions"
                                :key="opt.value"
                                class="w-full text-left px-3 py-2 text-sm hover:bg-gray-50"
                                @click="props.state.selectCreateBugPriority(opt.value)"
                            >
                                {{ opt.label }}
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 标签 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">标签</label>
                <div class="flex flex-wrap gap-2">
                    <button
                        v-for="tag in createBugTagOptions"
                        :key="tag"
                        class="h-7 px-3 rounded-full text-xs border flex items-center gap-1 transition-colors"
                        :class="props.state.createBugForm.tags.includes(tag) ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-gray-300 hover:border-gray-400'"
                        @click="props.state.createBugForm.tags.includes(tag) ? props.state.createBugForm.tags.splice(props.state.createBugForm.tags.indexOf(tag), 1) : props.state.createBugForm.tags.push(tag)"
                    >
                        <span v-if="props.state.createBugForm.tags.includes(tag)" class="w-4 h-4 rounded-full bg-blue-500 text-white flex items-center justify-center text-[10px]">✓</span>
                        {{ tag }}
                    </button>
                </div>
            </div>

            <!-- 代码信息 -->
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="text-sm text-gray-600 mb-1 block">仓库</label>
                    <vort-select v-model="props.state.createBugForm.repo" placeholder="请选择仓库" class="w-full" allow-clear>
                        <vort-select-option v-for="r in createBugRepoOptions" :key="r" :value="r">{{ r }}</vort-select-option>
                    </vort-select>
                </div>
                <div>
                    <label class="text-sm text-gray-600 mb-1 block">分支</label>
                    <vort-select v-model="props.state.createBugForm.branch" placeholder="请选择分支" class="w-full" allow-clear>
                        <vort-select-option v-for="b in createBugBranchOptions" :key="b" :value="b">{{ b }}</vort-select-option>
                    </vort-select>
                </div>
            </div>

            <!-- 计划时间 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">计划时间</label>
                <vort-range-picker
                    v-model="props.state.createBugForm.planTime as DateRange"
                    value-format="YYYY-MM-DD"
                    :placeholder="['开始日期', '结束日期']"
                    class="w-full"
                />
            </div>

            <!-- 描述 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">描述</label>
                <vort-textarea v-model="props.state.createBugForm.description" :rows="6" placeholder="请输入缺陷描述" />
            </div>

            <!-- 备注 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">备注</label>
                <vort-textarea v-model="props.state.createBugForm.remark" :rows="2" placeholder="请输入备注" />
            </div>

            <!-- 附件 -->
            <div>
                <label class="text-sm text-gray-600 mb-1 block">附件</label>
                <input
                    ref="props.state.createAttachmentInputRef.value"
                    type="file"
                    multiple
                    class="hidden"
                    @change="props.state.onCreateAttachmentChange"
                />
                <div class="space-y-2">
                    <button class="h-9 px-4 border border-dashed border-gray-300 rounded text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600" @click="props.state.openCreateAttachmentDialog()">
                        + 添加附件
                    </button>
                    <div v-if="props.state.createBugAttachments.value.length" class="space-y-1">
                        <div v-for="att in props.state.createBugAttachments.value" :key="att.id" class="flex items-center justify-between h-9 px-3 bg-gray-50 rounded text-sm">
                            <span class="truncate flex-1">{{ att.name }}</span>
                            <span class="text-gray-400 text-xs mx-2">{{ formatFileSize(att.size) }}</span>
                            <button class="text-gray-400 hover:text-red-500" @click="props.state.removeCreateAttachment(att.id)">×</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 底部按钮 -->
        <template #footer>
            <div class="flex justify-end gap-3">
                <vort-button @click="closeDrawer">取消</vort-button>
                <vort-button variant="primary" @click="handleSubmit">确定</vort-button>
            </div>
        </template>
    </vort-drawer>
</template>

<style scoped>
@reference "../../../assets/styles/index.css";

.status-arrow-simple {
    @apply w-2 h-2 border-r-2 border-b-2 border-gray-400 -rotate-45 transition-transform;
}

.status-arrow-simple.open {
    @apply rotate-[135deg] -mt-0.5;
}
</style>
