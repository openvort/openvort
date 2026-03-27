/**
 * 全局弹层栈管理
 *
 * 解决多个弹层（Dialog、Drawer、Image 预览等）叠加时的 ESC 事件冲突：
 * - 所有模态弹层打开时入栈、关闭时出栈
 * - 全局只有一个 keydown 监听器，ESC 只触发栈顶弹层的回调
 * - 栈顶弹层即使不响应 ESC（如 keyboard=false），也不会穿透到下层
 */

interface OverlayEntry {
    id: symbol;
    onEsc?: () => void;
}

const overlayStack: OverlayEntry[] = [];
let escListenerRegistered = false;

function handleGlobalEsc(e: KeyboardEvent) {
    if (e.key !== "Escape" || overlayStack.length === 0) return;

    const topEntry = overlayStack[overlayStack.length - 1];
    if (topEntry?.onEsc) {
        topEntry.onEsc();
    }
}

function ensureEscListener() {
    if (escListenerRegistered || typeof document === "undefined") return;
    document.addEventListener("keydown", handleGlobalEsc);
    escListenerRegistered = true;
}

/**
 * 弹层栈管理 composable
 *
 * @example
 * ```ts
 * const overlay = useOverlayStack();
 *
 * // 打开弹层时入栈
 * overlay.push(() => {
 *     if (props.keyboard) close();
 * });
 *
 * // 关闭弹层时出栈
 * overlay.pop();
 * ```
 */
export function useOverlayStack() {
    const id = Symbol("overlay");

    /**
     * 入栈 - 弹层打开时调用
     * @param onEsc 当此弹层处于栈顶时按 ESC 的回调
     */
    function push(onEsc?: () => void) {
        ensureEscListener();
        // 防止重复入栈（如组件先关后开时 watch 连续触发）
        const existingIdx = overlayStack.findIndex((e) => e.id === id);
        if (existingIdx > -1) overlayStack.splice(existingIdx, 1);
        overlayStack.push({ id, onEsc });
    }

    /** 出栈 - 弹层关闭时调用 */
    function pop() {
        const idx = overlayStack.findIndex((e) => e.id === id);
        if (idx > -1) overlayStack.splice(idx, 1);
    }

    /** 当前弹层是否在栈顶 */
    function isTopmost() {
        return overlayStack.length > 0 && overlayStack[overlayStack.length - 1]?.id === id;
    }

    /** 获取在栈中的位置索引（可用于 z-index 递增） */
    function getStackIndex() {
        return overlayStack.findIndex((e) => e.id === id);
    }

    return { id, push, pop, isTopmost, getStackIndex };
}
