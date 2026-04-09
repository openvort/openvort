<script setup lang="ts">
import { ref } from "vue";
import { onClickOutside } from "@vueuse/core";

export type ViewMode = "list" | "gantt";

const props = defineProps<{
    modelValue: ViewMode;
}>();

const emit = defineEmits<{
    "update:modelValue": [value: ViewMode];
}>();

const dropdownOpen = ref(false);
const wrapperRef = ref<HTMLElement | null>(null);

onClickOutside(wrapperRef, () => { dropdownOpen.value = false; });

const options: { value: ViewMode; label: string; icon: string }[] = [
    { value: "list", label: "列表", icon: "list" },
    { value: "gantt", label: "甘特图", icon: "gantt" },
];

const currentOption = () => options.find(o => o.value === props.modelValue) || options[0]!;

function select(value: ViewMode) {
    emit("update:modelValue", value);
    dropdownOpen.value = false;
}
</script>

<template>
    <div ref="wrapperRef" class="view-mode-toggle">
        <button
            type="button"
            class="view-mode-btn"
            @click="dropdownOpen = !dropdownOpen"
        >
            <svg v-if="currentOption().icon === 'list'" class="view-mode-icon" width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
            <svg v-else class="view-mode-icon" width="14" height="14" viewBox="0 0 1024 1024" fill="currentColor">
                <path d="M856 672c22.092 0 40 17.908 40 40v144c0 22.092-17.908 40-40 40H376c-22.092 0-40-17.908-40-40v-144c0-22.092 17.908-40 40-40z m-40 80H416v64h400v-64z m40-352c22.092 0 40 17.908 40 40v144c0 22.092-17.908 40-40 40H376c-22.092 0-40-17.908-40-40v-144c0-22.092 17.908-40 40-40z m-40 80H416v64h400v-64z m-168-352c22.092 0 40 17.908 40 40v144c0 22.092-17.908 40-40 40H168c-22.092 0-40-17.908-40-40V168c0-22.092 17.908-40 40-40z m-40 80H208v64h400V208z"/>
            </svg>
            <span class="view-mode-label">{{ currentOption().label }}</span>
            <svg
                class="view-mode-arrow"
                :class="{ open: dropdownOpen }"
                width="12" height="12" viewBox="0 0 12 12" fill="none"
            >
                <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </button>

        <Transition name="dropdown">
            <div v-if="dropdownOpen" class="view-mode-dropdown">
                <button
                    v-for="opt in options"
                    :key="opt.value"
                    type="button"
                    class="view-mode-option"
                    :class="{ active: opt.value === modelValue }"
                    @click="select(opt.value)"
                >
                    <svg v-if="opt.icon === 'list'" class="view-mode-option-icon" width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path d="M2 4h12M2 8h12M2 12h12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    </svg>
                    <svg v-else class="view-mode-option-icon" width="14" height="14" viewBox="0 0 1024 1024" fill="currentColor">
                        <path d="M856 672c22.092 0 40 17.908 40 40v144c0 22.092-17.908 40-40 40H376c-22.092 0-40-17.908-40-40v-144c0-22.092 17.908-40 40-40z m-40 80H416v64h400v-64z m40-352c22.092 0 40 17.908 40 40v144c0 22.092-17.908 40-40 40H376c-22.092 0-40-17.908-40-40v-144c0-22.092 17.908-40 40-40z m-40 80H416v64h400v-64z m-168-352c22.092 0 40 17.908 40 40v144c0 22.092-17.908 40-40 40H168c-22.092 0-40-17.908-40-40V168c0-22.092 17.908-40 40-40z m-40 80H208v64h400V208z"/>
                    </svg>
                    <span>{{ opt.label }}</span>
                    <svg v-if="opt.value === modelValue" class="view-mode-check" width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path d="M3.5 8.5l3 3 6-7" stroke="var(--vort-primary, #1456f0)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                </button>
            </div>
        </Transition>
    </div>
</template>

<style scoped>
.view-mode-toggle {
    position: relative;
}

.view-mode-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 10px;
    border: 1px solid #d9d9d9;
    border-radius: 6px;
    background: #fff;
    color: #374151;
    font-size: 13px;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.2s;
}

.view-mode-btn:hover {
    border-color: var(--vort-primary, #1456f0);
    color: var(--vort-primary, #1456f0);
}

.view-mode-icon {
    flex-shrink: 0;
}

.view-mode-label {
    font-weight: 500;
}

.view-mode-arrow {
    transition: transform 0.2s;
}
.view-mode-arrow.open {
    transform: rotate(180deg);
}

.view-mode-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    min-width: 140px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08), 0 3px 6px -4px rgba(0, 0, 0, 0.12);
    padding: 4px;
    z-index: 50;
}

.view-mode-option {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    border: none;
    background: transparent;
    text-align: left;
    font-size: 14px;
    color: #1e293b;
    border-radius: 6px;
    cursor: pointer;
    transition: background 0.15s;
    white-space: nowrap;
}

.view-mode-option:hover {
    background: rgba(0, 0, 0, 0.04);
}

.view-mode-option.active {
    background: rgba(20, 86, 240, 0.06);
}

.view-mode-option-icon {
    flex-shrink: 0;
}

.view-mode-check {
    margin-left: auto;
}

.dropdown-enter-active,
.dropdown-leave-active {
    transition: opacity 0.15s, transform 0.15s;
}
.dropdown-enter-from,
.dropdown-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}
</style>
