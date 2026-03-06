import { ref, onMounted } from "vue";

/**
 * Vort SSR 环境检测工具
 *
 * 提供 SSR 环境检测能力，确保组件在服务端渲染时不会访问浏览器 API
 */

/**
 * 是否在客户端环境
 * - 可用于模块顶层的静态判断
 * - 注意：在 SSR hydration 前后值不会变化
 */
export const isClient = typeof window !== "undefined";

/**
 * 是否在服务端环境
 */
export const isServer = !isClient;

/**
 * SSR 安全的客户端状态 composable
 *
 * 返回一个 ref，在组件挂载后变为 true
 * 适用于需要在模板中条件渲染仅客户端内容的场景
 *
 * @example
 * ```vue
 * <script setup>
 * const isMounted = useIsClient()
 * </script>
 *
 * <template>
 *   <Teleport v-if="isMounted" to="body">
 *     <MyPopup />
 *   </Teleport>
 * </template>
 * ```
 */
export function useIsClient() {
    const isMounted = ref(false);

    onMounted(() => {
        isMounted.value = true;
    });

    return isMounted;
}

/**
 * SSR 安全的函数执行包装器
 *
 * 仅在客户端执行传入的函数，服务端直接跳过
 *
 * @param fn 要执行的函数
 * @returns 函数返回值，服务端返回 undefined
 *
 * @example
 * ```ts
 * const width = onClient(() => window.innerWidth)
 * ```
 */
export function onClient<T>(fn: () => T): T | undefined {
    if (isClient) {
        return fn();
    }
    return undefined;
}
