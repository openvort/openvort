<script setup lang="ts">
import { computed, ref } from "vue";
import { ChevronDown, Settings, Plus, Pin } from "lucide-vue-next";
import type { VortFlowView } from "../composables/useVortFlowViews";

interface Props {
    views: VortFlowView[];
    selectedId: string;
    personalViews?: { id: string; name: string }[];
    sharedViews?: { id: string; name: string }[];
}

const props = withDefaults(defineProps<Props>(), {
    personalViews: () => [],
    sharedViews: () => [],
});

const emit = defineEmits<{
    select: [id: string];
    unpin: [];
    manage: [];
    createView: [];
}>();

const systemExpanded = ref(true);
const personalExpanded = ref(true);
const sharedExpanded = ref(true);

const systemViews = computed(() => props.views);
</script>

<template>
    <div class="view-sidebar">
        <div class="sidebar-header">
            <span class="sidebar-title">视图</span>
            <button type="button" class="sidebar-pin-btn" title="取消固定" @click="emit('unpin')">
                <Pin :size="14" />
            </button>
        </div>

        <div class="sidebar-section">
            <div class="section-header" @click="systemExpanded = !systemExpanded">
                <span class="section-title">系统视图</span>
                <ChevronDown
                    :size="14"
                    class="section-arrow"
                    :class="{ collapsed: !systemExpanded }"
                />
            </div>
            <div v-show="systemExpanded" class="section-items">
                <div
                    v-for="view in systemViews"
                    :key="view.id"
                    class="view-item"
                    :class="{ active: selectedId === view.id }"
                    @click="emit('select', view.id)"
                >
                    {{ view.name }}
                </div>
            </div>
        </div>

        <div v-if="personalViews.length > 0" class="sidebar-section">
            <div class="section-header" @click="personalExpanded = !personalExpanded">
                <span class="section-title">个人视图</span>
                <div class="section-actions">
                    <button type="button" class="section-action-btn" @click.stop="emit('manage')">
                        <Settings :size="12" />
                    </button>
                    <button type="button" class="section-action-btn" @click.stop="emit('createView')">
                        <Plus :size="12" />
                    </button>
                    <ChevronDown
                        :size="14"
                        class="section-arrow"
                        :class="{ collapsed: !personalExpanded }"
                    />
                </div>
            </div>
            <div v-show="personalExpanded" class="section-items">
                <div
                    v-for="view in personalViews"
                    :key="view.id"
                    class="view-item"
                    :class="{ active: selectedId === view.id }"
                    @click="emit('select', view.id)"
                >
                    {{ view.name }}
                </div>
            </div>
        </div>

        <div v-if="sharedViews.length > 0" class="sidebar-section">
            <div class="section-header" @click="sharedExpanded = !sharedExpanded">
                <span class="section-title">公共视图</span>
                <div class="section-actions">
                    <button type="button" class="section-action-btn" @click.stop="emit('manage')">
                        <Settings :size="12" />
                    </button>
                    <button type="button" class="section-action-btn" @click.stop="emit('createView')">
                        <Plus :size="12" />
                    </button>
                    <ChevronDown
                        :size="14"
                        class="section-arrow"
                        :class="{ collapsed: !sharedExpanded }"
                    />
                </div>
            </div>
            <div v-show="sharedExpanded" class="section-items">
                <div
                    v-for="view in sharedViews"
                    :key="view.id"
                    class="view-item"
                    :class="{ active: selectedId === view.id }"
                    @click="emit('select', view.id)"
                >
                    {{ view.name }}
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.view-sidebar {
    width: 220px;
    background: #fff;
    border-right: 1px solid #f0f0f0;
    border-radius: 12px;
    padding: 12px 0;
    flex-shrink: 0;
    overflow-y: auto;
}
.sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    margin-bottom: 4px;
}
.sidebar-title {
    font-weight: 600;
    font-size: 14px;
    color: #333;
}
.sidebar-pin-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 4px;
    background: transparent;
    color: var(--vort-primary);
    cursor: pointer;
    transition: background 0.2s;
}
.sidebar-pin-btn:hover {
    background: var(--vort-primary-bg);
}
.sidebar-section {
    margin-bottom: 4px;
}
.section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 16px;
    cursor: pointer;
    user-select: none;
}
.section-title {
    font-size: 12px;
    color: #999;
    font-weight: 500;
}
.section-actions {
    display: flex;
    align-items: center;
    gap: 2px;
}
.section-action-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    border: none;
    border-radius: 3px;
    background: transparent;
    color: #999;
    cursor: pointer;
    transition: all 0.15s;
}
.section-action-btn:hover {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
}
.section-arrow {
    color: #999;
    transition: transform 0.2s;
    flex-shrink: 0;
}
.section-arrow.collapsed {
    transform: rotate(-90deg);
}
.section-items {
    padding: 2px 8px;
}
.view-item {
    padding: 7px 12px;
    border-radius: 6px;
    font-size: 13px;
    color: #333;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.view-item:hover {
    background: rgba(0, 0, 0, 0.04);
}
.view-item.active {
    color: var(--vort-primary);
    background: var(--vort-primary-bg);
    font-weight: 500;
}
</style>
