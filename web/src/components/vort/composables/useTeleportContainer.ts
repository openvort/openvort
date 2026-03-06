/**
 * Vort Teleport 容器工具
 *
 * 目的：
 * - 让 Teleport 到 body 的弹层也能继承 ConfigProvider 的 CSS 变量（主题 token）
 * - 默认将弹层渲染到 App 内部的统一容器上（如果存在）
 */
export const VORT_TELEPORT_CONTAINER_ID = "vort-teleport-container";

/**
 * 获取默认的“Popup 容器”元素
 *
 * - 优先返回 App 内部的 `#vort-teleport-container`
 * - 不存在时回退到 `document.body`
 *
 * 说明：
 * 这里返回的是 HTMLElement，用于 `getPopupContainer` 这类 API（需要元素而不是选择器）
 */
export function getVortPopupContainer(): HTMLElement {
    // SSR / 预渲染时不访问 window/document
    if (typeof window === "undefined") return undefined as unknown as HTMLElement;

    const el = document.getElementById(VORT_TELEPORT_CONTAINER_ID);
    return el ?? document.body;
}

/**
 * 获取 Teleport 的默认挂载点
 *
 * @returns HTMLElement（优先）或 'body' 选择器字符串
 */
export function getVortTeleportTo(): HTMLElement | string {
    // SSR / 预渲染时不访问 window/document
    if (typeof window === "undefined") return "body";

    const el = document.getElementById(VORT_TELEPORT_CONTAINER_ID);
    return el ?? "body";
}
