import { ref } from "vue";
import { getJenkinsInstances, createJenkinsInstance, updateJenkinsInstance, deleteJenkinsInstance, verifyJenkinsInstance, getJenkinsInstanceCredential, saveJenkinsInstanceCredential, deleteJenkinsInstanceCredential } from "@/api/jenkins";
import { message } from "@openvort/vort-ui";
import type { JenkinsInstance } from "../types";

export function useJenkinsInstances() {
    const instances = ref<JenkinsInstance[]>([]);
    const selectedInstance = ref<JenkinsInstance | null>(null);
    const loading = ref(false);
    const credentialConfigured = ref<boolean | null>(null);
    const credentialUsername = ref("");

    async function checkCredential(instanceId?: string) {
        const id = instanceId || selectedInstance.value?.id;
        if (!id) {
            credentialConfigured.value = null;
            return;
        }
        try {
            const res: any = await getJenkinsInstanceCredential(id);
            credentialConfigured.value = res.configured;
            credentialUsername.value = res.username || "";
        } catch {
            credentialConfigured.value = false;
        }
    }

    async function saveCredential(instanceId: string, data: { username: string; api_token: string }) {
        await saveJenkinsInstanceCredential(instanceId, data);
        message.success("凭证配置成功");
        credentialConfigured.value = true;
        credentialUsername.value = data.username;
    }

    async function removeCredential(instanceId: string) {
        await deleteJenkinsInstanceCredential(instanceId);
        message.success("凭证已删除");
        credentialConfigured.value = false;
        credentialUsername.value = "";
    }

    async function loadInstances() {
        loading.value = true;
        try {
            const res: any = await getJenkinsInstances();
            instances.value = res.instances || [];
            if (!selectedInstance.value && instances.value.length > 0) {
                const defaultInst = instances.value.find((i) => i.is_default);
                selectedInstance.value = defaultInst || instances.value[0];
            }
            if (selectedInstance.value) {
                const stillExists = instances.value.find((i) => i.id === selectedInstance.value!.id);
                if (!stillExists) {
                    selectedInstance.value = instances.value[0] || null;
                }
            }
        } catch {
            // error handled by interceptor
        } finally {
            loading.value = false;
        }
    }

    async function addInstance(data: { name: string; url: string; verify_ssl?: boolean; is_default?: boolean }) {
        const res: any = await createJenkinsInstance(data);
        message.success(`实例「${res.name}」创建成功`);
        await loadInstances();
        if (res.id) {
            selectedInstance.value = instances.value.find((i) => i.id === res.id) || selectedInstance.value;
        }
        return res;
    }

    async function editInstance(id: string, data: { name?: string; url?: string; verify_ssl?: boolean; is_default?: boolean }) {
        const res: any = await updateJenkinsInstance(id, data);
        message.success(`实例「${res.name}」更新成功`);
        await loadInstances();
        return res;
    }

    async function removeInstance(id: string) {
        await deleteJenkinsInstance(id);
        message.success("实例已删除");
        await loadInstances();
    }

    async function verifyInstance(id: string) {
        try {
            await verifyJenkinsInstance(id);
            message.success("连接成功");
            return true;
        } catch {
            return false;
        }
    }

    function selectInstance(inst: JenkinsInstance) {
        selectedInstance.value = inst;
    }

    return {
        instances,
        selectedInstance,
        loading,
        credentialConfigured,
        credentialUsername,
        checkCredential,
        saveCredential,
        removeCredential,
        loadInstances,
        addInstance,
        editInstance,
        removeInstance,
        verifyInstance,
        selectInstance,
    };
}
