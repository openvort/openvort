<script setup lang="ts">
import { useIsClient } from "@/components/vort/composables";

defineOptions({ name: "VortClientOnly" });

/**
 * Vort ClientOnly - 仅客户端渲染组件
 *
 * 用于包裹仅在客户端渲染的内容，SSR 时会渲染 fallback 插槽内容
 *
 * @example
 * ```vue
 * <ClientOnly>
 *   <template #fallback>
 *     <div>Loading...</div>
 *   </template>
 *   <ComplexComponent />
 * </ClientOnly>
 * ```
 */

const isMounted = useIsClient();
</script>

<template>
    <template v-if="isMounted">
        <slot />
    </template>
    <template v-else>
        <slot name="fallback" />
    </template>
</template>
