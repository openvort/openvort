import { ref, onMounted, onUnmounted } from "vue";

/**
 * 响应式媒体查询 hook
 * 监听指定的 CSS 媒体查询，返回响应式的匹配状态
 */
export function useMediaQuery(query: string) {
    const matches = ref(false);
    let mediaQuery: MediaQueryList | null = null;

    const updateMatches = () => {
        if (mediaQuery) {
            matches.value = mediaQuery.matches;
        }
    };

    onMounted(() => {
        mediaQuery = window.matchMedia(query);
        matches.value = mediaQuery.matches;
        mediaQuery.addEventListener("change", updateMatches);
    });

    onUnmounted(() => {
        if (mediaQuery) {
            mediaQuery.removeEventListener("change", updateMatches);
        }
    });

    return matches;
}

/**
 * 响应式断点 hook
 * 提供常用断点的响应式检测
 * - isMobile: < 768px
 * - isTablet: 768px ~ 991px
 * - isDesktop: >= 992px
 */
export function useBreakpoint() {
    const isMobile = useMediaQuery("(max-width: 767px)");
    const isTablet = useMediaQuery("(min-width: 768px) and (max-width: 991px)");
    const isDesktop = useMediaQuery("(min-width: 992px)");

    return { isMobile, isTablet, isDesktop };
}
