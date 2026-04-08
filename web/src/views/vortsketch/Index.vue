<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import {
    Button as VortButton, Spin as VortSpin, Input as VortInput,
    Dialog as VortDialog, message,
} from "@openvort/vort-ui";
import { Plus, Search, PencilRuler } from "lucide-vue-next";
import { getSketches, createSketch, updateSketch, deleteSketch, duplicateSketch } from "@/api";
import SketchCard from "./components/SketchCard.vue";
import SketchCreateDialog from "./components/SketchCreateDialog.vue";

interface SketchItem {
    id: string;
    name: string;
    description: string;
    project_id?: string;
    story_id?: string;
    story_type?: string;
    page_count: number;
    is_archived: boolean;
    created_at: string;
    updated_at: string;
    thumbnail_url?: string;
}

const loading = ref(false);
const sketches = ref<SketchItem[]>([]);
const keyword = ref("");

const showDialog = ref(false);
const editingSketch = ref<SketchItem | null>(null);

const deleteConfirmOpen = ref(false);
const deletingSketch = ref<SketchItem | null>(null);
const deleting = ref(false);

const filteredSketches = computed(() => {
    if (!keyword.value) return sketches.value;
    const kw = keyword.value.toLowerCase();
    return sketches.value.filter(s =>
        s.name.toLowerCase().includes(kw) || s.description.toLowerCase().includes(kw)
    );
});

async function loadSketches() {
    loading.value = true;
    try {
        const res: any = await getSketches({ page: 1, page_size: 100 });
        sketches.value = res?.items || [];
    } catch {
        message.error("加载原型列表失败");
    } finally {
        loading.value = false;
    }
}

function openCreate() {
    editingSketch.value = null;
    showDialog.value = true;
}

function handleCardClick(sketch: SketchItem) {
    window.open(`/vortsketch/${sketch.id}`, "_blank");
}

function handleEdit(sketch: SketchItem) {
    editingSketch.value = sketch;
    showDialog.value = true;
}

async function handleDialogSubmit(data: { name: string; description: string }) {
    if (editingSketch.value) {
        try {
            await updateSketch(editingSketch.value.id, data);
            showDialog.value = false;
            message.success("已更新");
            loadSketches();
        } catch {
            message.error("更新失败");
        }
    } else {
        try {
            const res: any = await createSketch(data);
            showDialog.value = false;
            message.success("原型已创建");
            window.open(`/vortsketch/${res.id}`, "_blank");
            loadSketches();
        } catch {
            message.error("创建失败");
        }
    }
}

async function handleDuplicate(sketch: SketchItem) {
    try {
        await duplicateSketch(sketch.id);
        message.success("已创建副本");
        loadSketches();
    } catch {
        message.error("创建副本失败");
    }
}

function handleDeleteRequest(sketch: SketchItem) {
    deletingSketch.value = sketch;
    deleteConfirmOpen.value = true;
}

async function confirmDelete() {
    if (!deletingSketch.value) return;
    deleting.value = true;
    try {
        await deleteSketch(deletingSketch.value.id);
        message.success("已删除");
        deleteConfirmOpen.value = false;
        loadSketches();
    } catch {
        message.error("删除失败");
    } finally {
        deleting.value = false;
    }
}

onMounted(() => {
    loadSketches();
});
</script>

<template>
    <div class="space-y-4">
        <!-- Header -->
        <div class="flex items-start justify-between">
            <div>
                <h1 class="text-xl font-semibold text-gray-900 flex items-center gap-2">
                    <PencilRuler :size="22" class="text-indigo-600" />
                    VortSketch
                </h1>
                <p class="text-sm text-gray-500 mt-1">AI 驱动的 UI 原型生成器 — 描述你想要的界面，AI 帮你画出来</p>
            </div>
            <VortButton type="primary" @click="openCreate">
                <Plus :size="16" class="mr-1" />
                新建原型
            </VortButton>
        </div>

        <!-- Content -->
        <div class="bg-white rounded-xl border p-5">
            <!-- Search -->
            <div class="flex items-center gap-3 mb-5">
                <VortInput
                    v-model="keyword"
                    placeholder="搜索原型..."
                    class="max-w-xs"
                >
                    <template #prefix>
                        <Search :size="14" class="text-gray-400" />
                    </template>
                </VortInput>
            </div>

            <!-- Grid -->
            <VortSpin :spinning="loading">
                <!-- Empty state -->
                <div v-if="filteredSketches.length === 0 && !loading" class="flex flex-col items-center justify-center py-20">
                    <div class="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center mb-4">
                        <PencilRuler :size="28" class="text-indigo-400" />
                    </div>
                    <h3 class="text-base font-medium text-gray-700 mb-1">还没有原型</h3>
                    <p class="text-sm text-gray-400 mb-4">描述你想要的界面，AI 帮你快速生成可交互的原型</p>
                    <VortButton type="primary" @click="openCreate">
                        <Plus :size="16" class="mr-1" />
                        创建第一个原型
                    </VortButton>
                </div>

                <!-- Cards -->
                <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    <SketchCard
                        v-for="sketch in filteredSketches"
                        :key="sketch.id"
                        :sketch="sketch"
                        @click="handleCardClick"
                        @edit="handleEdit"
                        @duplicate="handleDuplicate"
                        @delete="handleDeleteRequest"
                    />
                </div>
            </VortSpin>
        </div>

        <!-- Create / Edit Dialog -->
        <SketchCreateDialog
            :open="showDialog"
            :edit-data="editingSketch ? { id: editingSketch.id, name: editingSketch.name, description: editingSketch.description } : null"
            @update:open="showDialog = $event"
            @submit="handleDialogSubmit"
        />

        <!-- Delete Confirmation -->
        <VortDialog
            :open="deleteConfirmOpen"
            title="删除原型"
            width="420px"
            @update:open="deleteConfirmOpen = $event"
        >
            <p class="text-sm text-gray-600 py-2">
                确定要删除原型「<span class="font-medium text-gray-900">{{ deletingSketch?.name }}</span>」吗？此操作不可撤销，所有页面数据将被永久删除。
            </p>
            <template #footer>
                <div class="flex justify-end gap-2">
                    <VortButton @click="deleteConfirmOpen = false">取消</VortButton>
                    <VortButton type="primary" danger :loading="deleting" @click="confirmDelete">删除</VortButton>
                </div>
            </template>
        </VortDialog>
    </div>
</template>
