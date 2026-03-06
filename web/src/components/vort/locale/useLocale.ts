import { inject, type InjectionKey, computed, type ComputedRef, type Ref, unref, isRef } from "vue";
import type { Locale, LocaleComponentName } from "./types";
import zhCN from "./zh-CN";

/**
 * Locale 注入 Key
 * 支持 Locale、Ref<Locale> 或 ComputedRef<Locale>
 */
export const localeContextKey: InjectionKey<Locale | Ref<Locale> | ComputedRef<Locale>> = Symbol("vortLocale");

/**
 * 字符串模板插值
 * @param template 模板字符串，如 "第 {start}-{end} 条"
 * @param params 参数对象，如 { start: 1, end: 10 }
 * @returns 替换后的字符串
 */
function interpolate(template: string, params: Record<string, string | number>): string {
    return template.replace(/\{(\w+)\}/g, (_, key) => {
        return params[key] !== undefined ? String(params[key]) : `{${key}}`;
    });
}

/**
 * 获取组件的国际化文本
 *
 * @param componentName 组件名称
 * @returns locale 对象和翻译函数 t
 *
 * @example
 * ```ts
 * const { t } = useLocale('Pagination');
 *
 * // 简单文本
 * t('prev_page') // => '上一页' 或 'Previous page'
 *
 * // 带参数的模板
 * t('total', { start: 1, end: 10, total: 100 })
 * // => '第 1-10 条 / 总共 100 条' 或 '1-10 of 100 items'
 * ```
 */
export function useLocale<T extends LocaleComponentName>(componentName: T) {
    const localeRef = inject(localeContextKey, zhCN);

    // 响应式获取当前 locale（支持 Ref、ComputedRef 或普通对象）
    const locale = computed(() => unref(localeRef));
    const componentLocale = computed(() => locale.value[componentName] as Locale[T]);

    /**
     * 获取翻译文本
     * @param key 文本键名
     * @param params 可选的插值参数
     */
    function t<K extends keyof Locale[T]>(key: K, params?: Record<string, string | number>): string {
        const text = componentLocale.value[key];
        if (text === undefined || text === null) {
            return String(key);
        }
        if (typeof text !== "string") {
            return String(text);
        }
        return params ? interpolate(text, params) : text;
    }

    return {
        /** 当前 locale 配置（ComputedRef） */
        locale,
        /** 当前组件的 locale 配置 */
        componentLocale,
        /** 翻译函数 */
        t
    };
}

/**
 * 获取完整的 locale 对象（不限定组件）
 *
 * @example
 * ```ts
 * const { locale } = useGlobalLocale();
 * console.log(locale.locale); // 'zh-CN' 或 'en-US'
 * ```
 */
export function useGlobalLocale() {
    const localeRef = inject(localeContextKey, zhCN);
    const locale = computed(() => unref(localeRef));
    return { locale };
}
