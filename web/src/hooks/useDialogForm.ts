import { ref, computed, onMounted, watch, type Ref } from "vue";
import { message } from "@/components/vort/message";

export interface DialogFormProps<P = Record<string, unknown>> {
    params: P;
    okHandler?: (payload?: unknown) => void;
    cancelHandler?: () => void;
    confirmLoading?: boolean;
}

export interface CommonFormParams {
    id?: string;
    act?: "add" | "detail" | string;
    examine?: number;
    [key: string]: unknown;
}

export interface UseDialogFormOptions<T, P extends CommonFormParams = CommonFormParams> {
    defaultFormState: T;
    detailApi?: (params: { id: string }) => Promise<T>;
    submitApi: (operation: "create" | "update", data: T & { id?: string }) => Promise<unknown>;
    props: DialogFormProps<P>;
    formRef: Ref<{ validateFields: () => Promise<unknown> } | null>;
    successMessage?: string;
    autoFetchOnMount?: boolean;
    operationMap?: Record<string, "create" | "update">;
}

export function useDialogForm<T extends object, P extends CommonFormParams = CommonFormParams>(options: UseDialogFormOptions<T, P>) {
    const {
        defaultFormState, detailApi, submitApi, props, formRef,
        successMessage = "操作成功", autoFetchOnMount = true,
        operationMap = { add: "create", detail: "update" }
    } = options;

    const loading = ref(true);
    const formState = ref<T>({ ...defaultFormState }) as Ref<T>;

    const id = computed<string | undefined>(() => props.params.id);
    const hasValidId = computed(() => id.value !== undefined && id.value !== null && id.value !== "");
    const action = computed(() => props.params.act ?? "add");
    const isReadonly = computed(() => props.params.examine === 1);
    const isEdit = computed(() => action.value !== "add");
    const isAdd = computed(() => action.value === "add");
    const operation = computed(() => operationMap[action.value] ?? "update");

    const fetchDetail = async () => {
        if (!detailApi || !hasValidId.value) { loading.value = false; return; }
        try {
            const result = await detailApi({ id: id.value as string });
            Object.assign(formState.value, result);
        } catch (error: unknown) {
            message.error(error instanceof Error ? error.message : "加载失败");
            props.cancelHandler?.();
        } finally {
            loading.value = false;
        }
    };

    const onSubmit = async () => {
        try {
            const validateResult = await formRef.value?.validateFields();
            if (validateResult && typeof validateResult === "object" && "valid" in validateResult) {
                if (!(validateResult as { valid: boolean }).valid) { message.error("请检查表单填写"); return; }
            }
        } catch { message.error("请检查表单填写"); return; }

        try {
            const data = operation.value === "create" ? { ...formState.value } : { id: id.value as string, ...formState.value };
            await submitApi(operation.value, data);
            message.success(successMessage);
            props.okHandler?.();
        } catch (error: any) {
            if (error?.message) message.error(error.message);
        }
    };

    const resetFormState = () => { Object.assign(formState.value, defaultFormState); };

    onMounted(() => {
        if (autoFetchOnMount && isEdit.value) fetchDetail();
        else loading.value = false;
    });

    watch([() => props.params.id, () => props.params.act], () => {
        if (isAdd.value) { resetFormState(); loading.value = false; return; }
        loading.value = true; resetFormState(); fetchDetail();
    }, { immediate: false });

    return { loading, formState, id, hasValidId, action, isReadonly, isEdit, isAdd, operation, fetchDetail, onSubmit, resetFormState };
}
