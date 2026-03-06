import { ref } from "vue";
import { dialog } from "@/components/vort";

/**
 * Track form dirty state and confirm before discarding unsaved changes.
 *
 * Usage:
 *   const { snapshot, takeSnapshot, isDirty, confirmClose } = useDirtyCheck(currentRow);
 *   // call takeSnapshot() when opening add/edit drawer
 *   // use confirmClose(closeFn) instead of directly setting drawerVisible = false
 */
export function useDirtyCheck<T extends Record<string, any>>(formData: { value: Partial<T> }) {
    const snapshot = ref<string>("");

    const takeSnapshot = () => {
        snapshot.value = JSON.stringify(formData.value);
    };

    const isDirty = () => {
        return JSON.stringify(formData.value) !== snapshot.value;
    };

    const confirmClose = (closeFn: () => void) => {
        if (isDirty()) {
            dialog.confirm({
                title: "放弃更改？",
                content: "当前内容尚未保存，确定要放弃更改吗？",
                okText: "放弃",
                cancelText: "继续编辑",
                okType: "danger",
                centered: true,
                onOk: closeFn,
            });
        } else {
            closeFn();
        }
    };

    return { snapshot, takeSnapshot, isDirty, confirmClose };
}
