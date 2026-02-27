<script setup lang="ts">
import { ref, computed } from "vue";
import Tag from "./Tag.vue";
import { CloseOutlined } from "@/components/vort/icons";

defineOptions({ name: "VortDraggableTags" });

/** Vort DraggableTags - 可拖拽排序的标签组 */

export interface TagItem {
    /** 标签唯一标识 */
    key: string | number;
    /** 标签内容 */
    label: string;
    /** 标签颜色 */
    color?: string;
    /** 是否可关闭 */
    closable?: boolean;
}

interface Props {
    /** 标签数据列表 */
    modelValue: TagItem[];
    /** 是否可拖拽 */
    draggable?: boolean;
    /** 是否显示拖拽提示图标 */
    showDragIcon?: boolean;
    /** 是否有边框 */
    bordered?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    draggable: true,
    showDragIcon: false,
    bordered: true
});

const emit = defineEmits<{
    /** 标签顺序变化 */
    "update:modelValue": [value: TagItem[]];
    /** 拖拽结束 */
    dragEnd: [value: TagItem[]];
    /** 标签关闭 */
    close: [item: TagItem, index: number];
}>();

// 定义插槽类型
defineSlots<{
    /** 自定义标签内容 */
    tag?: (props: { item: TagItem; index: number }) => unknown;
}>();

// 拖拽状态
const dragIndex = ref<number | null>(null);
const dropIndex = ref<number | null>(null);
const isDragging = ref(false);

// 实时预览列表
const previewList = computed(() => {
    if (!isDragging.value || dragIndex.value === null || dropIndex.value === null) {
        return props.modelValue;
    }

    if (dragIndex.value === dropIndex.value) {
        return props.modelValue;
    }

    // 创建预览排序
    const list = [...props.modelValue];
    const [removed] = list.splice(dragIndex.value, 1);
    list.splice(dropIndex.value, 0, removed!);
    return list;
});

// 计算容器类名
const containerClasses = computed(() => {
    const classes = ["vort-draggable-tags"];
    if (props.class) classes.push(props.class);
    return classes;
});

// 获取标签包装器类名
const getWrapperClasses = (item: TagItem) => {
    const classes = ["vort-tag-wrapper"];

    if (props.draggable) {
        classes.push("vort-tag-wrapper-draggable");
    }

    // 正在拖拽的标签
    if (isDragging.value && dragIndex.value !== null) {
        const originalItem = props.modelValue[dragIndex.value];
        if (originalItem && originalItem.key === item.key) {
            classes.push("vort-tag-wrapper-dragging");
        }
    }

    return classes;
};

// 通过 key 找到原始索引
const getOriginalIndex = (key: string | number): number => {
    return props.modelValue.findIndex((item) => item.key === key);
};

// 开始拖拽
const handleDragStart = (e: DragEvent, item: TagItem) => {
    if (!props.draggable) return;

    const originalIndex = getOriginalIndex(item.key);

    isDragging.value = true;
    dragIndex.value = originalIndex;
    dropIndex.value = originalIndex;

    // 设置拖拽数据和效果
    if (e.dataTransfer) {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", String(item.key));

        // 创建自定义拖拽图像
        const currentTarget = e.currentTarget as HTMLElement | null;
        if (currentTarget) {
            // 创建克隆元素作为拖拽图像（注意：克隆节点会被插入到 body，scoped 样式无法命中）
            const clone = currentTarget.cloneNode(true) as HTMLElement;

            // 把原始节点的计算样式复制到克隆节点，保证拖拽图像样式与页面展示一致
            const copyComputedStyle = (source: HTMLElement, target: HTMLElement) => {
                const computed = window.getComputedStyle(source);
                for (const prop of computed) {
                    target.style.setProperty(prop, computed.getPropertyValue(prop), computed.getPropertyPriority(prop));
                }
            };

            copyComputedStyle(currentTarget, clone);
            const sourceChildren = currentTarget.querySelectorAll<HTMLElement>("*");
            const targetChildren = clone.querySelectorAll<HTMLElement>("*");
            sourceChildren.forEach((el, idx) => {
                const targetEl = targetChildren[idx];
                if (!targetEl) return;
                copyComputedStyle(el, targetEl);
            });

            clone.style.position = "absolute";
            clone.style.top = "-9999px";
            clone.style.left = "-9999px";
            clone.style.opacity = "0.9";
            clone.style.transform = "scale(1.05)";
            clone.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
            document.body.appendChild(clone);

            e.dataTransfer.setDragImage(clone, currentTarget.offsetWidth / 2, currentTarget.offsetHeight / 2);

            // 延迟删除克隆元素
            requestAnimationFrame(() => {
                document.body.removeChild(clone);
            });
        }
    }
};

// 拖拽经过 - 使用预览列表中的索引
const handleDragOver = (e: DragEvent, previewIndex: number) => {
    if (!props.draggable || dragIndex.value === null) return;

    e.preventDefault();
    if (e.dataTransfer) {
        e.dataTransfer.dropEffect = "move";
    }

    // 获取预览列表中该位置对应的原始索引
    const item = previewList.value[previewIndex];
    if (!item) return;

    const targetOriginalIndex = getOriginalIndex(item.key);

    // 如果是拖拽的元素本身，使用预览索引作为目标
    if (targetOriginalIndex === dragIndex.value) {
        // 保持当前 dropIndex
        return;
    }

    // 更新放置位置
    if (dropIndex.value !== targetOriginalIndex) {
        dropIndex.value = targetOriginalIndex;
    }
};

// 拖拽结束
const handleDragEnd = () => {
    // 执行排序
    if (dragIndex.value !== null && dropIndex.value !== null && dragIndex.value !== dropIndex.value) {
        const newList = [...props.modelValue];
        const [removed] = newList.splice(dragIndex.value, 1);
        newList.splice(dropIndex.value, 0, removed!);

        emit("update:modelValue", newList);
        emit("dragEnd", newList);
    }

    // 重置状态
    isDragging.value = false;
    dragIndex.value = null;
    dropIndex.value = null;
};

// 放置
const handleDrop = (e: DragEvent) => {
    if (!props.draggable) return;
    e.preventDefault();
    handleDragEnd();
};

// 关闭标签
const handleClose = (e: MouseEvent, item: TagItem) => {
    e.stopPropagation();
    e.preventDefault();

    const index = getOriginalIndex(item.key);
    const newList = props.modelValue.filter((_, i) => i !== index);
    emit("update:modelValue", newList);
    emit("close", item, index);
};
</script>

<template>
    <div :class="containerClasses" @dragover.prevent @drop="handleDrop">
        <TransitionGroup name="tag-sort">
            <div
                v-for="(item, index) in previewList"
                :key="item.key"
                :draggable="draggable"
                :class="getWrapperClasses(item)"
                @dragstart="handleDragStart($event, item)"
                @dragover="handleDragOver($event, index)"
                @dragend="handleDragEnd"
            >
                <slot name="tag" :item="item" :index="index">
                    <Tag :color="item.color" :bordered="bordered" :closable="item.closable">
                        <template v-if="draggable && showDragIcon" #icon>
                            <svg aria-hidden="true" class="vort-tag-drag-icon" viewBox="0 0 1024 1024" width="12" height="12">
                                <path
                                    d="M316.928 24.356571h116.589714v116.589715H316.928V24.356571z m264.923429 0h116.516571v116.589715H581.851429V24.356571zM316.928 299.885714h116.589714v116.516572H316.928V299.885714z m264.923429 0h116.516571v116.516572H581.851429V299.885714zM316.928 575.268571h116.589714V691.931429H316.928V575.268571z m264.923429 0h116.516571V691.931429H581.851429V575.268571zM316.928 850.870857h116.589714v116.516572H316.928v-116.516572z m264.923429 0h116.516571v116.516572H581.851429v-116.516572z"
                                    fill="#B6B7BF"
                                />
                            </svg>
                        </template>
                        {{ item.label }}
                        <template v-if="item.closable" #closeIcon>
                            <span class="vort-tag-close-btn" @click="handleClose($event, item)" @mousedown.stop>
                                <CloseOutlined class="vort-tag-close-icon" />
                            </span>
                        </template>
                    </Tag>
                </slot>
            </div>
        </TransitionGroup>
    </div>
</template>

<style scoped>
.vort-draggable-tags {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}

.vort-draggable-tags [draggable="true"] {
    user-select: none;
    touch-action: none;
}

.vort-tag-wrapper {
    display: inline-flex;
    align-items: center;
    transition:
        transform 0.2s cubic-bezier(0.2, 0, 0, 1),
        opacity 0.15s ease;
}

.vort-tag-wrapper-draggable {
    cursor: grab;
}

.vort-tag-wrapper-draggable:active {
    cursor: grabbing;
}

.vort-tag-drag-icon {
    display: inline-block;
    flex: 0 0 auto;
}

/* 正在拖拽的元素 */
.vort-tag-wrapper-dragging {
    opacity: 0.4;
    transform: scale(0.95);
}

/* 关闭按钮 */
.vort-tag-close-btn {
    display: inline-flex;
}

.vort-tag-close-icon {
    font-size: 10px;
}

/* TransitionGroup 排序动画 - 核心丝滑效果 */
.tag-sort-move {
    transition: transform 0.25s cubic-bezier(0.2, 0, 0, 1);
}

/* 防止离开动画期间影响其他元素 */
.tag-sort-leave-active {
    display: none;
}

/* 添加/删除动画 */
.tag-sort-enter-active {
    transition: all 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.tag-sort-enter-from {
    opacity: 0;
    transform: scale(0.8);
}
</style>
