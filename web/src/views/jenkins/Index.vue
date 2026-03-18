<template>
    <div class="space-y-4 p-5">
        <!-- Header -->
        <div class="flex items-center justify-between">
            <div>
                <h2 class="text-lg font-semibold text-gray-800">Jenkins</h2>
                <p class="text-sm text-gray-400 mt-0.5">管理 CI/CD 流水线，查看构建状态与日志</p>
            </div>
            <div v-if="isAdmin && pageState !== 'loading'" class="flex items-center gap-2">
                <AiAssistButton
                    v-if="pageState === 'no-instances'"
                    label="AI 助手配置"
                    prompt="我需要配置 Jenkins 实例，请引导我完成。请先询问我 Jenkins 服务器的地址、用户名和 API Token，然后帮我创建实例并验证连通性。"
                />
                <VortButton variant="primary" @click="openInstanceForm(null)">
                    <Plus :size="14" class="mr-1" /> 添加实例
                </VortButton>
            </div>
        </div>

        <!-- Loading state -->
        <div v-if="pageState === 'loading'" class="bg-white rounded-xl flex items-center justify-center" style="min-height: 480px;">
            <Loader2 class="w-6 h-6 animate-spin text-gray-400" />
        </div>

        <!-- No instances -->
        <div v-else-if="pageState === 'no-instances'" class="bg-white rounded-xl flex items-center justify-center" style="min-height: 480px;">
            <div class="text-center max-w-sm">
                <HardDrive class="w-12 h-12 text-gray-300 mx-auto mb-4" />
                <h3 class="text-base font-medium text-gray-600 mb-2">{{ isAdmin ? "添加你的第一个 Jenkins 实例" : "暂无 Jenkins 实例" }}</h3>
                <p class="text-sm text-gray-400">{{ isAdmin ? "配置 Jenkins 服务器地址，开始管理你的 CI/CD 流水线。" : "请联系管理员添加 Jenkins 实例。" }}</p>
            </div>
        </div>

        <!-- Main content -->
        <div v-else class="bg-white rounded-xl overflow-hidden flex min-h-0" style="min-height: 540px;">
            <!-- Left panel: Instance list -->
            <div class="w-56 shrink-0 border-r border-gray-100">
                <InstanceList
                    :instances="instCtx.instances.value"
                    :selected-id="instCtx.selectedInstance.value?.id ?? null"
                    :loading="instCtx.loading.value"
                    :is-admin="isAdmin"
                    @select="handleSelectInstance"
                    @add="openInstanceForm(null)"
                    @edit="openInstanceForm"
                    @delete="handleDeleteInstance"
                    @verify="(inst) => instCtx.verifyInstance(inst.id)"
                    @set-default="handleSetDefault"
                />
            </div>

            <!-- Right panel -->
            <div class="flex-1 flex flex-col min-w-0">
                <!-- Per-instance credential not configured -->
                <div v-if="instCtx.credentialConfigured.value === false" class="flex-1 flex items-center justify-center">
                    <div class="text-center max-w-sm">
                        <KeyRound class="w-12 h-12 text-gray-300 mx-auto mb-4" />
                        <h3 class="text-base font-medium text-gray-600 mb-2">凭证未配置</h3>
                        <p class="text-sm text-gray-400 mb-6">
                            需要为实例「{{ instCtx.selectedInstance.value?.name }}」配置你的 Jenkins 账号才能使用。
                        </p>
                        <VortButton @click="credentialDialogOpen = true">配置凭证</VortButton>
                    </div>
                </div>

                <!-- Auth failed -->
                <div v-else-if="instCtx.credentialConfigured.value === true && authFailed" class="flex-1 flex items-center justify-center">
                    <div class="text-center max-w-sm">
                        <AlertTriangle class="w-12 h-12 text-amber-400 mx-auto mb-4" />
                        <h3 class="text-base font-medium text-gray-600 mb-2">凭证认证失败</h3>
                        <p class="text-sm text-gray-400 mb-6">
                            当前配置的 Jenkins 账号无法通过认证，请检查用户名和 API Token 是否正确。
                        </p>
                        <div class="flex items-center justify-center gap-3">
                            <VortButton @click="credentialDialogOpen = true">重新配置凭证</VortButton>
                            <VortButton variant="outline" @click="loadInstanceData(false)">重试</VortButton>
                        </div>
                    </div>
                </div>

                <!-- Credential OK: show jobs -->
                <template v-else-if="instCtx.credentialConfigured.value === true && !authFailed">
                    <div class="flex items-center border-b border-gray-100 overflow-hidden">
                        <ViewTabs
                            class="flex-1 min-w-0 !border-b-0"
                            :views="jobCtx.views.value"
                            :active-view="jobCtx.activeView.value"
                            @switch="handleSwitchView"
                        />
                        <VortTooltip title="修改凭证">
                            <button
                                class="shrink-0 px-3 py-2 mr-2 text-gray-400 hover:text-gray-600 transition-colors"
                                @click="credentialDialogOpen = true"
                            >
                                <Settings class="w-4 h-4" />
                            </button>
                        </VortTooltip>
                    </div>
                    <JobTable
                        :jobs="jobCtx.jobs.value"
                        :breadcrumbs="jobCtx.breadcrumbs.value"
                        :keyword="jobCtx.keyword.value"
                        :loading="jobCtx.loading.value"
                        :building-job="buildingJobName"
                        @enter-folder="handleEnterFolder"
                        @view-detail="handleViewDetail"
                        @trigger-build="handleTriggerBuild"
                        @view-config="handleViewConfig"
                        @navigate-breadcrumb="handleNavigateBreadcrumb"
                        @update:keyword="jobCtx.keyword.value = $event"
                        @search="refreshJobs"
                    />
                </template>

                <!-- Checking credential -->
                <div v-else class="flex-1 flex items-center justify-center">
                    <Loader2 class="w-5 h-5 animate-spin text-gray-400" />
                </div>
            </div>
        </div>

        <!-- Dialogs -->
        <InstanceFormDialog
            :open="instanceFormOpen"
            :edit-instance="editingInstance"
            @update:open="instanceFormOpen = $event"
            @submit="handleInstanceFormSubmit"
        />

        <CredentialDialog
            :open="credentialDialogOpen"
            :instance-name="instCtx.selectedInstance.value?.name ?? ''"
            :initial-username="instCtx.credentialUsername.value"
            @update:open="credentialDialogOpen = $event"
            @submit="handleCredentialSubmit"
        />

        <BuildDialog
            :open="buildDialogOpen"
            :job-name="buildJobName"
            :parameters="buildJobParams"
            :triggering="buildCtx.buildTriggering.value"
            @update:open="buildDialogOpen = $event"
            @confirm="handleBuildConfirm"
        />

        <JobDetailDrawer
            :open="jobDetailOpen"
            :job="jobCtx.jobDetail.value"
            :loading="jobCtx.jobDetailLoading.value"
            @update:open="jobDetailOpen = $event"
            @trigger-build="handleDetailTriggerBuild"
            @view-log="handleViewLog"
        />

        <ConfigDialog
            :open="configDialogOpen"
            :job-name="configJobName"
            :config="jobCtx.configSummary.value"
            :loading="jobCtx.configSummaryLoading.value"
            @update:open="configDialogOpen = $event"
        />

        <BuildLogViewer
            :open="buildLogOpen"
            :build-number="logBuildNumber"
            :build-result="logBuildResult"
            :log-content="buildCtx.buildLog.value"
            :log-loading="buildCtx.buildLogLoading.value"
            :truncated="buildCtx.buildLogTruncated.value"
            :line-count="buildCtx.buildLogLineCount.value"
            @update:open="buildLogOpen = $event"
            @load-full="loadFullLog"
        />
    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Loader2, HardDrive, Plus, KeyRound, AlertTriangle, Settings } from "lucide-vue-next";
import { AiAssistButton } from "@/components/vort-biz/ai-assist-button";
import { useUserStore } from "@/stores";

import InstanceList from "./components/InstanceList.vue";
import InstanceFormDialog from "./components/InstanceFormDialog.vue";
import CredentialDialog from "./components/CredentialDialog.vue";
import ViewTabs from "./components/ViewTabs.vue";
import JobTable from "./components/JobTable.vue";
import BuildDialog from "./components/BuildDialog.vue";
import JobDetailDrawer from "./components/JobDetailDrawer.vue";
import BuildLogViewer from "./components/BuildLogViewer.vue";
import ConfigDialog from "./components/ConfigDialog.vue";

import { useJenkinsInstances } from "./composables/useJenkinsInstances";
import { useJenkinsJobs } from "./composables/useJenkinsJobs";
import { useJenkinsBuild } from "./composables/useJenkinsBuild";
import type { JenkinsInstance, JenkinsJob, JenkinsParameterDef } from "./types";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const isAdmin = computed(() => userStore.userInfo?.roles?.includes("admin") ?? false);

const instCtx = useJenkinsInstances();
const jobCtx = useJenkinsJobs();
const buildCtx = useJenkinsBuild();

const initialLoading = ref(true);
const initialized = ref(false);
const pageState = computed(() => {
    if (initialLoading.value) return "loading";
    if (instCtx.instances.value.length === 0) return "no-instances";
    return "ready";
});

const currentInstanceId = computed(() => instCtx.selectedInstance.value?.id ?? "");

const authFailed = ref(false);

const JENKINS_STATE_KEY = "openvort.jenkins.nav-state";

function buildNavQuery(): Record<string, string> {
    const query: Record<string, string> = {};
    if (instCtx.selectedInstance.value?.id) {
        query.instance = instCtx.selectedInstance.value.id;
    }
    if (jobCtx.activeView.value && jobCtx.activeView.value !== "All") {
        query.view = jobCtx.activeView.value;
    }
    if (jobCtx.folderPath.value.length > 0) {
        query.folder = jobCtx.folderPath.value.join("/");
    }
    return query;
}

function syncUrlState() {
    const query = buildNavQuery();
    router.replace({ query });
    try { sessionStorage.setItem(JENKINS_STATE_KEY, JSON.stringify(query)); } catch {}
}

watch(
    [currentInstanceId, () => jobCtx.activeView.value, () => jobCtx.folderPath.value.join("/")],
    () => { if (initialized.value) syncUrlState(); },
);

async function loadInstanceData(silent = true) {
    if (!currentInstanceId.value) return;
    authFailed.value = false;
    const viewResult = await jobCtx.loadViews(currentInstanceId.value, silent);
    if (viewResult === "auth_error") {
        authFailed.value = true;
        return;
    }
    const jobResult = await jobCtx.loadJobs(currentInstanceId.value, silent);
    if (jobResult === "auth_error") {
        authFailed.value = true;
    }
}

const instanceFormOpen = ref(false);
const editingInstance = ref<JenkinsInstance | null>(null);

function openInstanceForm(inst: JenkinsInstance | null) {
    editingInstance.value = inst;
    instanceFormOpen.value = true;
}

async function handleInstanceFormSubmit(data: { name: string; url: string; verify_ssl: boolean; is_default: boolean }) {
    try {
        if (editingInstance.value) {
            await instCtx.editInstance(editingInstance.value.id, data);
        } else {
            await instCtx.addInstance(data);
        }
        instanceFormOpen.value = false;
    } catch { /* error handled by interceptor */ }
}

async function handleDeleteInstance(inst: JenkinsInstance) {
    if (!confirm(`确定要删除实例「${inst.name}」吗？`)) return;
    await instCtx.removeInstance(inst.id);
}

async function handleSetDefault(inst: JenkinsInstance) {
    await instCtx.editInstance(inst.id, { is_default: true });
}

function handleSelectInstance(inst: JenkinsInstance) {
    instCtx.credentialConfigured.value = null;
    authFailed.value = false;
    jobCtx.resetNavigation();
    instCtx.selectInstance(inst);
}

const credentialDialogOpen = ref(false);

async function handleCredentialSubmit(data: { username: string; api_token: string }) {
    if (!instCtx.selectedInstance.value) return;
    try {
        await instCtx.saveCredential(instCtx.selectedInstance.value.id, data);
        credentialDialogOpen.value = false;
        await loadInstanceData();
    } catch { /* error handled by interceptor */ }
}

watch(currentInstanceId, async (id) => {
    if (!id || !initialized.value) return;
    instCtx.credentialConfigured.value = null;
    jobCtx.resetNavigation();
    authFailed.value = false;
    await instCtx.checkCredential(id);
});

watch(() => instCtx.credentialConfigured.value, async (configured) => {
    if (configured === true && initialized.value) {
        await loadInstanceData();
    }
});

function handleSwitchView(viewName: string) {
    jobCtx.switchView(viewName);
    refreshJobs();
}

function handleEnterFolder(folderName: string) {
    jobCtx.enterFolder(folderName);
    refreshJobs();
}

function handleNavigateBreadcrumb(path: string[]) {
    jobCtx.navigateBreadcrumb(path);
    refreshJobs();
}

function refreshJobs() {
    if (currentInstanceId.value) {
        jobCtx.loadJobs(currentInstanceId.value);
    }
}

const jobDetailOpen = ref(false);

function handleViewDetail(job: JenkinsJob) {
    jobDetailOpen.value = true;
    if (currentInstanceId.value) {
        jobCtx.loadJobDetail(currentInstanceId.value, job.full_name || job.name);
    }
}

// Config dialog
const configDialogOpen = ref(false);
const configJobName = ref("");

function handleViewConfig(job: JenkinsJob) {
    const jobName = job.full_name || job.name;
    configJobName.value = jobName;
    configDialogOpen.value = true;
    if (currentInstanceId.value) {
        jobCtx.loadConfigSummary(currentInstanceId.value, jobName);
    }
}

const buildDialogOpen = ref(false);
const buildJobName = ref("");
const buildJobFullName = ref("");
const buildJobParams = ref<JenkinsParameterDef[]>([]);
const buildingJobName = ref("");

async function handleTriggerBuild(job: JenkinsJob) {
    buildJobName.value = job.name;
    buildJobFullName.value = job.full_name || job.name;
    buildingJobName.value = job.name;
    try {
        if (currentInstanceId.value) {
            await jobCtx.loadJobDetail(currentInstanceId.value, job.full_name || job.name);
            buildJobParams.value = jobCtx.jobDetail.value?.parameters ?? [];
        }
        buildDialogOpen.value = true;
    } finally {
        buildingJobName.value = "";
    }
}

function handleDetailTriggerBuild() {
    if (!jobCtx.jobDetail.value) return;
    buildJobName.value = jobCtx.jobDetail.value.name;
    buildJobFullName.value = jobCtx.jobDetail.value.full_name || jobCtx.jobDetail.value.name;
    buildJobParams.value = jobCtx.jobDetail.value.parameters;
    buildDialogOpen.value = true;
}

async function handleBuildConfirm(params: Record<string, any>) {
    if (!currentInstanceId.value) return;
    const hasParams = buildJobParams.value.length > 0;
    const ok = await buildCtx.trigger(
        currentInstanceId.value,
        buildJobFullName.value,
        hasParams ? params : undefined,
    );
    if (ok) {
        buildDialogOpen.value = false;
        refreshJobs();
    }
}

const buildLogOpen = ref(false);
const logBuildNumber = ref(0);
const logBuildResult = ref("");
const logJobName = ref("");

async function handleViewLog(buildNumber: number) {
    if (!currentInstanceId.value || !jobCtx.jobDetail.value) return;
    logJobName.value = jobCtx.jobDetail.value.full_name || jobCtx.jobDetail.value.name;
    logBuildNumber.value = buildNumber;
    const build = jobCtx.jobDetail.value.builds.find((b) => b.number === buildNumber);
    logBuildResult.value = build?.result || "";
    buildLogOpen.value = true;
    await buildCtx.loadBuildLog(currentInstanceId.value, logJobName.value, buildNumber);
}

async function loadFullLog() {
    if (!currentInstanceId.value) return;
    await buildCtx.loadBuildLog(currentInstanceId.value, logJobName.value, logBuildNumber.value, 5000);
}

onMounted(async () => {
    let navInstanceId = route.query.instance as string | undefined;
    let navView = route.query.view as string | undefined;
    let navFolder = route.query.folder as string | undefined;

    if (!navInstanceId) {
        try {
            const saved = sessionStorage.getItem(JENKINS_STATE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved) as Record<string, string>;
                navInstanceId = parsed.instance || undefined;
                navView = parsed.view || undefined;
                navFolder = parsed.folder || undefined;
            }
        } catch {}
    }

    await instCtx.loadInstances();
    initialLoading.value = false;

    if (instCtx.instances.value.length === 0) {
        initialized.value = true;
        return;
    }

    if (navInstanceId) {
        const inst = instCtx.instances.value.find(i => i.id === navInstanceId);
        if (inst) instCtx.selectInstance(inst);
    }

    if (currentInstanceId.value) {
        await instCtx.checkCredential(currentInstanceId.value);
    }

    if (instCtx.credentialConfigured.value === true) {
        if (navView) jobCtx.activeView.value = navView;
        if (navFolder) jobCtx.folderPath.value = navFolder.split("/");
        await loadInstanceData();
    }

    initialized.value = true;
});
</script>
