<script setup lang="ts">
import { ref, computed } from "vue";
import { Dialog, Button, Input, Switch, Checkbox } from "@/components/vort";
import { GripVertical, Pencil, Trash2, Plus, Search } from "lucide-vue-next";
import ViewCreateDialog from "./ViewCreateDialog.vue";
import type { VortFlowView } from "../composables/useVortFlowViews";

interface ManagedView {
    id: string;
    name: string;
    scope: "system" | "shared" | "personal";
    visible: boolean;
    editable: boolean;
}

const open = defineModel<boolean>("open", { default: false });

const props = defineProps<{
    views: VortFlowView[];
}>();

const emit = defineEmits<{
    createView: [data: { name: string; scope: "personal" | "shared" }];
    deleteView: [id: string];
    toggleView: [id: string, visible: boolean];
}>();

const searchKeyword = ref("");
const showCreateDialog = ref(false);

const managedViews = ref<ManagedView[]>([
    { id: "all", name: "全部工作项", scope: "system", visible: true, editable: false },
    { id: "my_participated", name: "我参与的", scope: "system", visible: true, editable: false },
    { id: "my_assigned", name: "我负责的", scope: "system", visible: true, editable: false },
    { id: "parent_only", name: "父级工作项", scope: "system", visible: true, editable: false },
    { id: "my_created", name: "我创建的", scope: "system", visible: true, editable: false },
]);

const filteredViews = computed(() => {
    const kw = searchKeyword.value.trim().toLowerCase();
    if (!kw) return managedViews.value;
    return managedViews.value.filter(v => v.name.toLowerCase().includes(kw));
});

const scopeLabel = (scope: string) => {
    if (scope === "system") return "系统";
    if (scope === "shared") return "公共";
    return "个人";
};

const handleCreateView = (data: { name: string; scope: "personal" | "shared" }) => {
    managedViews.value.push({
        id: `custom_${Date.now()}`,
        name: data.name,
        scope: data.scope,
        visible: true,
        editable: true,
    });
    emit("createView", data);
    showCreateDialog.value = false;
};

const handleDeleteView = (id: string) => {
    managedViews.value = managedViews.value.filter(v => v.id !== id);
    emit("deleteView", id);
};

const handleToggleView = (view: ManagedView) => {
    view.visible = !view.visible;
    emit("toggleView", view.id, view.visible);
};
</script>

<template>
    <Dialog v-model:open="open" title="视图管理" width="680px">
        <div class="view-manage-content">
            <div class="view-manage-toolbar">
                <div class="search-wrapper">
                    <Input
                        v-model:value="searchKeyword"
                        placeholder="请输入视图名称"
                        allow-clear
                        size="small"
                    >
                        <template #suffix>
                            <Search :size="14" class="text-gray-400" />
                        </template>
                    </Input>
                </div>
                <Button type="primary" @click="showCreateDialog = true">
                    新建视图
                </Button>
            </div>

            <div class="view-list-header">
                <span class="col-order">顺序</span>
                <span class="col-name">名称</span>
                <span class="col-type">类型</span>
                <span class="col-show">显示</span>
                <span class="col-ops">操作</span>
            </div>

            <div class="view-list">
                <div v-for="view in filteredViews" :key="view.id" class="view-list-row">
                    <span class="col-order">
                        <GripVertical :size="14" class="text-gray-300 cursor-grab" />
                    </span>
                    <span class="col-name">{{ view.name }}</span>
                    <span class="col-type">{{ scopeLabel(view.scope) }}</span>
                    <span class="col-show">
                        <Checkbox :checked="view.visible" @update:checked="handleToggleView(view)" />
                    </span>
                    <span class="col-ops">
                        <button type="button" class="op-btn" :disabled="!view.editable">
                            <Pencil :size="14" />
                        </button>
                        <button
                            type="button"
                            class="op-btn"
                            :disabled="!view.editable"
                            @click="view.editable && handleDeleteView(view.id)"
                        >
                            <Trash2 :size="14" />
                        </button>
                    </span>
                </div>
            </div>
        </div>

        <template #footer>
            <Button @click="open = false">关闭</Button>
        </template>
    </Dialog>

    <ViewCreateDialog v-model:open="showCreateDialog" @create="handleCreateView" />
</template>

<style scoped>
.view-manage-content {
    min-height: 300px;
}
.view-manage-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
}
.search-wrapper {
    flex: 1;
}
.view-list-header {
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
    font-size: 12px;
    color: #999;
}
.view-list-row {
    display: flex;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #f5f5f5;
    font-size: 13px;
    transition: background 0.15s;
}
.view-list-row:hover {
    background: rgba(0, 0, 0, 0.02);
}
.col-order { width: 50px; text-align: center; flex-shrink: 0; }
.col-name { flex: 1; min-width: 0; }
.col-type { width: 80px; text-align: center; flex-shrink: 0; color: #666; }
.col-show { width: 60px; text-align: center; flex-shrink: 0; }
.col-ops { width: 80px; display: flex; gap: 4px; justify-content: center; flex-shrink: 0; }
.op-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: #999;
    cursor: pointer;
    transition: all 0.2s;
}
.op-btn:hover:not(:disabled) {
    color: #4096ff;
    background: rgba(64, 150, 255, 0.08);
}
.op-btn:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}
</style>
