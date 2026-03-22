<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { GripVertical, Pencil, ArrowRightLeft, Trash2, Plus } from "lucide-vue-next";
import { getVortflowTags, deleteVortflowTag, reorderVortflowTags } from "@/api";
import { message } from "@/components/vort/message";
import TagEditDialog from "./components/TagEditDialog.vue";
import TagMigrateDialog from "./components/TagMigrateDialog.vue";

interface TagItem {
    id: string;
    name: string;
    color: string;
    sort_order: number;
    usage_count: number;
}

const loading = ref(false);
const tags = ref<TagItem[]>([]);
const keyword = ref("");

const filteredTags = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) return tags.value;
    return tags.value.filter((t) => t.name.toLowerCase().includes(kw));
});

const editDialogOpen = ref(false);
const editDialogMode = ref<"add" | "edit">("add");
const editDialogData = ref<{ id?: string; name?: string; color?: string }>({});

const migrateDialogOpen = ref(false);
const migrateTag = ref<TagItem | null>(null);

const loadTags = async () => {
    loading.value = true;
    try {
        const res: any = await getVortflowTags();
        tags.value = (res?.items || []) as TagItem[];
    } catch {
        tags.value = [];
    } finally {
        loading.value = false;
    }
};

const handleAdd = () => {
    editDialogMode.value = "add";
    editDialogData.value = {};
    editDialogOpen.value = true;
};

const handleEdit = (row: TagItem) => {
    editDialogMode.value = "edit";
    editDialogData.value = { id: row.id, name: row.name, color: row.color };
    editDialogOpen.value = true;
};

const handleMigrate = (row: TagItem) => {
    migrateTag.value = row;
    migrateDialogOpen.value = true;
};

const handleDelete = async (row: TagItem) => {
    try {
        const res: any = await deleteVortflowTag(row.id);
        if (res?.error) {
            message.error(res.error);
            return;
        }
        message.success("标签已删除");
        loadTags();
    } catch (e: any) {
        message.error(e?.message || "删除失败");
    }
};

// Drag & drop reorder
const dragIndex = ref<number | null>(null);
const dragOverIndex = ref<number | null>(null);

const onDragStart = (index: number) => {
    dragIndex.value = index;
};

const onDragOver = (e: DragEvent, index: number) => {
    e.preventDefault();
    dragOverIndex.value = index;
};

const onDragEnd = async () => {
    if (dragIndex.value !== null && dragOverIndex.value !== null && dragIndex.value !== dragOverIndex.value) {
        const list = [...tags.value];
        const [moved] = list.splice(dragIndex.value, 1);
        list.splice(dragOverIndex.value, 0, moved!);
        tags.value = list;
        try {
            await reorderVortflowTags(list.map((t) => t.id));
        } catch {
            message.error("排序保存失败");
            loadTags();
        }
    }
    dragIndex.value = null;
    dragOverIndex.value = null;
};

onMounted(loadTags);
</script>

<template>
    <div>
        <div class="flex items-center justify-end mb-4 gap-3">
            <vort-input-search
                v-model="keyword"
                placeholder="搜索标签..."
                allow-clear
                class="w-[200px]"
            />
            <vort-button variant="primary" @click="handleAdd">
                <Plus :size="14" class="mr-1" /> 新建标签
            </vort-button>
        </div>

        <vort-table :data-source="filteredTags" :loading="loading" :pagination="false" row-key="id">
            <vort-table-column label="排序" :width="60">
                <template #default="{ index }">
                    <div
                        class="drag-handle"
                        draggable="true"
                        @dragstart="onDragStart(index)"
                        @dragover="(e: DragEvent) => onDragOver(e, index)"
                        @dragend="onDragEnd"
                    >
                        <GripVertical :size="16" class="text-gray-400" />
                    </div>
                </template>
            </vort-table-column>
            <vort-table-column label="标签" :width="160">
                <template #default="{ row }">
                    <vort-tag :color="row.color">{{ row.name }}</vort-tag>
                </template>
            </vort-table-column>
            <vort-table-column label="名称" prop="name" />
            <vort-table-column label="颜色" :width="80">
                <template #default="{ row }">
                    <span
                        class="inline-block w-5 h-5 rounded"
                        :style="{ backgroundColor: row.color }"
                    />
                </template>
            </vort-table-column>
            <vort-table-column label="操作" :width="280" fixed="right">
                <template #default="{ row }">
                    <div class="flex items-center gap-2 whitespace-nowrap">
                        <a class="text-sm text-blue-600 cursor-pointer inline-flex items-center gap-1" @click="handleEdit(row)">
                            <Pencil :size="13" /> 编辑
                        </a>
                        <vort-divider type="vertical" />
                        <a class="text-sm text-blue-600 cursor-pointer inline-flex items-center gap-1" @click="handleMigrate(row)">
                            <ArrowRightLeft :size="13" /> 数据迁移
                        </a>
                        <vort-divider type="vertical" />
                        <vort-popconfirm title="确认删除该标签？删除后已使用该标签的工作项将移除此标签。" @confirm="handleDelete(row)">
                            <a class="text-sm text-red-500 cursor-pointer inline-flex items-center gap-1">
                                <Trash2 :size="13" /> 删除
                            </a>
                        </vort-popconfirm>
                    </div>
                </template>
            </vort-table-column>
        </vort-table>

        <TagEditDialog
            v-model:open="editDialogOpen"
            :mode="editDialogMode"
            :data="editDialogData"
            @saved="loadTags"
        />

        <TagMigrateDialog
            v-model:open="migrateDialogOpen"
            :tag="migrateTag"
            :all-tags="tags"
            @saved="loadTags"
        />
    </div>
</template>

<style scoped>
.drag-handle {
    cursor: grab;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4px;
}
.drag-handle:active {
    cursor: grabbing;
}
</style>
