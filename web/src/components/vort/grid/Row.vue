<script setup lang="ts">
import { computed, provide } from "vue";
import { rowContextKey } from "./types";

defineOptions({ name: "VortRow" });

/** Vort Row - 栅格行组件 */

type Gutter = number | [number, number];
type Justify = "start" | "end" | "center" | "space-around" | "space-between" | "space-evenly";
type Align = "top" | "middle" | "bottom" | "stretch";

interface Props {
    /** 栅格间隔，可以是数字或数组 [水平间隔, 垂直间隔] */
    gutter?: Gutter;
    /** 水平排列方式 */
    justify?: Justify;
    /** 垂直对齐方式 */
    align?: Align;
    /** 是否自动换行 */
    wrap?: boolean;
    /** 自定义类名 */
    class?: string;
}

const props = withDefaults(defineProps<Props>(), {
    gutter: 0,
    justify: "start",
    align: "top",
    wrap: true
});

// 计算间隔
const gutterHorizontal = computed(() => {
    if (Array.isArray(props.gutter)) {
        return props.gutter[0] || 0;
    }
    return props.gutter || 0;
});

const gutterVertical = computed(() => {
    if (Array.isArray(props.gutter)) {
        return props.gutter[1] || 0;
    }
    return 0;
});

// 提供给 Col 组件使用
provide(rowContextKey, {
    get gutter() {
        return [gutterHorizontal.value, gutterVertical.value] as [number, number];
    }
});

// ========== 类名计算 ==========

const rowClasses = computed(() => {
    const classes = ["vort-row"];
    if (!props.wrap) classes.push("vort-row-nowrap");
    classes.push(`vort-row-justify-${props.justify}`);
    classes.push(`vort-row-align-${props.align}`);
    if (props.class) classes.push(props.class);
    return classes;
});

// 行样式 - 负 margin 用于抵消 gutter
const rowStyle = computed(() => {
    const style: Record<string, string> = {};

    if (gutterHorizontal.value > 0) {
        const marginX = -(gutterHorizontal.value / 2);
        style.marginLeft = `${marginX}px`;
        style.marginRight = `${marginX}px`;
    }

    if (gutterVertical.value > 0) {
        style.rowGap = `${gutterVertical.value}px`;
    }

    return style;
});
</script>

<template>
    <div :class="rowClasses" :style="rowStyle">
        <slot />
    </div>
</template>

<style scoped>
.vort-row {
    display: flex;
    flex-wrap: wrap;
    box-sizing: border-box;
}

.vort-row-nowrap {
    flex-wrap: nowrap;
}

/* ========== Justify ========== */
.vort-row-justify-start {
    justify-content: flex-start;
}

.vort-row-justify-end {
    justify-content: flex-end;
}

.vort-row-justify-center {
    justify-content: center;
}

.vort-row-justify-space-around {
    justify-content: space-around;
}

.vort-row-justify-space-between {
    justify-content: space-between;
}

.vort-row-justify-space-evenly {
    justify-content: space-evenly;
}

/* ========== Align ========== */
.vort-row-align-top {
    align-items: flex-start;
}

.vort-row-align-middle {
    align-items: center;
}

.vort-row-align-bottom {
    align-items: flex-end;
}

.vort-row-align-stretch {
    align-items: stretch;
}
</style>
