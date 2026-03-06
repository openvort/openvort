<script setup lang="ts">
import { computed } from "vue";
import SkeletonAvatar from "./SkeletonAvatar.vue";

defineOptions({ name: "VortSkeleton" });

/** Vort Skeleton - 骨架屏组件 */

export interface SkeletonTitleProps {
    /** 标题宽度 */
    width?: string | number;
}

export interface SkeletonParagraphProps {
    /** 段落行数 */
    rows?: number;
    /** 每行宽度，可以是数组或单个值 */
    width?: string | number | (string | number)[];
}

export interface SkeletonAvatarProps {
    /** 头像大小 */
    size?: "large" | "small" | "default" | number;
    /** 头像形状 */
    shape?: "circle" | "square";
}

interface Props {
    /** 是否显示动画效果 */
    active?: boolean;
    /** 是否显示头像占位 */
    avatar?: boolean | SkeletonAvatarProps;
    /** 是否显示骨架屏（为 true 时显示骨架屏，为 false 时显示子内容） */
    loading?: boolean;
    /** 是否显示段落占位 */
    paragraph?: boolean | SkeletonParagraphProps;
    /** 是否显示圆角 */
    round?: boolean;
    /** 是否显示标题占位 */
    title?: boolean | SkeletonTitleProps;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    active: false,
    avatar: false,
    loading: true,
    paragraph: true,
    round: false,
    title: true
});

const slots = defineSlots<{
    default?(): unknown;
}>();

// 获取头像配置
const avatarProps = computed(() => {
    if (typeof props.avatar === "boolean") {
        return props.avatar ? {} : null;
    }
    return props.avatar;
});

// 获取标题配置
const titleProps = computed(() => {
    if (typeof props.title === "boolean") {
        return props.title ? {} : null;
    }
    return props.title;
});

// 获取段落配置
const paragraphProps = computed(() => {
    if (typeof props.paragraph === "boolean") {
        return props.paragraph ? { rows: 3 } : null;
    }
    return { rows: 3, ...props.paragraph };
});

// 计算段落行宽度
const getParagraphWidth = (index: number): string => {
    if (!paragraphProps.value) return "100%";

    const { width, rows = 3 } = paragraphProps.value;

    // 如果没有指定宽度，最后一行默认 61%
    if (!width) {
        return index === rows - 1 ? "61%" : "100%";
    }

    // 如果是数组
    if (Array.isArray(width)) {
        return formatWidth(width[index] ?? "100%");
    }

    // 如果是单个值，只应用于最后一行
    return index === rows - 1 ? formatWidth(width) : "100%";
};

// 格式化宽度值
const formatWidth = (width: string | number): string => {
    if (typeof width === "number") {
        return `${width}px`;
    }
    return width;
};

// 容器样式
const containerClass = computed(() => {
    const classes = ["vort-skeleton"];
    if (props.active) classes.push("vort-skeleton-active");
    if (props.round) classes.push("vort-skeleton-round");
    if (avatarProps.value) classes.push("vort-skeleton-with-avatar");
    if (props.class) classes.push(props.class);
    return classes;
});
</script>

<template>
    <!-- 显示骨架屏 -->
    <div v-if="loading" :class="containerClass">
        <!-- 头像区域 -->
        <div v-if="avatarProps" class="vort-skeleton-header">
            <SkeletonAvatar :size="avatarProps.size" :shape="avatarProps.shape" :active="active" />
        </div>

        <!-- 内容区域 -->
        <div class="vort-skeleton-content">
            <!-- 标题 -->
            <h3
                v-if="titleProps"
                class="vort-skeleton-title"
                :style="{ width: titleProps.width ? formatWidth(titleProps.width) : avatarProps ? '50%' : '38%' }"
            />

            <!-- 段落 -->
            <ul v-if="paragraphProps" class="vort-skeleton-paragraph">
                <li v-for="index in paragraphProps.rows" :key="index" :style="{ width: getParagraphWidth(index - 1) }" />
            </ul>
        </div>
    </div>

    <!-- 显示实际内容 -->
    <slot v-else />
</template>

<style scoped>
.vort-skeleton {
    display: table;
    width: 100%;
}

.vort-skeleton-header {
    display: table-cell;
    padding-right: 16px;
    vertical-align: top;
}

.vort-skeleton-content {
    display: table-cell;
    width: 100%;
    vertical-align: top;
}

.vort-skeleton-title {
    height: 16px;
    margin-top: 16px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 4px;
}

.vort-skeleton-with-avatar .vort-skeleton-title {
    margin-top: 12px;
}

.vort-skeleton-paragraph {
    margin: 0;
    padding: 0;
    list-style: none;
}

.vort-skeleton-paragraph > li {
    height: 16px;
    margin-top: 16px;
    background: rgba(0, 0, 0, 0.06);
    border-radius: 4px;
}

.vort-skeleton-paragraph > li:first-child {
    margin-top: 24px;
}

.vort-skeleton-with-avatar .vort-skeleton-paragraph > li:first-child {
    margin-top: 12px;
}

/* 圆角模式 */
.vort-skeleton-round .vort-skeleton-title {
    border-radius: 100px;
}

.vort-skeleton-round .vort-skeleton-paragraph > li {
    border-radius: 100px;
}

/* 动画效果 */
.vort-skeleton-active .vort-skeleton-title,
.vort-skeleton-active .vort-skeleton-paragraph > li,
.vort-skeleton-active :deep(.vort-skeleton-avatar) {
    background: linear-gradient(90deg, rgba(0, 0, 0, 0.06) 25%, rgba(0, 0, 0, 0.15) 37%, rgba(0, 0, 0, 0.06) 63%);
    background-size: 400% 100%;
    animation: vort-skeleton-loading 1.4s ease infinite;
}

@keyframes vort-skeleton-loading {
    0% {
        background-position: 100% 50%;
    }
    100% {
        background-position: 0 50%;
    }
}
</style>
