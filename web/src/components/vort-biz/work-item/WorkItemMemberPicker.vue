<script setup lang="ts">
import { computed, reactive, watch } from "vue";
import PopoverSelect from "@/components/vort-biz/popover-select/PopoverSelect.vue";

type MemberPickerMode = "owner" | "assignee" | "collaborators";

interface MemberGroup {
    label: string;
    members: string[];
}

interface Props {
    mode?: MemberPickerMode;
    owner?: string;
    collaborators?: string[];
    groups?: MemberGroup[];
    disabled?: boolean;
    placeholder?: string;
    searchPlaceholder?: string;
    dropdownWidth?: number | string;
    dropdownMaxHeight?: number;
    showAllOption?: boolean;
    showUnassigned?: boolean;
    allLabel?: string;
    allValue?: string;
    unassignedLabel?: string;
    unassignedValue?: string;
    collapsible?: boolean;
    bordered?: boolean;
    getAvatarBg?: (name: string) => string;
    getAvatarLabel?: (name: string) => string;
    getAvatarUrl?: (name: string) => string;
    filterScore?: (member: string, keyword: string) => number;
}

const props = withDefaults(defineProps<Props>(), {
    mode: "owner",
    owner: "",
    collaborators: () => [],
    groups: () => [],
    disabled: false,
    placeholder: "请选择成员",
    searchPlaceholder: "搜索成员...",
    dropdownWidth: 260,
    dropdownMaxHeight: 280,
    showAllOption: false,
    showUnassigned: false,
    allLabel: "全部",
    allValue: "",
    unassignedLabel: "未指派",
    unassignedValue: "未指派",
    collapsible: true,
    bordered: true,
    getAvatarBg: undefined,
    getAvatarLabel: undefined,
    getAvatarUrl: undefined,
    filterScore: undefined
});

const emit = defineEmits<{
    "update:owner": [value: string];
    "update:collaborators": [value: string[]];
    change: [payload: { owner: string; collaborators: string[] }];
}>();

const open = defineModel<boolean>("open", { default: false });
const keyword = defineModel<string>("keyword", { default: "" });

const groupOpen = reactive<Record<string, boolean>>({});

const ensureGroupOpen = () => {
    props.groups.forEach((group) => {
        if (groupOpen[group.label] === undefined) {
            groupOpen[group.label] = true;
        }
    });
};

watch(
    () => props.groups,
    () => ensureGroupOpen(),
    { immediate: true, deep: true }
);

const avatarBgPalette = ["#2f80ed", "#5b8ff9", "#9b59b6", "#27ae60", "#f39c12", "#e67e22", "#16a085", "#8b44ad"];

const fallbackAvatarBg = (name: string): string => {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
    }
    return avatarBgPalette[hash % avatarBgPalette.length]!;
};

const fallbackAvatarLabel = (name: string): string => name.slice(0, 1).toUpperCase();

const getAvatarBg = (name: string) => props.getAvatarBg?.(name) || fallbackAvatarBg(name);
const getAvatarLabel = (name: string) => props.getAvatarLabel?.(name) || fallbackAvatarLabel(name);
const getAvatarUrl = (name: string) => props.getAvatarUrl?.(name) || "";

const getDefaultFilterScore = (member: string, search: string): number => {
    const kw = search.trim().toLowerCase();
    if (!kw) return 1;
    const normalized = member.toLowerCase();
    if (normalized === kw) return 120;
    if (normalized.startsWith(kw)) return 100;
    if (normalized.includes(kw)) return 60;
    return 0;
};

const filteredGroups = computed(() => {
    const kw = keyword.value.trim();
    if (!kw) return props.groups;

    return props.groups
        .map((group) => ({
            ...group,
            members: group.members
                .map((member, index) => ({
                    member,
                    index,
                    score: props.filterScore?.(member, kw) ?? getDefaultFilterScore(member, kw)
                }))
                .filter((item) => item.score > 0)
                .sort((a, b) => b.score - a.score || a.index - b.index)
                .map((item) => item.member)
        }))
        .filter((group) => group.members.length > 0);
});

const currentOwner = computed(() => props.owner || "");
const currentCollaborators = computed(() => props.collaborators || []);

const isOwner = (member: string) => currentOwner.value === member;
const isCollaborator = (member: string) => currentCollaborators.value.includes(member);

const emitChange = (nextOwner = currentOwner.value, nextCollaborators = currentCollaborators.value) => {
    emit("change", {
        owner: nextOwner,
        collaborators: [...nextCollaborators]
    });
};

const closeAndResetSearch = () => {
    open.value = false;
    keyword.value = "";
};

const setOwner = (member: string) => {
    const nextOwner = member;
    const nextCollaborators = currentCollaborators.value.filter((item) => item !== member);
    emit("update:owner", nextOwner);
    emit("update:collaborators", nextCollaborators);
    emitChange(nextOwner, nextCollaborators);
    if (props.mode === "owner") {
        closeAndResetSearch();
    }
};

const toggleCollaborator = (member: string) => {
    const nextCollaborators = [...currentCollaborators.value];

    if (isOwner(member)) {
        emit("update:owner", "");
        if (!nextCollaborators.includes(member)) {
            nextCollaborators.unshift(member);
        }
        emit("update:collaborators", nextCollaborators);
        emitChange("", nextCollaborators);
        return;
    }

    const index = nextCollaborators.indexOf(member);
    if (index >= 0) {
        nextCollaborators.splice(index, 1);
    } else {
        nextCollaborators.push(member);
    }
    emit("update:collaborators", nextCollaborators);
    emitChange(currentOwner.value, nextCollaborators);
};

const toggleGroup = (group: string) => {
    if (!props.collapsible) return;
    groupOpen[group] = !groupOpen[group];
};

const visibleMembers = (group: MemberGroup) => {
    if (!props.collapsible) return group.members;
    return groupOpen[group.label] ? group.members : [];
};
</script>

<template>
    <PopoverSelect
        v-model:open="open"
        v-model:keyword="keyword"
        :disabled="disabled"
        :placeholder="placeholder"
        :search-placeholder="searchPlaceholder"
        :show-search="true"
        :dropdown-width="dropdownWidth"
        :dropdown-max-height="dropdownMaxHeight"
        :bordered="bordered"
    >
        <template #trigger="{ open: triggerOpen }">
            <slot
                name="trigger"
                :open="triggerOpen"
                :owner="currentOwner"
                :collaborators="currentCollaborators"
            >
                <button type="button" class="member-picker-default-trigger" :disabled="disabled">
                    <span class="truncate">{{ currentOwner || placeholder }}</span>
                </button>
            </slot>
        </template>

        <div class="member-picker-content">
            <template v-if="mode === 'owner'">
                <div
                    v-if="showAllOption"
                    class="member-picker-row"
                    :class="{ 'is-active': currentOwner === allValue }"
                    @click.stop="setOwner(allValue)"
                >
                    <div class="member-picker-row-left">
                        <vort-checkbox
                            :checked="currentOwner === allValue"
                            @click.stop
                            @update:checked="setOwner(allValue)"
                        />
                        <span class="member-picker-name">{{ allLabel }}</span>
                    </div>
                </div>

                <div
                    v-if="showUnassigned"
                    class="member-picker-row"
                    :class="{ 'is-active': currentOwner === unassignedValue }"
                    @click.stop="setOwner(unassignedValue)"
                >
                    <div class="member-picker-row-left">
                        <vort-checkbox
                            :checked="currentOwner === unassignedValue"
                            @click.stop
                            @update:checked="setOwner(unassignedValue)"
                        />
                        <span class="member-picker-name">{{ unassignedLabel }}</span>
                    </div>
                </div>
            </template>

            <div v-for="group in filteredGroups" :key="group.label" class="member-picker-group">
                <button
                    type="button"
                    class="member-picker-group-header"
                    @click.stop="toggleGroup(group.label)"
                >
                    <span>{{ group.label }}（{{ group.members.length }}）</span>
                    <span
                        v-if="collapsible"
                        class="status-arrow-simple"
                        :class="{ open: groupOpen[group.label] }"
                    />
                </button>

                <div
                    v-for="member in visibleMembers(group)"
                    :key="`${group.label}-${member}`"
                    class="member-picker-row"
                    :class="{
                        'is-active': mode === 'owner' ? isOwner(member) : isCollaborator(member),
                        'is-owner-row': mode === 'assignee' && isOwner(member),
                        'is-collaborator-row': mode === 'assignee' && !isOwner(member) && isCollaborator(member)
                    }"
                >
                    <template v-if="mode === 'assignee'">
                        <div class="member-picker-row-left">
                            <span
                                class="member-picker-avatar"
                                :style="{ backgroundColor: getAvatarBg(member) }"
                            >
                                <img
                                    v-if="getAvatarUrl(member)"
                                    :src="getAvatarUrl(member)"
                                    class="w-full h-full object-cover"
                                />
                                <template v-else>{{ getAvatarLabel(member) }}</template>
                            </span>
                            <span class="member-picker-name">{{ member }}</span>
                        </div>

                        <div class="member-picker-row-actions">
                            <button
                                type="button"
                                class="member-picker-role-btn owner"
                                :class="{ 'is-active': isOwner(member) }"
                                @click.stop="setOwner(member)"
                            >
                                负责人
                            </button>
                            <button
                                type="button"
                                class="member-picker-role-btn collaborator"
                                :class="{ 'is-active': isCollaborator(member) }"
                                @click.stop="toggleCollaborator(member)"
                            >
                                协作者
                            </button>
                        </div>
                    </template>

                    <template v-else>
                        <div class="member-picker-row-left" @click.stop="mode === 'owner' ? setOwner(member) : toggleCollaborator(member)">
                            <vort-checkbox
                                :checked="mode === 'owner' ? isOwner(member) : isCollaborator(member)"
                                @click.stop
                                @update:checked="mode === 'owner' ? setOwner(member) : toggleCollaborator(member)"
                            />
                            <span
                                class="member-picker-avatar"
                                :style="{ backgroundColor: getAvatarBg(member) }"
                            >
                                <img
                                    v-if="getAvatarUrl(member)"
                                    :src="getAvatarUrl(member)"
                                    class="w-full h-full object-cover"
                                />
                                <template v-else>{{ getAvatarLabel(member) }}</template>
                            </span>
                            <span class="member-picker-name">{{ member }}</span>
                        </div>
                    </template>
                </div>
            </div>
        </div>
    </PopoverSelect>
</template>

<style scoped>
.member-picker-default-trigger {
    width: 100%;
    text-align: left;
}

.member-picker-content {
    padding: 4px;
}

.member-picker-group + .member-picker-group {
    margin-top: 4px;
}

.member-picker-group-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    height: 40px;
    padding: 0 8px;
    border-radius: 4px;
    background: #f8fafc;
    color: #334155;
    font-size: 13px;
    text-align: left;
}

.member-picker-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 36px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s ease;
}

.member-picker-row:hover {
    background: rgba(0, 0, 0, 0.04);
}

.member-picker-row.is-active {
    background: #f1f5f9;
}

.member-picker-row.is-owner-row {
    background: #eff6ff;
}

.member-picker-row.is-collaborator-row {
    background: #ecfdf5;
}

.member-picker-row-left {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 0;
    flex: 1;
}

.member-picker-avatar {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 9999px;
    overflow: hidden;
    flex-shrink: 0;
    color: #fff;
    font-size: 12px;
    line-height: 1;
}

.member-picker-name {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    color: #334155;
    font-size: 14px;
    line-height: 20px;
}

.member-picker-row-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: 12px;
}

.member-picker-role-btn {
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid transparent;
    font-size: 12px;
    line-height: 18px;
    transition: all 0.15s ease;
}

.member-picker-role-btn.owner {
    color: #3b82f6;
    border-color: rgba(59, 130, 246, 0.4);
}

.member-picker-role-btn.owner.is-active {
    background: #3b82f6;
    color: #fff;
    border-color: #3b82f6;
}

.member-picker-role-btn.collaborator {
    color: #10b981;
    border-color: rgba(16, 185, 129, 0.4);
}

.member-picker-role-btn.collaborator.is-active {
    background: #10b981;
    color: #fff;
    border-color: #10b981;
}
</style>
